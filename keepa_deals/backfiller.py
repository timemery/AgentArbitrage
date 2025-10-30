from logging import getLogger
import os
import json
import sqlite3
import time
from datetime import datetime, timezone
from dotenv import load_dotenv
import redis

from worker import celery
from .db_utils import recreate_deals_table, sanitize_col_name, save_watermark
from .keepa_api import fetch_deals_for_deals, fetch_product_batch, validate_asin
from .token_manager import TokenManager
from .field_mappings import FUNCTION_LIST
from .seller_info import get_all_seller_info
from .business_calculations import (
    load_settings as business_load_settings,
    calculate_all_in_cost,
    calculate_profit_and_margin,
    calculate_min_listing_price,
)
from .new_analytics import get_1yr_avg_sale_price, get_percent_discount, get_trend
from .seasonality_classifier import classify_seasonality, get_sells_period
from .processing import _process_single_deal, clean_numeric_values
from .stable_calculations import clear_analysis_cache

# Configure logging
logger = getLogger(__name__)

# Load environment variables
load_dotenv()

# --- Constants ---
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'deals.db')
TABLE_NAME = 'deals'
HEADERS_PATH = os.path.join(os.path.dirname(__file__), 'headers.json')
MAX_ASINS_PER_BATCH = 50
LOCK_KEY = "backfill_deals_lock"
LOCK_TIMEOUT = 60 * 60 * 4 # 4 hours for a full backfill

def _convert_keepa_time_to_iso(keepa_minutes):
    """Converts Keepa time (minutes since 2000-01-01) to ISO 8601 UTC string."""
    keepa_epoch = datetime(2000, 1, 1, tzinfo=timezone.utc)
    dt_object = keepa_epoch + timedelta(minutes=keepa_minutes)
    return dt_object.isoformat()

