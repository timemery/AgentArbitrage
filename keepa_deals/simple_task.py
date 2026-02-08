from logging import getLogger
import os
import json
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
import redis

from worker import celery_app as celery
from .db_utils import create_deals_table_if_not_exists, sanitize_col_name, load_watermark, save_watermark, DB_PATH
from .keepa_api import fetch_deals_for_deals, fetch_product_batch, validate_asin, fetch_current_stats_batch
from .token_manager import TokenManager
from .field_mappings import FUNCTION_LIST
from .seller_info import get_seller_info_for_single_deal
from .business_calculations import (
    load_settings as business_load_settings,
    calculate_all_in_cost,
    calculate_profit_and_margin,
    calculate_min_listing_price,
)
from .new_analytics import get_1yr_avg_sale_price, get_percent_discount, get_trend
from .seasonality_classifier import classify_seasonality, get_sells_period
from .processing import _process_single_deal, clean_numeric_values, _process_lightweight_update

# Configure logging
logger = getLogger(__name__)

# Version Check: Load Shedding & Smart Reset Implemented
# Load environment variables
load_dotenv()

# --- Version Identifier ---
SIMPLE_TASK_VERSION = "2.12-Priority-Fix"

# --- Constants ---
# DB_PATH is imported from db_utils
TABLE_NAME = 'deals'
HEADERS_PATH = os.path.join(os.path.dirname(__file__), 'headers.json')
# REGRESSION WARNING: Do not increase MAX_ASINS_PER_BATCH above 5 without careful testing.
# A batch of 10 costs ~200 tokens. If the Backfiller is running with a target of 180,
# the Upserter (Target 250) will be starved.
# Reducing batch to 5 (Cost ~100) lowers the Target to ~150.
# UPDATE: With Backfiller Target reduced to 90 (Threshold 50 + Cost 40), we must reduce Upserter
# batch to 2 (Cost ~40 -> Target 90) to prevent Backfiller from starving Upserter.
MAX_ASINS_PER_BATCH = 2
LOCK_KEY = "update_recent_deals_lock"
LOCK_TIMEOUT = 60 * 30  # 30 minutes
MAX_PAGES_PER_RUN = 50 # Safety limit to prevent runaway pagination
MAX_NEW_DEALS_PER_RUN = 200 # Safety limit: If we find > 200 new deals, stop fetching and process what we have to allow catch-up.

def _convert_keepa_time_to_iso(keepa_minutes):
    """Converts Keepa time (minutes since 2011-01-01) to ISO 8601 UTC string."""
    keepa_epoch = datetime(2011, 1, 1, tzinfo=timezone.utc)
    dt_object = keepa_epoch + timedelta(minutes=keepa_minutes)
    return dt_object.isoformat()

def _convert_iso_to_keepa_time(iso_str):
    """Converts an ISO 8601 UTC string to Keepa time (minutes since 2011-01-01)."""
    if not iso_str:
        return 0
    dt_object = datetime.fromisoformat(iso_str).astimezone(timezone.utc)
    keepa_epoch = datetime(2011, 1, 1, tzinfo=timezone.utc)
    delta = dt_object - keepa_epoch
    return int(delta.total_seconds() / 60)


