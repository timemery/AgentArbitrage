import logging
import os
import json
import sqlite3
from datetime import datetime, timezone
from dotenv import load_dotenv
import redis

from celery_config import celery
from .db_utils import create_deals_table_if_not_exists, sanitize_col_name
from .keepa_api import fetch_deals_for_deals, fetch_product_batch, validate_asin, fetch_seller_data
from .token_manager import TokenManager
from .business_calculations import load_settings as business_load_settings
from .processing import _process_single_deal, clean_and_prepare_row_for_db
from .seller_info import seller_data_cache

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'deals.db')
TABLE_NAME = 'deals'
HEADERS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'keepa_deals', 'headers.json')
MAX_ASINS_PER_BATCH = 50
LOCK_KEY = "update_recent_deals_lock"
LOCK_TIMEOUT = 60 * 60  # 1 hour lock timeout

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

        # Step 1: Fetch all pages of recent deals
        logger.info("Step 1: Fetching all pages of recent deals...")
        all_deals = []
        page = 0
        while True:
            token_manager.request_permission_for_call(estimated_cost=5)
            deal_response, tokens_left = fetch_deals_for_deals(page, api_key, use_deal_settings=True)
            if tokens_left is not None: token_manager.update_after_call(tokens_left)

            if not deal_response or 'deals' not in deal_response or not deal_response['deals']['dr']:
                logger.info(f"No more deals found on page {page}. Ending deal fetch.")
                break

            deals_page = [d for d in deal_response['deals']['dr'] if validate_asin(d.get('asin'))]
            all_deals.extend(deals_page)
            logger.info(f"Fetched {len(deals_page)} valid deals from page {page}. Total deals so far: {len(all_deals)}")
            page += 1

        if not all_deals:
            logger.info("Step 1 Complete: No new valid deals found across all pages.")
            return
        logger.info(f"Step 1 Complete: Fetched a total of {len(all_deals)} deals.")

        # Step 2: Fetch product data for all deals
        logger.info("Step 2: Fetching product data for all deals...")
        all_fetched_products = {}
        asin_list = [d['asin'] for d in all_deals]

        for i in range(0, len(asin_list), MAX_ASINS_PER_BATCH):
            batch_asins = asin_list[i:i + MAX_ASINS_PER_BATCH]
            estimated_cost = len(batch_asins) * 2
            token_manager.request_permission_for_call(estimated_cost)

            product_response, _, _, tokens_left = fetch_product_batch(api_key, batch_asins, history=1, offers=20)
            if tokens_left is not None: token_manager.update_after_call(tokens_left)

            if product_response and 'products' in product_response:
                for p in product_response['products']: all_fetched_products[p['asin']] = p
        logger.info(f"Step 2 Complete: Fetched product data for {len(all_fetched_products)} ASINs.")

        # Step 2.5: Pre-fetch all seller data
        logger.info("Step 2.5: Pre-fetching all required seller data...")
        unique_seller_ids = {offer['sellerId'] for p in all_fetched_products.values() for offer in p.get('offers', []) if offer.get('sellerId')}
        seller_ids_to_fetch = list(unique_seller_ids - set(seller_data_cache.keys()))

        if seller_ids_to_fetch:
            logger.info(f"Found {len(seller_ids_to_fetch)} new sellers to fetch.")
            estimated_cost = len(seller_ids_to_fetch)
            token_manager.request_permission_for_call(estimated_cost)

            seller_data_response, _, _, tokens_left = fetch_seller_data(api_key, seller_ids_to_fetch)
            if tokens_left is not None: token_manager.update_after_call(tokens_left)

            if seller_data_response and seller_data_response.get('sellers'):
                for seller_id, data in seller_data_response['sellers'].items(): seller_data_cache[seller_id] = data
        else:
            logger.info("All required seller data is already in cache.")
        logger.info("Step 2.5 Complete: Seller data pre-fetched and cached.")

        # Step 3: Process deals
        logger.info("Step 3: Processing deals...")
        with open(HEADERS_PATH) as f: headers = json.load(f)

        rows_to_upsert = []
        for deal in all_deals:
            asin = deal['asin']
            if asin not in all_fetched_products: continue

            product_data = all_fetched_products[asin]
            product_data.update(deal)

            processed_row = _process_single_deal(product_data, api_key, xai_api_key, business_settings, headers)

            if processed_row:
                processed_row['last_seen_utc'] = datetime.now(timezone.utc).isoformat()
                processed_row['source'] = 'upserter'
                rows_to_upsert.append(processed_row)
        logger.info(f"Step 3 Complete: Processed {len(rows_to_upsert)} deals.")

        if not rows_to_upsert:
            logger.info("No rows to upsert. Task finished.")
            return

        # Step 4: Upsert to database
        logger.info(f"Step 4: Upserting {len(rows_to_upsert)} rows into database...")
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                original_headers = headers
                sanitized_headers = [sanitize_col_name(h) for h in original_headers]

                cursor.execute(f"PRAGMA table_info({TABLE_NAME})")
                schema_info = {row[1]: row[2] for row in cursor.fetchall()}

                data_for_upsert = [clean_and_prepare_row_for_db(row, original_headers, schema_info) for row in rows_to_upsert]

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