from logging import getLogger
import os
import json
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import redis

from worker import celery
from .db_utils import create_deals_table_if_not_exists, sanitize_col_name, load_watermark, save_watermark
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


def _convert_keepa_time_to_iso(keepa_minutes):
    """Converts Keepa time (minutes since 2000-01-01) to ISO 8601 UTC string."""
    keepa_epoch = datetime(2000, 1, 1, tzinfo=timezone.utc)
    dt_object = keepa_epoch + timedelta(minutes=keepa_minutes)
    return dt_object.isoformat()

def _convert_iso_to_keepa_time(iso_str):
    """Converts an ISO 8601 UTC string to Keepa time (minutes since 2000-01-01)."""
    if not iso_str:
        return 0
    dt_object = datetime.fromisoformat(iso_str).astimezone(timezone.utc)
    keepa_epoch = datetime(2000, 1, 1, tzinfo=timezone.utc)
    delta = dt_object - keepa_epoch
    return int(delta.total_seconds() / 60)


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
        xai_api_key = os.getenv("XAI_TOKEN") # Corrected from XAI_API_KEY
        if not api_key:
            logger.error("KEEPA_API_KEY not set. Aborting.")
            return

        token_manager = TokenManager(api_key)
        business_settings = business_load_settings()

        # --- New Delta Sync Logic ---
        logger.info("Step 1: Initializing Delta Sync...")

        # CRITICAL FIX: Add token check before any API calls
        if not token_manager.has_enough_tokens(5): # 5 tokens is the cost of a single deal page
            logger.warning("Upserter: Insufficient tokens to check for new deals. Skipping run.")
            return

        watermark_iso = load_watermark()
        if watermark_iso is None:
            logger.error("CRITICAL: Watermark not found. The backfiller must be run at least once before the upserter. Aborting.")
            return

        watermark_keepa_time = _convert_iso_to_keepa_time(watermark_iso)
        logger.info(f"Loaded watermark: {watermark_iso} (Keepa time: {watermark_keepa_time})")

        newest_deal_timestamp = 0
        all_new_deals = []
        page = 0
        
        logger.info("Step 2: Paginating through deals to find new ones...")
        while True:
            # Sort by newest first (sortType=0)
            deal_response, tokens_consumed, tokens_left = fetch_deals_for_deals(page, api_key, sort_type=0)
            token_manager.update_after_call(tokens_left)

            if not deal_response or 'deals' not in deal_response or not deal_response['deals']['dr']:
                logger.info("No more deals found on subsequent pages. Stopping pagination.")
                break

            deals_on_page = [d for d in deal_response['deals']['dr'] if validate_asin(d.get('asin'))]

            if page == 0 and deals_on_page:
                # The very first deal on the first page is the newest overall
                newest_deal_timestamp = deals_on_page[0].get('lastUpdate', 0)

            # Core Delta Logic
            found_older_deal = False
            for deal in deals_on_page:
                if deal['lastUpdate'] <= watermark_keepa_time:
                    found_older_deal = True
                    break # Stop processing deals on this page
                all_new_deals.append(deal)

            if found_older_deal:
                logger.info(f"Found a deal older than the watermark on page {page}. Stopping pagination.")
                break

            page += 1
            time.sleep(1) # Be courteous to the API

        if not all_new_deals:
            logger.info("Step 2 Complete: No new deals found since the last run.")
            return
        logger.info(f"Step 2 Complete: Found {len(all_new_deals)} new deals.")

        logger.info("Step 3: Fetching product data for new deals...")
        all_fetched_products = {}
        asin_list = [d['asin'] for d in all_new_deals]

        for i in range(0, len(asin_list), MAX_ASINS_PER_BATCH):
            batch_asins = asin_list[i:i + MAX_ASINS_PER_BATCH]
            product_response, api_info, tokens_consumed, tokens_left = fetch_product_batch(
                api_key, batch_asins, history=1, offers=20
            )
            token_manager.update_after_call(tokens_left)

            if product_response and 'products' in product_response and not (api_info and api_info.get('error_status_code')):
                for p in product_response['products']:
                    all_fetched_products[p['asin']] = p
        logger.info(f"Step 3 Complete: Fetched product data for {len(all_fetched_products)} ASINs.")

        logger.info("Step 4: Pre-fetching all seller data...")
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
                token_manager.update_after_call(tokens_left)
                if seller_data_response and 'sellers' in seller_data_response:
                    seller_data_cache.update(seller_data_response['sellers'])
        logger.info(f"Step 4 Complete: Fetched data for {len(seller_data_cache)} unique sellers.")

        logger.info("Step 5: Processing deals...")
        with open(HEADERS_PATH) as f:
            headers = json.load(f)

        rows_to_upsert = []
        for deal in all_new_deals:
            asin = deal['asin']
            if asin not in all_fetched_products:
                continue

            product_data = all_fetched_products[asin]
            product_data.update(deal)

            processed_row = _process_single_deal(product_data, seller_data_cache, xai_api_key, business_settings, headers)

            if processed_row:
                processed_row = clean_numeric_values(processed_row)
                processed_row['last_seen_utc'] = datetime.now(timezone.utc).isoformat()
                processed_row['source'] = 'upserter'
                rows_to_upsert.append(processed_row)
        logger.info(f"Step 5 Complete: Processed {len(rows_to_upsert)} deals.")

        if not rows_to_upsert:
            logger.info("No rows to upsert. Task finished.")
            return

        logger.info(f"Step 6: Upserting {len(rows_to_upsert)} rows into database...")
        try:
            with sqlite3.connect(DB_PATH) as conn:
                cursor = conn.cursor()
                sanitized_headers = [sanitize_col_name(h) for h in headers]
                sanitized_headers.extend(['last_seen_utc', 'source'])

                data_for_upsert = []
                for row_dict in rows_to_upsert:
                    row_tuple = tuple(row_dict.get(h) for h in headers) + (row_dict.get('last_seen_utc'), row_dict.get('source'))
                    data_for_upsert.append(row_tuple)

                cols_str = ', '.join(f'"{h}"' for h in sanitized_headers)
                vals_str = ', '.join(['?'] * len(sanitized_headers))
                update_str = ', '.join(f'"{h}"=excluded."{h}"' for h in sanitized_headers if h != 'ASIN')
                upsert_sql = f"INSERT INTO {TABLE_NAME} ({cols_str}) VALUES ({vals_str}) ON CONFLICT(ASIN) DO UPDATE SET {update_str}"
                
                cursor.executemany(upsert_sql, data_for_upsert)
                conn.commit()
                logger.info(f"Step 6 Complete: Successfully upserted/updated {cursor.rowcount} rows.")

        except sqlite3.Error as e:
            logger.error(f"Step 6 Failed: Database error during upsert: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Step 6 Failed: Unexpected error during upsert: {e}", exc_info=True)

        # --- Final Step: Update Watermark ---
        if newest_deal_timestamp > watermark_keepa_time:
            new_watermark_iso = _convert_keepa_time_to_iso(newest_deal_timestamp)
            save_watermark(new_watermark_iso)
            logger.info(f"Successfully updated watermark to {new_watermark_iso}")

        logger.info("--- Task: update_recent_deals finished ---")
    finally:
        lock.release()
        logger.info("--- Task: update_recent_deals finished and lock released. ---")