@celery.task(name='keepa_deals.simple_task.update_recent_deals')
def update_recent_deals():
    redis_client = redis.Redis.from_url(celery.conf.broker_url)

    # --- Backfiller Lock Check ---
    # Optimization: We NO LONGER skip if backfiller is running.
    # We want the 'Refiller' (simple_task) to be high priority.
    # The TokenManager handles the shared resource (tokens), so concurrency is safe.
    # If tokens are low, both will block, which is fine.
    # backfill_lock = redis_client.lock("backfill_deals_lock")
    # if backfill_lock.locked():
    #     logger.warning("Backfill task is running. Skipping update_recent_deals to prevent interference.")
    #     return

    lock = redis_client.lock(LOCK_KEY, timeout=LOCK_TIMEOUT)
    logger.info(f"DEBUG: Attempting to acquire lock {LOCK_KEY}...")
    if not lock.acquire(blocking=False):
        logger.info("--- Task: update_recent_deals is already running. Skipping execution. ---")
        return

    try:
        logger.info(f"--- Task: update_recent_deals started (Version: {SIMPLE_TASK_VERSION}) ---")
        logger.info(f"DEBUG: Lock acquired. Requesting tokens...")
        logger.info(f"Import Source: fetch_deals_for_deals is imported from {fetch_deals_for_deals.__module__}")
        create_deals_table_if_not_exists()

        api_key = os.getenv("KEEPA_API_KEY")
        xai_api_key = os.getenv("XAI_TOKEN") # Corrected from XAI_API_KEY
        if not api_key:
            logger.error("KEEPA_API_KEY not set. Aborting.")
            return

        token_manager = TokenManager(api_key)
        # Force an API sync to get the true token balance (avoids "double dipping" with backfiller)
        token_manager.sync_tokens()

        business_settings = business_load_settings()

        # --- New Delta Sync Logic ---
        logger.info("Step 1: Initializing Delta Sync...")

        # CRITICAL FIX: Add token check before any API calls
        # We use a blocking wait here instead of a simple check.
        # Previously, this returned early if tokens were low, causing "starvation" when the Backfiller
        # was running (which keeps tokens low). Now, we force the Upserter to wait in line.
        logger.info(f"DEBUG: Calling request_permission_for_call(5). Current tokens: {token_manager.tokens}")
        token_manager.request_permission_for_call(5)
        logger.info("DEBUG: Permission granted for Upserter.")

        watermark_iso = load_watermark()
        if watermark_iso is None:
            logger.error("CRITICAL: Watermark not found. The backfiller must be run at least once before the upserter. Aborting.")
            return

        watermark_keepa_time = _convert_iso_to_keepa_time(watermark_iso)
        logger.info(f"Loaded watermark: {watermark_iso} (Keepa time: {watermark_keepa_time})")

        newest_deal_timestamp = 0
        all_new_deals = []
        page = 0
        incomplete_run = False
        hit_new_deal_limit = False
        
        logger.info("Step 2: Paginating through deals to find new ones...")
        while True:
            # --- LOOP SAFETY CHECKS ---
            if page >= MAX_PAGES_PER_RUN:
                logger.warning(f"Safety Limit Reached: Stopped pagination after {MAX_PAGES_PER_RUN} pages to prevent runaway task.")
                break

            if len(all_new_deals) >= MAX_NEW_DEALS_PER_RUN:
                logger.warning(f"New Deal Limit Reached: Found {len(all_new_deals)} new deals. Stopping fetch to process current batch and update watermark.")
                hit_new_deal_limit = True
                break

            # WAITING LOGIC FIX: Instead of aborting, wait for tokens.
            # if not token_manager.has_enough_tokens(5):
            #     logger.warning(f"Low tokens during pagination ({token_manager.tokens}). Stopping fetch loop.")
            #     incomplete_run = True
            #     break
            token_manager.request_permission_for_call(5)
            # --------------------------

            # Sort by newest first (sortType=4: Last Update)
            SORT_TYPE_LAST_UPDATE = 4
            logger.info(f"Fetching deals using Sort Type: {SORT_TYPE_LAST_UPDATE} (Last Update). Page: {page}")
            deal_response = None
            max_page_retries = 3

            # Retry loop for robustness against 429s/Network blips
            for attempt in range(max_page_retries):
                try:
                    deal_response, tokens_consumed, tokens_left = fetch_deals_for_deals(page, api_key, sort_type=SORT_TYPE_LAST_UPDATE, token_manager=token_manager)
                    if tokens_left is not None:
                        token_manager.update_after_call(tokens_left)

                    if deal_response and 'deals' in deal_response:
                        break # Success
                except Exception as e:
                    logger.warning(f"Fetch failed on page {page} (Attempt {attempt+1}/{max_page_retries}): {e}")
                    # If we failed (likely 429), wait a bit before retrying
                    time.sleep(15 * (attempt + 1))

            if not deal_response or 'deals' not in deal_response:
                if page == 0:
                    logger.error("Failed to fetch Page 0 after retries. Aborting task to prevent partial state.")
                    return
                else:
                    logger.info("Failed to fetch subsequent page. Stopping pagination.")
                    break

            if not deal_response['deals']['dr']:
                logger.info("No more deals found (empty list). Stopping pagination.")
                break

            deals_on_page = [d for d in deal_response['deals']['dr'] if validate_asin(d.get('asin'))]

            if page == 0 and deals_on_page:
                # The very first deal on the first page is the newest overall
                newest_deal_timestamp = deals_on_page[0].get('lastUpdate', 0)

                # --- SANITY CHECK FOR SORT ORDER ---
                # Check if the "newest" deal is surprisingly old.
                # Keepa timestamps are minutes since 2011-01-01.
                current_time_keepa = _convert_iso_to_keepa_time(datetime.now(timezone.utc).isoformat())
                age_minutes = current_time_keepa - newest_deal_timestamp
                # 24 hours = 1440 minutes.
                if age_minutes > 1440:
                    logger.warning(f"SORT ORDER WARNING: The top deal on Page 0 is {age_minutes/60:.1f} hours old. "
                                   f"If you expect live updates, this indicates Sort Type 4 (Last Update) might be failing "
                                   f"or reverting to Sales Rank (Sort 0). Requested Sort Type: {SORT_TYPE_LAST_UPDATE}.")
                # -----------------------------------

            # Core Delta Logic
            found_older_deal = False
            for deal in deals_on_page:
                if deal['lastUpdate'] <= watermark_keepa_time:
                    # Detailed logging to help diagnose why ingestion stops
                    logger.info(f"Stop Trigger: Deal {deal.get('asin')} (Update: {deal['lastUpdate']}) <= Watermark ({watermark_keepa_time}). Diff: {watermark_keepa_time - deal['lastUpdate']} min.")
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

        # --- Check Existing ASINs ---
        existing_asins_set = set()
        existing_rows_map = {}
        try:
            conn_check = sqlite3.connect(DB_PATH, timeout=60)
            conn_check.row_factory = sqlite3.Row
            c_check = conn_check.cursor()
            placeholders = ','.join('?' * len(asin_list))
            c_check.execute(f"SELECT * FROM {TABLE_NAME} WHERE ASIN IN ({placeholders})", asin_list)
            rows = c_check.fetchall()
            for r in rows:
                existing_asins_set.add(r['ASIN'])
                existing_rows_map[r['ASIN']] = dict(r)
            conn_check.close()
        except Exception as e:
            logger.warning(f"Failed to check existing ASINs in simple_task: {e}")
        # ----------------------------

        # Split batches into New vs Existing
        # NO: We must iterate chunks to support incremental upsert

        # Determine dynamic batch size for low refill rates
        current_batch_size = MAX_ASINS_PER_BATCH
        if token_manager.REFILL_RATE_PER_MINUTE < 20:
            current_batch_size = 1

        logger.info("Step 3 & 4 & 6: Fetching, Processing, and Upserting deals incrementally...")
        with open(HEADERS_PATH) as f:
            headers = json.load(f)

        total_upserted = 0

        # We iterate over `all_new_deals` in chunks (using current_batch_size)
        # For each chunk, we Fetch -> Process -> Upsert
        for i in range(0, len(all_new_deals), current_batch_size):
            chunk_deals = all_new_deals[i:i + current_batch_size]

            # 1. Fetch
            chunk_asins = [d['asin'] for d in chunk_deals]
            chunk_new_asins = [a for a in chunk_asins if a not in existing_asins_set]
            chunk_existing_asins = [a for a in chunk_asins if a in existing_asins_set]

            chunk_products = {}

            # A. Heavy Fetch
            if chunk_new_asins:
                token_manager.request_permission_for_call(20 * len(chunk_new_asins))
                product_response, _, _, tokens_left = fetch_product_batch(
                    api_key, chunk_new_asins, days=1095, history=1, offers=20
                )
                if tokens_left: token_manager.update_after_call(tokens_left)
                if product_response and 'products' in product_response:
                    for p in product_response['products']:
                        chunk_products[p['asin']] = p

            # B. Light Fetch
            if chunk_existing_asins:
                 token_manager.request_permission_for_call(2 * len(chunk_existing_asins))
                 product_response, _, _, tokens_left = fetch_current_stats_batch(
                     api_key, chunk_existing_asins, days=180
                 )
                 if tokens_left: token_manager.update_after_call(tokens_left)
                 if product_response and 'products' in product_response:
                    for p in product_response['products']:
                        chunk_products[p['asin']] = p

            # 2. Process
            rows_to_upsert = []
            for deal in chunk_deals:
                asin = deal['asin']
                if asin not in chunk_products: continue

                product_data = chunk_products[asin]
                product_data.update(deal)

                processed_row = None
                if asin in existing_asins_set:
                     # Lightweight Update
                     processed_row = _process_lightweight_update(existing_rows_map[asin], product_data)
                     if processed_row:
                         processed_row = clean_numeric_values(processed_row)
                         processed_row['last_seen_utc'] = datetime.now(timezone.utc).isoformat()
                         processed_row['source'] = 'upserter_light'
                else:
                     # Heavy Process (New Deal)
                     seller_data_cache = get_seller_info_for_single_deal(product_data, api_key, token_manager)
                     processed_row = _process_single_deal(product_data, seller_data_cache, xai_api_key)
                     if processed_row:
                         processed_row = clean_numeric_values(processed_row)
                         processed_row['last_seen_utc'] = datetime.now(timezone.utc).isoformat()
                         processed_row['source'] = 'upserter'

                if processed_row:
                    rows_to_upsert.append(processed_row)

            # 3. Upsert
            if not rows_to_upsert:
                continue

            try:
                with sqlite3.connect(DB_PATH, timeout=60) as conn:
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
                    total_upserted += len(rows_to_upsert)
                    logger.info(f"Chunk upsert success: {len(rows_to_upsert)} deals.")

                    # Trigger restriction check
                    new_asins = [row['ASIN'] for row in rows_to_upsert if 'ASIN' in row]
                    if new_asins:
                        celery.send_task('keepa_deals.sp_api_tasks.check_restriction_for_asins', args=[new_asins])

            except sqlite3.Error as e:
                logger.error(f"Chunk upsert failed: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"Chunk processing failed: {e}", exc_info=True)

        logger.info(f"Task Complete: Processed and upserted {total_upserted} deals total.")

        # --- Final Step: Update Watermark ---
        # Only update watermark if we actually found newer deals AND processed them properly.
        # If we hit the `MAX_NEW_DEALS_PER_RUN` limit, we MUST update the watermark to the newest deal we found.
        # This effectively "skips" the older backlog deals that we chose not to process in this run.
        # Given that we sort by Newest First, skipping the backlog (old deals) is acceptable behavior for an upserter.

        # Watermark Logic Update (2026-02-07):
        # We now ALLOW updating the watermark even if the run was "incomplete" (due to token limits),
        # provided we found newer deals. This prevents the "Infinite Rejection Loop" where the system
        # keeps re-fetching the same page of bad deals because it never "finished" the page.
        # By advancing the watermark to the newest deal we *did* see, we ensure forward progress.

        # Original strict logic: should_update_watermark = (not incomplete_run) or hit_new_deal_limit
        should_update_watermark = True

        logger.info(f"DEBUG: Watermark Update Check -> Should={should_update_watermark}, Incomplete={incomplete_run}, HitLimit={hit_new_deal_limit} (Strict check disabled to force progress)")
        logger.info(f"DEBUG: Timestamp Check -> Newest={newest_deal_timestamp}, Watermark={watermark_keepa_time}, Diff={newest_deal_timestamp - watermark_keepa_time}")

        if should_update_watermark and newest_deal_timestamp > watermark_keepa_time:
            new_watermark_iso = _convert_keepa_time_to_iso(newest_deal_timestamp)
            save_watermark(new_watermark_iso)
            logger.info(f"Successfully updated watermark to {new_watermark_iso}")
        elif incomplete_run and not hit_new_deal_limit:
            # This branch is now unreachable if should_update_watermark is forced True,
            # but keeping logic structure for clarity if we revert.
            logger.warning("Task was incomplete due to token limits. forcing watermark update anyway to prevent stagnation.")

        logger.info("--- Task: update_recent_deals finished ---")
    finally:
        lock.release()
        logger.info("--- Task: update_recent_deals finished and lock released. ---")
