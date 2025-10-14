from logging import getLogger
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
from .field_mappings import FUNCTION_LIST
from .seller_info import get_all_seller_info
from .business_calculations import (
    load_settings as business_load_settings,
    calculate_total_amz_fees,
    calculate_all_in_cost,
    calculate_profit_and_margin,
    calculate_min_listing_price,
)
from .new_analytics import get_1yr_avg_sale_price, get_percent_discount, get_trend
from .seasonality_classifier import classify_seasonality, get_sells_period
from .processing import _process_single_deal

# Configure logging
logger = getLogger(__name__)

# Load environment variables
load_dotenv()

# --- Constants ---
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'deals.db')
TABLE_NAME = 'deals'
HEADERS_PATH = os.path.join(os.path.dirname(__file__), 'headers.json')
MAX_ASINS_PER_BATCH = 50
LOCK_KEY = "update_recent_deals_lock"
LOCK_TIMEOUT = 60 * 30  # 30 minutes


@celery.task(name='keepa_deals.simple_task.update_recent_deals')
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
        deal_response_raw, tokens_consumed, tokens_left = fetch_deals_for_deals(0, api_key, use_deal_settings=True)
        token_manager.update_after_call(tokens_consumed)
        
        deal_response = deal_response_raw

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
            product_response, api_info, tokens_consumed, tokens_left = fetch_product_batch(
                api_key, batch_asins, history=1, offers=20
            )
            token_manager.update_after_call(tokens_consumed)

            if product_response and 'products' in product_response and not (api_info and api_info.get('error_status_code')):
                for p in product_response['products']:
                    all_fetched_products[p['asin']] = p
        logger.info(f"Step 2 Complete: Fetched product data for {len(all_fetched_products)} ASINs.")

        logger.info("Step 2.5: Pre-fetching all seller data...")
        unique_seller_ids = set()
        for product in all_fetched_products.values():
            for offer in product.get('offers', []):
                if offer.get('sellerId'):
                    unique_seller_ids.add(offer['sellerId'])

        from .keepa_api import fetch_seller_data
        seller_data_cache = {}
        if unique_seller_ids:
            seller_id_list = list(unique_seller_ids)
            for i in range(0, len(seller_id_list), 100):
                batch_seller_ids = seller_id_list[i:i+100]
                seller_data_response, _, tokens_consumed, tokens_left = fetch_seller_data(api_key, batch_seller_ids)
                token_manager.update_after_call(tokens_consumed)
                if seller_data_response and 'sellers' in seller_data_response:
                    seller_data_cache.update(seller_data_response['sellers'])
        logger.info(f"Step 2.5 Complete: Fetched data for {len(seller_data_cache)} unique sellers.")

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

            processed_row = _process_single_deal(product_data, seller_data_cache, xai_api_key, business_settings, headers)

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
            logger.info(f"Attempting to connect to database at: {DB_PATH}")
            with sqlite3.connect(DB_PATH) as conn:
                logger.info("Database connection successful.")
                cursor = conn.cursor()
                sanitized_headers = [sanitize_col_name(h) for h in headers]
                
                # Add the two new fields to the headers list for the upsert
                sanitized_headers.extend(['last_seen_utc', 'source'])

                # Prepare the data for upsert, ensuring the new fields are included
                data_for_upsert = []
                for row_dict in rows_to_upsert:
                    row_tuple = tuple(row_dict.get(h) for h in headers) + (row_dict.get('last_seen_utc'), row_dict.get('source'))
                    data_for_upsert.append(row_tuple)

                # Dynamically build the upsert SQL
                cols_str = ', '.join(f'"{h}"' for h in sanitized_headers)
                vals_str = ', '.join(['?'] * len(sanitized_headers))
                update_str = ', '.join(f'"{h}"=excluded."{h}"' for h in sanitized_headers if h != 'ASIN')

                upsert_sql = f"INSERT INTO {TABLE_NAME} ({cols_str}) VALUES ({vals_str}) ON CONFLICT(ASIN) DO UPDATE SET {update_str}"
                
                cursor.executemany(upsert_sql, data_for_upsert)
                logger.info(f"Executing upsert for {cursor.rowcount} rows. Attempting to commit.")
                conn.commit()
                logger.info("Commit successful.")
                logger.info(f"Step 4 Complete: Successfully upserted/updated {cursor.rowcount} rows.")

        except sqlite3.Error as e:
            logger.error(f"Step 4 Failed: Database error during upsert: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Step 4 Failed: Unexpected error during upsert: {e}", exc_info=True)

        logger.info("--- Task: update_recent_deals finished ---")
    finally:
        lock.release()
        logger.info("--- Task: update_recent_deals finished and lock released. ---")
