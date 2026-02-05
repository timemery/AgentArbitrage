from logging import getLogger
import os
import json
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import redis

from worker import celery_app as celery
from .db_utils import (
    sanitize_col_name, save_watermark, DB_PATH,
    get_system_state, set_system_state, recreate_deals_table,
    create_deals_table_if_not_exists, recreate_user_restrictions_table,
    get_deal_count
)
from .keepa_api import fetch_deals_for_deals, fetch_product_batch, validate_asin, fetch_seller_data, fetch_current_stats_batch
from .token_manager import TokenManager
from .processing import _process_single_deal, clean_numeric_values, _process_lightweight_update
from .seller_info import get_seller_info_for_single_deal
from .stable_calculations import clear_analysis_cache

# Configure logging
logger = getLogger(__name__)

# Load environment variables
load_dotenv()

# --- Version Identifier ---
BACKFILLER_VERSION = "2.10-Starvation-Fix"

# --- Constants ---
# DB_PATH is imported from db_utils
TABLE_NAME = 'deals'
HEADERS_PATH = os.path.join(os.path.dirname(__file__), 'headers.json')
# DO NOT CHANGE. The optimal chunk size is 20, and is required to allow the Token Bucket sufficient time to refill between requests.
DEALS_PER_CHUNK = 20
LOCK_KEY = "backfill_deals_lock"
LOCK_TIMEOUT = 3600 # 1 hour (Reduced from 10 days to prevent zombie locks)
STATE_FILE_LEGACY = 'backfill_state.json'

def _convert_keepa_time_to_iso(keepa_minutes):
    """Converts Keepa time (minutes since 2011-01-01) to ISO 8601 UTC string."""
    keepa_epoch = datetime(2011, 1, 1, tzinfo=timezone.utc)
    dt_object = keepa_epoch + timedelta(minutes=keepa_minutes)
    return dt_object.isoformat()

def load_backfill_state():
    """
    Loads the last completed page from the system_state table.
    Migrates from legacy JSON file if DB entry is missing.
    """
    # 1. Try loading from DB
    val = get_system_state('backfill_page')
    if val is not None:
        try:
            return int(val)
        except ValueError:
            logger.error(f"Invalid backfill_page in DB: {val}. Defaulting to 0.")
            return 0

    # 2. Migration: Check legacy file
    if os.path.exists(STATE_FILE_LEGACY):
        logger.info("Backfill state missing in DB. Checking legacy file...")
        try:
            with open(STATE_FILE_LEGACY, 'r') as f:
                data = json.load(f)
                page = data.get('last_completed_page', 0)
                logger.info(f"Found legacy backfill state: page {page}. Migrating to DB.")
                save_backfill_state(page)
                return page
        except (json.JSONDecodeError, FileNotFoundError, ValueError) as e:
            logger.error(f"Error loading legacy backfill state: {e}")
            return 0

    return 0

def save_backfill_state(page_number):
    """Saves the last completed page to the system_state table."""
    set_system_state('backfill_page', str(page_number))
    logger.info(f"--- Backfill state saved. Last completed page: {page_number} ---")

