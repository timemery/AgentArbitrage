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
from .keepa_api import fetch_deals_for_deals, fetch_product_batch, validate_asin
from .token_manager import TokenManager
from .seller_info import get_all_seller_info
from .business_calculations import (
    load_settings as business_load_settings,
)
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
STATE_FILE = 'backfill_state.json'
# This batch size is a critical performance and stability parameter.
# It is set to a conservative value (20) to ensure that the estimated cost of a single
# batch API call (~15 tokens/ASIN * 20 ASINs = ~300 tokens) remains close to or
# slightly above the maximum token bucket size (300). This allows the TokenManager's
# "controlled deficit" strategy to function effectively, preventing excessive negative
# token balances and minimizing long wait times for token refills.
MAX_ASINS_PER_BATCH = 5
LOCK_KEY = "backfill_deals_lock"
LOCK_TIMEOUT = 864000 # 10 days, to prevent expiration during very long runs

def load_backfill_state():
    """Loads the last completed page number from the state file."""
    if not os.path.exists(STATE_FILE):
        return 0
    try:
        with open(STATE_FILE, 'r') as f:
            state = json.load(f)
            return state.get('last_completed_page', 0)
    except (json.JSONDecodeError, FileNotFoundError):
        return 0

def save_backfill_state(page_number):
    """Saves the last completed page number to the state file."""
    with open(STATE_FILE, 'w') as f:
        json.dump({'last_completed_page': page_number}, f)
    logger.info(f"--- Backfill state saved. Last completed page: {page_number} ---")

