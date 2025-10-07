import logging
import os
import json
import sqlite3
import time
from datetime import datetime, timezone
from dotenv import load_dotenv
import redis

from celery_config import celery
from .db_utils import create_deals_table_if_not_exists, sanitize_col_name
from .keepa_api import fetch_deals_for_deals, fetch_product_batch, validate_asin, fetch_seller_data
from .token_manager import TokenManager
from .business_calculations import load_settings as business_load_settings
from .processing import _process_single_deal, clean_and_prepare_row_for_db
from .seller_info import seller_data_cache # Import the cache to populate it

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# --- Constants ---
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'deals.db')
TABLE_NAME = 'deals'
HEADERS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'keepa_deals', 'headers.json')
MAX_ASINS_PER_BATCH = 50
LOCK_KEY = "update_recent_deals_lock"
LOCK_TIMEOUT = 60 * 30  # 30 minutes


@celery.task(name='keepa_deals.tasks.update_recent_deals')
def update_recent_deals():
    redis_client = redis.Redis.from_url(celery.conf.broker_url)
    lock = redis_client.lock(LOCK_KEY, timeout=LOCK_TIMEOUT)

    if not lock.acquire(blocking=False):
        logger.info("--- Task: update_recent_deals is already running. Skipping execution. ---")
        return

    try:
        logger.info("--- Task: update_recent_deals started ---")
        create_deals_table_if_not_exists()

        api_key = os.getenv("KEEPA_API_KEY")
        xai_api_key = os.getenv("XAI_API_KEY")
        if not api_key:
            logger.error("KEEPA_API_KEY not set. Aborting.")
            return

        token_manager = TokenManager(api_key)
        business_settings = business_load_settings()

        logger.info("Step 1: Fetching recent deals...")
        token_manager.request_permission_for_call(estimated_cost=5)
        deal_response, tokens_left = fetch_deals_for_deals(1, api_key, use_deal_settings=True)
        if tokens_left is not None: token_manager.update_after_call(tokens_left)

        if not deal_response or 'deals' not in deal_response:
            logger.error("Step 1 Failed: No response from deal fetch.")
            return

        recent_deals = [d for d in deal_response.get('deals', {}).get('dr', []) if validate_asin(d.get('asin'))]
        if not recent_deals:
            logger.info("Step 1 Complete: No new valid deals found.")
            return
        logger.info(f"Step 1 Complete: Fetched {len(recent_deals)} deals.")

        logger.info("Step 2: Fetching product data for deals...")
        all_fetched_products = {}
        asin_list = [d['asin'] for d in recent_deals]

        for i in range(0, len(asin_list), MAX_ASINS_PER_BATCH):
            batch_asins = asin_list[i:i + MAX_ASINS_PER_BATCH]
            estimated_cost = len(batch_asins) * 2
            token_manager.request_permission_for_call(estimated_cost)

            product_response, _, _, tokens_left = fetch_product_batch(api_key, batch_asins, history=1, offers=20)
            if tokens_left is not None: token_manager.update_after_call(tokens_left)

            if product_response and 'products' in product_response:
                for p in product_response['products']: all_fetched_products[p['asin']] = p
        logger.info(f"Step 2 Complete: Fetched product data for {len(all_fetched_products)} ASINs.")

        # --- Step 2.5: Pre-fetch all seller data to prevent runaway calls ---
        logger.info("Step 2.5: Pre-fetching all required seller data...")
        unique_seller_ids = set()
        for product in all_fetched_products.values():
            for offer in product.get('offers', []):
                if offer.get('sellerId'):
                    unique_seller_ids.add(offer['sellerId'])

        seller_ids_to_fetch = list(unique_seller_ids - set(seller_data_cache.keys()))

        if seller_ids_to_fetch:
            logger.info(f"Found {len(seller_ids_to_fetch)} new sellers to fetch.")
            estimated_cost = len(seller_ids_to_fetch)
            token_manager.request_permission_for_call(estimated_cost)

            seller_data_response, _, _, tokens_left = fetch_seller_data(api_key, seller_ids_to_fetch)
            if tokens_left is not None: token_manager.update_after_call(tokens_left)

            if seller_data_response and seller_data_response.get('sellers'):
                for seller_id, data in seller_data_response['sellers'].items():
                    seller_data_cache[seller_id] = data # Populate the cache
        else:
            logger.info("All required seller data is already in cache.")
        logger.info("Step 2.5 Complete: Seller data pre-fetched and cached.")


        logger.info("Step 3: Processing deals...")
        with open(HEADERS_PATH) as f: headers = json.load(f)

        rows_to_upsert = []
        for deal in recent_deals:
            asin = deal['asin']
            if asin not in all_fetched_products: continue

            product_data = all_fetched_products[asin]
            product_data.update(deal)

            # The token_manager is now passed for potential future use, but seller calls are cached.
            processed_row = _process_single_deal(product_data, api_key, token_manager, xai_api_key, business_settings, headers)

            if processed_row:
                processed_row['last_seen_utc'] = datetime.now(timezone.utc).isoformat()
                processed_row['source'] = 'upserter'
                rows_to_upsert.append(processed_row)
        logger.info(f"Step 3 Complete: Processed {len(rows_to_upsert)} deals.")

        if not rows_to_upsert:
            logger.info("No rows to upsert. Task finished.")
            return

        logger.info(f"Step 4: Upserting {len(rows_to_upsert)} rows into database...")
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                original_headers = headers
                sanitized_headers = [sanitize_col_name(h) for h in original_headers]

                cursor.execute(f"PRAGMA table_info({TABLE_NAME})")
                schema_info = {row[1]: row[2] for row in cursor.fetchall()}

                data_for_upsert = [
                    clean_and_prepare_row_for_db(row_dict, original_headers, schema_info)
                    for row_dict in rows_to_upsert
                ]

                upsert_sql = f"""
                INSERT INTO {TABLE_NAME} ({', '.join(f'"{h}"' for h in sanitized_headers)})
                VALUES ({', '.join(['?'] * len(sanitized_headers))})
                ON CONFLICT(ASIN) DO UPDATE SET
                  {', '.join(f'"{h}"=excluded."{h}"' for h in sanitized_headers if h != 'ASIN')}
                """

                cursor.executemany(upsert_sql, data_for_upsert)
                conn.commit()
                logger.info(f"Step 4 Complete: Successfully upserted/updated {cursor.rowcount} rows.")
        except sqlite3.Error as e:
            logger.error(f"Step 4 Failed: Database error during upsert: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Step 4 Failed: Unexpected error during upsert: {e}", exc_info=True)

    finally:
        lock.release()
        logger.info("--- Task: update_recent_deals finished and lock released. ---")