@celery.task(name='keepa_deals.backfiller.backfill_deals')
def backfill_deals(reset=False):
    # Ensure tables exist immediately
    create_deals_table_if_not_exists()

    if reset:
        logger.info("Reset requested. Clearing backfill state and database.")
        # Reset DB state to 0
        save_backfill_state(0)

        # Remove legacy file if it exists
        if os.path.exists(STATE_FILE_LEGACY):
            try:
                os.remove(STATE_FILE_LEGACY)
                logger.info(f"Removed legacy state file {STATE_FILE_LEGACY}.")
            except OSError as e:
                logger.warning(f"Could not remove legacy state file: {e}")

        # Recreate table (clears data)
        recreate_deals_table()

        # Also clear user restrictions to ensure fresh checks for new data
        recreate_user_restrictions_table()

        logger.info("Database has been reset (Deals and User Restrictions cleared).")

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
        # STARVATION FIX: Increase threshold for backfiller to prioritize upserter (simple_task)
        # The upserter uses the default threshold of 50. By making the backfiller wait for 80,
        # we create a protected window [50, 80] where the upserter can run without competition,
        # but avoid the 'livelock' where a slow refill rate prevents reaching 150.
        # UPDATE: With 5 tokens/min, 80 is unreachable if upserter runs frequently.
        # Reducing to 50 to prevent starvation.
        # UPDATE 2: 50 is still too high. Reducing to 20 to allow operation in low-refill environments.
        token_manager.MIN_TOKEN_THRESHOLD = 20
        token_manager.sync_tokens()

        page = load_backfill_state()
        logger.info(f"--- Resuming backfill from page {page} ---")

        while True:
            # Check for artificial limit
            if get_system_state('backfill_limit_enabled') == 'true':
                limit_count = int(get_system_state('backfill_limit_count', 3000))
                current_count = get_deal_count()

                if current_count >= limit_count:
                    logger.info(f"--- Artificial backfill limit reached ({current_count} >= {limit_count}). Stopping backfill. ---")
                    # We break the loop, effectively ending the task.
                    break

            logger.info(f"Fetching page {page} of deals...")
            # We pass token_manager to fetch_deals_for_deals to handle the rate limiting internaly
            deal_response, _, tokens_left = fetch_deals_for_deals(page, api_key, use_deal_settings=True, token_manager=token_manager)
            token_manager.update_after_call(tokens_left)

            if not deal_response or 'deals' not in deal_response or not deal_response['deals']['dr']:
                logger.info("No more deals found. Pagination complete.")
                break

            deals_on_page = [d for d in deal_response['deals']['dr'] if validate_asin(d.get('asin'))]
            logger.info(f"Found {len(deals_on_page)} deals on page {page}.")

            # Update watermark if starting fresh (Page 0), so upserter knows where to pick up
            if page == 0 and deals_on_page:
                newest_ts = deals_on_page[0].get('lastUpdate')
                if newest_ts:
                    wm_iso = _convert_keepa_time_to_iso(newest_ts)
                    save_watermark(wm_iso)

            # Dynamic Chunk Sizing for Low-Tier Plans
            # If rate is low, we must upsert frequently (small chunks) to avoid losing data during long waits.
            current_chunk_size = DEALS_PER_CHUNK
            if token_manager.REFILL_RATE_PER_MINUTE < 20:
                current_chunk_size = 1
                logger.info(f"Low refill rate detected. Reducing chunk size to {current_chunk_size} to ensure incremental saves.")

            for i in range(0, len(deals_on_page), current_chunk_size):
                try:
                    chunk_deals = deals_on_page[i:i + current_chunk_size]
                    if not chunk_deals: continue

                    logger.info(f"--- Processing chunk {i//current_chunk_size + 1}/{(len(deals_on_page) + current_chunk_size - 1)//current_chunk_size} on page {page} ---")

                    # --- Hybrid Ingestion Logic: Check DB for existing ASINs ---
                    all_asins = [d['asin'] for d in chunk_deals]
                    existing_asins_set = set()
                    existing_rows_map = {} # Map ASIN to existing row dict

                    try:
                        conn_check = sqlite3.connect(DB_PATH, timeout=60)
                        conn_check.row_factory = sqlite3.Row # Enable dict-like access
                        c_check = conn_check.cursor()
                        placeholders = ','.join('?' * len(all_asins))
                        # We need to fetch ALL columns to preserve them
                        c_check.execute(f"SELECT * FROM {TABLE_NAME} WHERE ASIN IN ({placeholders})", all_asins)
                        rows = c_check.fetchall()
                        for r in rows:
                            asin_val = r['ASIN']
                            existing_asins_set.add(asin_val)
                            existing_rows_map[asin_val] = dict(r) # Convert Row to dict
                        conn_check.close()
                    except Exception as e:
                        logger.warning(f"Failed to check existing ASINs: {e}")

                    new_asins = [a for a in all_asins if a not in existing_asins_set]
                    existing_asins_list = list(existing_asins_set)

                    all_fetched_products = {}

                    # 1. Fetch NEW deals (Heavy: 365 days history, offers=20)
                    # Batching: Split into smaller chunks (2) to avoid requesting >300 tokens at once (Deadlock Fix)
                    # Cost per batch of 2 is ~40 tokens. Target = 80 + 40 = 120 (Safe for 300 bucket).
                    BACKFILL_BATCH_SIZE = 2
                    if token_manager.REFILL_RATE_PER_MINUTE < 20:
                        BACKFILL_BATCH_SIZE = 1  # Reduce to 1 (Cost ~20) to fit within 20-token buffer

                    if new_asins:
                        logger.info(f"Fetching full history for {len(new_asins)} NEW deals (Batched by {BACKFILL_BATCH_SIZE})...")
                        for k in range(0, len(new_asins), BACKFILL_BATCH_SIZE):
                            batch_asins = new_asins[k:k + BACKFILL_BATCH_SIZE]

                            # Request tokens for this specific batch
                            token_manager.request_permission_for_call(20 * len(batch_asins))

                            prod_resp, _, _, t_left = fetch_product_batch(api_key, batch_asins, days=365, history=1, offers=20)
                            if t_left: token_manager.update_after_call(t_left)

                            if prod_resp and 'products' in prod_resp:
                                 all_fetched_products.update({p['asin']: p for p in prod_resp['products']})

                            # Small sleep between API batches to be polite
                            time.sleep(0.5)

                    # 2. Fetch EXISTING deals (Light: stats=180, history=0)
                    if existing_asins_list:
                        logger.info(f"Fetching lightweight stats for {len(existing_asins_list)} EXISTING deals...")
                        # Estimated cost is low (~2 tokens/ASIN) but we don't pass token_manager to func
                        token_manager.request_permission_for_call(2 * len(existing_asins_list))

                        prod_resp_light, _, _, t_left_light = fetch_current_stats_batch(api_key, existing_asins_list, days=180)
                        if t_left_light: token_manager.update_after_call(t_left_light)

                        if prod_resp_light and 'products' in prod_resp_light:
                             # Merge into all_fetched_products. Logic downstream distinguishes how to process.
                             all_fetched_products.update({p['asin']: p for p in prod_resp_light['products']})

                    logger.info(f"Fetched product data for {len(all_fetched_products)} ASINs in chunk.")

                    rows_to_upsert = []
                    for deal in chunk_deals:
                        asin = deal['asin']
                        if asin not in all_fetched_products: continue
                        product_data = all_fetched_products[asin]
                        product_data.update(deal) # Merge deal info (like currentSince)

                        # Determine processing path
                        if asin in existing_asins_set:
                            # Lightweight Update
                            processed_row = _process_lightweight_update(existing_rows_map[asin], product_data)
                            if processed_row:
                                processed_row = clean_numeric_values(processed_row)
                                processed_row['last_seen_utc'] = datetime.now(timezone.utc).isoformat()
                                processed_row['source'] = 'backfiller_light' # Track source
                                rows_to_upsert.append(processed_row)
                        else:
                            # Heavy Process (New Deal)
                            seller_data_cache = get_seller_info_for_single_deal(product_data, api_key, token_manager)
                            processed_row = _process_single_deal(product_data, seller_data_cache, xai_api_key)

                            if processed_row:
                                processed_row = clean_numeric_values(processed_row)
                                processed_row['last_seen_utc'] = datetime.now(timezone.utc).isoformat()
                                processed_row['source'] = 'backfiller'
                                rows_to_upsert.append(processed_row)

                        time.sleep(0.5) # Reduced throttle for hybrid

                    rejection_count = len(chunk_deals) - len(rows_to_upsert)
                    logger.info(f"DEBUG: Chunk stats - Processed: {len(chunk_deals)}, Upserting: {len(rows_to_upsert)}, Rejected: {rejection_count}")

                    if rows_to_upsert:
                        logger.info(f"Upserting {len(rows_to_upsert)} processed deals from chunk into the database.")
                        conn = None
                        try:
                            conn = sqlite3.connect(DB_PATH, timeout=60)
                            cursor = conn.cursor()

                            # --- New Logging Logic: Refreshed vs New ---
                            # We do this check *before* the upsert to see what's already there
                            asin_list_upsert = [row.get('ASIN') for row in rows_to_upsert if row.get('ASIN')]
                            if asin_list_upsert:
                                # Sanitize placeholders
                                placeholders_check = ', '.join(['?'] * len(asin_list_upsert))
                                query_check = f"SELECT ASIN FROM {TABLE_NAME} WHERE ASIN IN ({placeholders_check})"
                                cursor.execute(query_check, asin_list_upsert)
                                existing_asins = {row[0] for row in cursor.fetchall()}

                                count_refreshed = len(existing_asins)
                                count_new = len(asin_list_upsert) - count_refreshed

                                logger.info(f"--- Upsert Stats: {count_new} New Deals, {count_refreshed} Refreshed Deals ---")
                            # -------------------------------------------

                            with open(HEADERS_PATH) as f:
                                headers_data = json.load(f)
                            db_columns = [sanitize_col_name(h) for h in headers_data]
                            db_columns.extend(['last_seen_utc', 'source'])
                            placeholders = ', '.join(['?'] * len(db_columns))
                            # Quote column names to handle special characters and numbers at the start
                            quoted_columns = [f'"{col}"' for col in db_columns]
                            query = f"INSERT OR REPLACE INTO {TABLE_NAME} ({', '.join(quoted_columns)}) VALUES ({placeholders})"
                            data_to_insert = [tuple(row.get(h) for h in headers_data) + (row.get('last_seen_utc'), row.get('source')) for row in rows_to_upsert]
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
                            # Do not raise - just log and continue to next chunk
                        finally:
                            if conn: conn.close()

                    # Throttling to prevent excessive token consumption
                    # Reduced from 60s to 1s because TokenManager now handles rate limiting (5 tokens/sec)
                    # This prevents "lugubrious" processing speeds while remaining safe.
                    time.sleep(1)

                except Exception as e:
                    logger.error(f"Unexpected error processing chunk on page {page}: {e}", exc_info=True)
                    time.sleep(5) # Sleep before retrying or moving on

            save_backfill_state(page)
            page += 1
            time.sleep(1)

        logger.info(f"--- Task: backfill_deals finished. ---")
    except Exception as e:
        logger.error(f"An unexpected error occurred in backfill_deals task: {e}", exc_info=True)
    finally:
        lock.release()
        logger.info("--- Task: backfill_deals lock released. ---")
# Refreshed