def _process_and_save_deal_page(deals_on_page, api_key, xai_api_key, token_manager, business_settings, headers):
    """
    Processes a single page of deals and saves them to the database.
    This function encapsulates the fetch-process-save logic for a chunk of deals.
    """
    if not deals_on_page:
        logger.info("No deals on this page to process.")
        return

    logger.info(f"--- Starting processing for a page with {len(deals_on_page)} deals. ---")

    # 2. Fetch product data for all collected ASINs on the page
    all_fetched_products = {}
    asin_list = [d['asin'] for d in deals_on_page]

    for i in range(0, len(asin_list), MAX_ASINS_PER_BATCH):
        batch_asins = asin_list[i:i + MAX_ASINS_PER_BATCH]
        # --- Token Cost Estimation ---
        # This is a critical tuning parameter. Do not change it without careful analysis.
        #
        # - Maximum Theoretical Cost: The API call uses `offers=20`, which requires 2 "offer pages".
        #   The documentation states a cost of 6 tokens per page, so the max cost per ASIN is 12.
        #
        # - Observed Average Cost: Analysis of live logs shows the real-world average cost
        #   is consistently between 7 and 10 tokens per ASIN.
        #
        # - The Multiplier (8): We use 8 as a safe, data-driven average. It is high enough
        #   to be conservative but low enough to prevent the TokenManager from constantly
        #   triggering long, unnecessary pauses when the token balance is moderately low.
        estimated_cost = 8 * len(batch_asins)
        token_manager.request_permission_for_call(estimated_cost)
        product_response, _, tokens_consumed, tokens_left = fetch_product_batch(api_key, batch_asins, history=1, offers=20)
        token_manager.update_after_call(tokens_left)
        if product_response and 'products' in product_response:
            all_fetched_products.update({p['asin']: p for p in product_response['products']})
        logger.info(f"Fetched product data for sub-batch {i//MAX_ASINS_PER_BATCH + 1}/{(len(asin_list) + MAX_ASINS_PER_BATCH - 1)//MAX_ASINS_PER_BATCH}")

    # 3. Pre-fetch seller data for the page
    unique_seller_ids = set()
    for product in all_fetched_products.values():
        for offer in product.get('offers', []):
            if isinstance(offer, dict) and offer.get('sellerId'):
                unique_seller_ids.add(offer['sellerId'])

    from .keepa_api import fetch_seller_data
    seller_data_cache = {}
    if unique_seller_ids:
        seller_id_list = list(unique_seller_ids)
        for i in range(0, len(seller_id_list), 100):
            batch_ids = seller_id_list[i:i+100]
            while True:
                logger.info(f"Attempting to fetch seller data for {len(batch_ids)} seller IDs.")
                token_manager.request_permission_for_call(estimated_cost=1)
                seller_data, _, tokens_consumed, tokens_left = fetch_seller_data(api_key, batch_ids)
                token_manager.update_after_call(tokens_left)

                if seller_data and 'sellers' in seller_data and seller_data['sellers']:
                    seller_data_cache.update(seller_data['sellers'])
                    logger.info(f"Successfully fetched seller data for batch. Cache size now: {len(seller_data_cache)}")
                    break
                else:
                    logger.warning(f"Failed to fetch a batch of seller data or seller data was empty. Tokens left: {tokens_left}. Retrying in 15 seconds.")
                    time.sleep(15)
    logger.info(f"Fetched data for {len(seller_data_cache)} unique sellers for this page.")

    # 4. Process deals for the page
    rows_to_upsert = []
    for deal in deals_on_page:
        asin = deal['asin']
        if asin not in all_fetched_products:
            continue
        product_data = all_fetched_products[asin]
        product_data.update(deal)
        processed_row = _process_single_deal(product_data, seller_data_cache, xai_api_key, business_settings, headers)
        if processed_row:
            processed_row = clean_numeric_values(processed_row)
            processed_row['last_seen_utc'] = datetime.now(timezone.utc).isoformat()
            processed_row['source'] = 'backfiller'
            rows_to_upsert.append(processed_row)

    # 5. Save processed deals directly to the database
    if rows_to_upsert:
        logger.info(f"Upserting {len(rows_to_upsert)} processed deals into the database.")
        conn = None
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            with open(HEADERS_PATH) as f:
                headers_data = json.load(f)

            db_columns = [sanitize_col_name(h['header']) for h in headers_data]
            if 'last_seen_utc' not in db_columns:
                db_columns.append('last_seen_utc')
            if 'source' not in db_columns:
                db_columns.append('source')

            placeholders = ', '.join(['?'] * len(db_columns))
            query = f"INSERT OR REPLACE INTO {TABLE_NAME} ({', '.join(db_columns)}) VALUES ({placeholders})"

            data_to_insert = []
            for row in rows_to_upsert:
                ordered_row = tuple(row.get(col) for col in db_columns)
                data_to_insert.append(ordered_row)

            cursor.executemany(query, data_to_insert)
            conn.commit()
            logger.info(f"Successfully upserted {len(rows_to_upsert)} deals.")

            # After a successful chunk save, trigger the restriction check for the new ASINs.
            new_asins = [row['ASIN'] for row in rows_to_upsert if 'ASIN' in row]
            if new_asins:
                from worker import celery_app
                celery_app.send_task('keepa_deals.sp_api_tasks.check_restriction_for_asins', args=[new_asins])
                logger.info(f"--- Triggered restriction check for {len(new_asins)} new ASINs. ---")

            # After a successful chunk save, trigger the refiller task.
            from worker import celery_app
            celery_app.send_task('keepa_deals.simple_task.update_recent_deals')
            logger.info("--- Triggered update_recent_deals task to sync recent changes. ---")

        except sqlite3.Error as e:
            logger.error(f"Database error while upserting deals: {e}", exc_info=True)
            raise
        finally:
            if conn:
                conn.close()


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
        business_settings = business_load_settings()

        with open(HEADERS_PATH) as f:
            headers = json.load(f)

        page = load_backfill_state()
        logger.info(f"--- Resuming backfill from page {page} ---")

        max_last_update = 0
        total_deals_processed_this_run = 0

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

            _process_and_save_deal_page(deals_on_page, api_key, xai_api_key, token_manager, business_settings, headers)

            save_backfill_state(page)

            total_deals_processed_this_run += len(deals_on_page)

            for deal in deals_on_page:
                if deal.get('lastUpdate', 0) > max_last_update:
                    max_last_update = deal['lastUpdate']

            page += 1
            time.sleep(1)

        if total_deals_processed_this_run > 0 and max_last_update > 0:
            keepa_epoch = datetime(2000, 1, 1, tzinfo=timezone.utc)
            watermark_datetime = keepa_epoch + timedelta(minutes=max_last_update)
            watermark_iso = watermark_datetime.isoformat()
            save_watermark(watermark_iso)
            logger.info(f"Final watermark set to {watermark_iso} based on the newest deal processed.")

        logger.info(f"--- Task: backfill_deals finished. Processed {total_deals_processed_this_run} deals in this run. ---")

    except Exception as e:
        logger.error(f"An unexpected error occurred in backfill_deals task: {e}", exc_info=True)
    finally:
        lock.release()
        logger.info("--- Task: backfill_deals lock released. ---")
