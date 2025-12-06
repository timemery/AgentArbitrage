from logging import getLogger
import os
import json
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import redis

from worker import celery_app as celery
from .db_utils import sanitize_col_name, save_watermark
from .keepa_api import fetch_deals_for_deals, fetch_product_batch, validate_asin, fetch_seller_data
from .token_manager import TokenManager
from .processing import _process_single_deal, clean_numeric_values
from .seller_info import get_seller_info_for_single_deal
from .stable_calculations import clear_analysis_cache

# Configure logging
logger = getLogger(__name__)

# Load environment variables
load_dotenv()

# --- Version Identifier ---
BACKFILLER_VERSION = "2.6-another-fix"

# --- Constants ---
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'deals.db')
TABLE_NAME = 'deals'
HEADERS_PATH = os.path.join(os.path.dirname(__file__), 'headers.json')
STATE_FILE = 'backfill_state.json'
DEALS_PER_CHUNK = 2
LOCK_KEY = "backfill_deals_lock"
LOCK_TIMEOUT = 864000 # 10 days

def load_backfill_state():
    if not os.path.exists(STATE_FILE): return 0
    try:
        with open(STATE_FILE, 'r') as f:
            return json.load(f).get('last_completed_page', 0)
    except (json.JSONDecodeError, FileNotFoundError):
        return 0

def save_backfill_state(page_number):
    with open(STATE_FILE, 'w') as f:
        json.dump({'last_completed_page': page_number}, f)
    logger.info(f"--- Backfill state saved. Last completed page: {page_number} ---")

@celery.task(name='keepa_deals.backfiller.backfill_deals')
def backfill_deals(reset=False):
    if reset:
        if os.path.exists(STATE_FILE):
            os.remove(STATE_FILE)
            logger.info(f"Removed state file {STATE_FILE} for a fresh start.")
        from .db_utils import recreate_deals_table
        recreate_deals_table()
        logger.info("Database has been reset.")

    redis_client = redis.Redis.from_url(celery.conf.broker_url)
    lock = redis_client.lock(LOCK_KEY, timeout=LOCK_TIMEOUT)
    if not lock.acquire(blocking=False):
        logger.warning(f"--- Task: backfill_deals is already running. Skipping execution. ---")
        return

    try:
        logger.info("--- Task: backfill_deals started ---")
        clear_analysis_cache()

        api_key = os.getenv("KEEPA_API_KEY")
        xai_api_key = os.getenv("XAI_TOKEN")
        if not api_key:
            logger.error("KEEPA_API_KEY not set. Aborting.")
            return

        token_manager = TokenManager(api_key)
        token_manager.sync_tokens()

        page = load_backfill_state()
        logger.info(f"--- Resuming backfill from page {page} ---")

        while True:
            logger.info(f"Fetching page {page} of deals...")
            token_manager.request_permission_for_call(estimated_cost=5)
            deal_response, _, tokens_left = fetch_deals_for_deals(page, api_key, use_deal_settings=True)
            token_manager.update_after_call(tokens_left)

            if not deal_response or 'deals' not in deal_response or not deal_response['deals']['dr']:
                logger.info("No more deals found. Pagination complete.")
                break

            deals_on_page = [d for d in deal_response['deals']['dr'] if validate_asin(d.get('asin'))]
            logger.info(f"Found {len(deals_on_page)} deals on page {page}.")

            for i in range(0, len(deals_on_page), DEALS_PER_CHUNK):
                chunk_deals = deals_on_page[i:i + DEALS_PER_CHUNK]
                if not chunk_deals: continue

                logger.info(f"--- Processing chunk {i//DEALS_PER_CHUNK + 1}/{(len(deals_on_page) + DEALS_PER_CHUNK - 1)//DEALS_PER_CHUNK} on page {page} ---")

                asin_list = [d['asin'] for d in chunk_deals]
                estimated_cost = 12 * len(asin_list)
                token_manager.request_permission_for_call(estimated_cost)

                product_response, _, _, tokens_left = fetch_product_batch(api_key, asin_list, history=1, offers=20)
                token_manager.update_after_call(tokens_left)

                all_fetched_products = {}
                if product_response and 'products' in product_response:
                    all_fetched_products.update({p['asin']: p for p in product_response['products']})
                logger.info(f"Fetched product data for {len(all_fetched_products)} ASINs in chunk.")

                rows_to_upsert = []
                for deal in chunk_deals:
                    asin = deal['asin']
                    if asin not in all_fetched_products: continue
                    product_data = all_fetched_products[asin]
                    product_data.update(deal)

                    # --- OPTIMIZATION ---
                    # Fetch seller data for ONLY the lowest-priced 'Used' offer.
                    seller_data_cache = get_seller_info_for_single_deal(product_data, api_key, token_manager)
                    # --- END OPTIMIZATION ---

                    processed_row = _process_single_deal(product_data, seller_data_cache, xai_api_key)

                    if processed_row:
                        processed_row = clean_numeric_values(processed_row)
                        processed_row['last_seen_utc'] = datetime.now(timezone.utc).isoformat()
                        processed_row['source'] = 'backfiller'
                        rows_to_upsert.append(processed_row)
                    time.sleep(1)

                if rows_to_upsert:
                    logger.info(f"Upserting {len(rows_to_upsert)} processed deals from chunk into the database.")
                    conn = None
                    try:
                        conn = sqlite3.connect(DB_PATH)
                        cursor = conn.cursor()
                        with open(HEADERS_PATH) as f:
                            headers_data = json.load(f)
                        db_columns = [sanitize_col_name(h) for h in headers_data]
                        db_columns.extend(['last_seen_utc', 'source'])
                        placeholders = ', '.join(['?'] * len(db_columns))
                        # Quote column names to handle special characters and numbers at the start
                        quoted_columns = [f'"{col}"' for col in db_columns]
                        query = f"INSERT OR REPLACE INTO {TABLE_NAME} ({', '.join(quoted_columns)}) VALUES ({placeholders})"
                        data_to_insert = [tuple(row.get(col) for col in db_columns) for row in rows_to_upsert]
                        cursor.executemany(query, data_to_insert)
                        conn.commit()
                        logger.info(f"Successfully upserted {len(rows_to_upsert)} deals.")

                        from worker import celery_app
                        new_asins = [d['ASIN'] for d in rows_to_upsert if 'ASIN' in d]
                        if new_asins:
                            celery_app.send_task('keepa_deals.sp_api_tasks.check_restriction_for_asins', args=[new_asins])
                        celery_app.send_task('keepa_deals.simple_task.update_recent_deals')
                        logger.info(f"--- Triggered downstream tasks for {len(new_asins)} ASINs. ---")
                    except sqlite3.Error as e:
                        logger.error(f"Database error while upserting deals: {e}", exc_info=True)
                        raise
                    finally:
                        if conn: conn.close()

            save_backfill_state(page)
            page += 1
            time.sleep(1)

        logger.info(f"--- Task: backfill_deals finished. ---")
    except Exception as e:
        logger.error(f"An unexpected error occurred in backfill_deals task: {e}", exc_info=True)
    finally:
        lock.release()
        logger.info("--- Task: backfill_deals lock released. ---")