@celery.task(name='keepa_deals.backfiller.backfill_deals')
def backfill_deals():
    redis_client = redis.Redis.from_url(celery.conf.broker_url)
    lock = redis_client.lock(LOCK_KEY, timeout=LOCK_TIMEOUT)

    if not lock.acquire(blocking=False):
        logger.warning(f"--- Task: backfill_deals is already running. Skipping execution. ---")
        return

    try:
        logger.info("--- Task: backfill_deals started ---")

        # --- CRITICAL FIX: Clear the memoization cache ---
        clear_analysis_cache()

        recreate_deals_table()

        api_key = os.getenv("KEEPA_API_KEY")
        xai_api_key = os.getenv("XAI_TOKEN") # Corrected from XAI_API_KEY
        if not api_key:
            logger.error("KEEPA_API_KEY not set. Aborting.")
            return

        token_manager = TokenManager(api_key)

        # --- TOKEN SYNC FIX ---
        # Authoritatively sync the token count with the Keepa API at the start of the task.
        # This prevents the task from starting with an incorrect, assumed token count.
        token_manager.sync_tokens()

        business_settings = business_load_settings()

        with open(HEADERS_PATH) as f:
            headers = json.load(f)

        all_deals = []
        page = 0
        max_last_update = 0

        # 1. Paginate through all deals
        while True:
            logger.info(f"Fetching page {page} of deals...")
            # --- RATE LIMITING FIX ---
            # Request permission BEFORE making the call to respect rate limits.
            token_manager.request_permission_for_call(estimated_cost=5) # Deals endpoint costs ~5 tokens

            deal_response, tokens_consumed, tokens_left = fetch_deals_for_deals(page, api_key, use_deal_settings=True)

            # --- TOKEN SYNC FIX ---
            # Update the manager with the authoritative 'tokens_left' value from the API response.
            token_manager.update_after_call(tokens_left)

            if not deal_response or 'deals' not in deal_response or not deal_response['deals']['dr']:
                logger.info("No more deals found. Pagination complete.")
                break

            deals_on_page = [d for d in deal_response['deals']['dr'] if validate_asin(d.get('asin'))]
            all_deals.extend(deals_on_page)
            logger.info(f"Found {len(deals_on_page)} deals on page {page}. Total deals so far: {len(all_deals)}")

            # Track the latest update timestamp
            for deal in deals_on_page:
                if deal.get('lastUpdate', 0) > max_last_update:
                    max_last_update = deal['lastUpdate']

            page += 1
            time.sleep(1) # Be nice to the API

        if not all_deals:
            logger.info("No deals found at all. Exiting.")
            return

        logger.info(f"Total deals collected: {len(all_deals)}. Starting product data fetch.")

        # 2. Fetch product data for all collected ASINs
        all_fetched_products = {}
        asin_list = [d['asin'] for d in all_deals]

        for i in range(0, len(asin_list), MAX_ASINS_PER_BATCH):
            batch_asins = asin_list[i:i + MAX_ASINS_PER_BATCH]

            # --- RATE LIMITING FIX ---
            # History and offers are expensive, estimate cost accordingly.
            estimated_cost = 15 * len(batch_asins)
            token_manager.request_permission_for_call(estimated_cost)

            product_response, _, tokens_consumed, tokens_left = fetch_product_batch(api_key, batch_asins, history=1, offers=20)

            # --- TOKEN SYNC FIX ---
            token_manager.update_after_call(tokens_left)

            if product_response and 'products' in product_response:
                all_fetched_products.update({p['asin']: p for p in product_response['products']})
            logger.info(f"Fetched product data for batch {i//MAX_ASINS_PER_BATCH + 1}/{(len(asin_list) + MAX_ASINS_PER_BATCH - 1)//MAX_ASINS_PER_BATCH}")

        # 3. Pre-fetch seller data
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
                batch_ids = seller_id_list[i:i+100]

                # --- RATE LIMITING FIX ---
                token_manager.request_permission_for_call(estimated_cost=len(batch_ids))

                seller_data, _, tokens_consumed, tokens_left = fetch_seller_data(api_key, batch_ids)

                # --- TOKEN SYNC FIX ---
                token_manager.update_after_call(tokens_left)

                if seller_data and 'sellers' in seller_data:
                    seller_data_cache.update(seller_data['sellers'])
        logger.info(f"Fetched data for {len(seller_data_cache)} unique sellers.")


        # 4. Process and save deals to DB
        rows_to_upsert = []
        for deal in all_deals:
            asin = deal['asin']
            if asin not in all_fetched_products:
                continue

            product_data = all_fetched_products[asin]
            product_data.update(deal) # Combine deal info with product info

            processed_row = _process_single_deal(product_data, seller_data_cache, xai_api_key, business_settings, headers)

            if processed_row:
                logger.info(f"Appending processed row for ASIN: {asin}")
                # Clean the numeric values before upserting
                processed_row = clean_numeric_values(processed_row)
                processed_row['last_seen_utc'] = datetime.now(timezone.utc).isoformat()
                processed_row['source'] = 'backfiller'
                rows_to_upsert.append(processed_row)
                logger.info(f"rows_to_upsert now contains {len(rows_to_upsert)} rows.")

        logger.info(f"Processed {len(rows_to_upsert)} deals. Upserting to database.")
        logger.info(f"Checking if rows_to_upsert is empty before database connection. Length is {len(rows_to_upsert)}")
        if rows_to_upsert:
            logger.info(f"Connecting to database at {DB_PATH}")
            conn = sqlite3.connect(DB_PATH, timeout=30)
            try:
                logger.info("Database connection successful. Creating cursor.")
                cursor = conn.cursor()
                sanitized_headers = [sanitize_col_name(h) for h in headers]
                sanitized_headers.extend(['last_seen_utc', 'source'])

                cols_str = ', '.join(f'"{h}"' for h in sanitized_headers)
                vals_str = ', '.join(['?'] * len(sanitized_headers))
                update_str = ', '.join(f'"{h}"=excluded."{h}"' for h in sanitized_headers if h != 'ASIN')
                upsert_sql = f"INSERT INTO {TABLE_NAME} ({cols_str}) VALUES ({vals_str}) ON CONFLICT(ASIN) DO UPDATE SET {update_str}"

                data_tuples = []
                for row in rows_to_upsert:
                    data_tuples.append(tuple(row.get(h) for h in headers) + (row.get('last_seen_utc'), row.get('source')))

                cursor.executemany(upsert_sql, data_tuples)
                conn.commit()
                logger.info(f"Successfully upserted {cursor.rowcount} rows.")
            finally:
                conn.close()

        # 5. Save the watermark
        if max_last_update > 0:
            # Keepa time is minutes since 2000-01-01. Convert to ISO 8601 UTC.
            from datetime import timedelta
            keepa_epoch = datetime(2000, 1, 1, tzinfo=timezone.utc)
            watermark_datetime = keepa_epoch + timedelta(minutes=max_last_update)
            watermark_iso = watermark_datetime.isoformat()
            save_watermark(watermark_iso)

        logger.info("--- Task: backfill_deals finished ---")

    except Exception as e:
        logger.error(f"An unexpected error occurred in backfill_deals task: {e}", exc_info=True)
    finally:
        lock.release()
        logger.info("--- Task: backfill_deals lock released. ---")
