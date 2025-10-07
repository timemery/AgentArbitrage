import logging
import os
import json
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
from .keepa_api import fetch_deals_for_deals, fetch_product_batch, validate_asin
from .token_manager import TokenManager
from .business_calculations import (
    load_settings as business_load_settings,
)
from .processing import _process_single_deal, clean_and_prepare_row_for_db

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# --- Constants ---
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'deals.db')
TABLE_NAME = 'deals'
HEADERS_PATH = os.path.join(os.path.dirname(__file__), 'headers.json')
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
        deal_response_raw = fetch_deals_for_deals(0, api_key, use_deal_settings=True)

        # CRITICAL FIX: Handle API functions that may return a tuple (data, info) instead of just data.
        deal_response = deal_response_raw[0] if isinstance(deal_response_raw, tuple) else deal_response_raw

        # Authoritatively update token manager with actual cost from the response
        tokens_consumed = deal_response.get('tokensConsumed', 0) if deal_response else 0
        token_manager.update_after_call(tokens_consumed)

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
            # Request historical data to enable all calculations.
            product_response, _, _, tokens_left = fetch_product_batch(
                api_key, batch_asins, history=1, offers=20
            )
            if tokens_left is not None:
                token_manager.update_after_call(tokens_left)

            if product_response and 'products' in product_response:
                for p in product_response['products']:
                    all_fetched_products[p['asin']] = p
        logger.info(f"Step 2 Complete: Fetched product data for {len(all_fetched_products)} ASINs.")

        logger.info("Step 3: Processing deals...")
        with open(HEADERS_PATH) as f:
            headers = json.load(f)

        rows_to_upsert = []
        for deal in recent_deals:
            asin = deal['asin']
            if asin not in all_fetched_products:
                continue

            product_data = all_fetched_products[asin]
            product_data.update(deal)

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

                # The list of original headers from the JSON file defines the canonical order.
                original_headers = headers
                sanitized_headers = [sanitize_col_name(h) for h in original_headers]

                # --- Data Cleaning and Type Conversion ---
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

        logger.info("--- Task: update_recent_deals finished ---")
    finally:
        lock.release()
        logger.info("--- Task: update_recent_deals finished and lock released. ---")