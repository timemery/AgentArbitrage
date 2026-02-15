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
from .token_manager import TokenManager, TokenRechargeError
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

# Version Check: Smart Ingestor Implementation
load_dotenv()

# --- Version Identifier ---
SMART_INGESTOR_VERSION = "3.0-Consolidated"

# --- Constants ---
# DB_PATH is imported from db_utils
TABLE_NAME = 'deals'
HEADERS_PATH = os.path.join(os.path.dirname(__file__), 'headers.json')
MAX_ASINS_PER_BATCH = 5 # Legacy constant, preserved for safety
SCAN_BATCH_SIZE = 50 # Optimized for Peek/Light Update
COMMIT_BATCH_SIZE = 5 # Safety limit for expensive commits
LOCK_KEY = "smart_ingestor_lock"
LOCK_TIMEOUT = 60 * 30  # 30 minutes
MAX_PAGES_PER_RUN = 50 # Safety limit
MAX_NEW_DEALS_PER_RUN = 200 # Safety limit

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

def save_safe_watermark(iso_timestamp):
    """Saves watermark with protection against future dates."""
    try:
        wm_dt = datetime.fromisoformat(iso_timestamp).astimezone(timezone.utc)
        now_utc = datetime.now(timezone.utc)
        # Allow up to 24 hours of future drift (clock skew / timezone issues)
        # Only clamp if it's egregiously in the future (e.g. > 24 hours)
        if wm_dt > (now_utc + timedelta(hours=24)):
            logger.warning(f"Clamping Extreme Future Watermark: {iso_timestamp} -> {now_utc.isoformat()}")
            iso_timestamp = now_utc.isoformat()
    except Exception as e:
        logger.error(f"Error checking watermark safety: {e}")

    save_watermark(iso_timestamp)

def check_peek_viability(stats):
    """
    Heuristic check to see if a deal is worth a heavy fetch (20 tokens).
    Returns True if potentially profitable, False if obviously bad.
    """
    if not stats: return False

    current = stats.get('current', [])
    avg90 = stats.get('avg90', [])
    avg365 = stats.get('avg365', [])

    # Indices: 0: Amazon, 1: New, 2: Used

    # 1. Determine Buy Price (Current Used)
    buy_price = -1
    if len(current) > 2 and current[2] != -1:
        buy_price = current[2]
    elif len(current) > 1 and current[1] != -1: # Fallback to New if Used missing
        buy_price = current[1]

    if buy_price == -1:
        return False # Can't buy it

    # 2. Determine Sell Price (Highest of Avg90 or Avg365)
    # We are optimistic here - find highest historical reference
    # CRITICAL UPDATE: Only consider USED prices (Index 2, 21) to align with processing logic.
    # New (1) and Amazon (0) prices are ignored to prevent processing deals with no Used history,
    # which would otherwise be rejected later (wasting tokens).
    sell_candidates = []

    # Avg90
    if len(avg90) > 2 and avg90[2] != -1: sell_candidates.append(avg90[2]) # Used
    if len(avg90) > 19 and avg90[19] != -1: sell_candidates.append(avg90[19]) # Used - Like New
    if len(avg90) > 20 and avg90[20] != -1: sell_candidates.append(avg90[20]) # Used - Very Good
    if len(avg90) > 21 and avg90[21] != -1: sell_candidates.append(avg90[21]) # Used - Good
    if len(avg90) > 22 and avg90[22] != -1: sell_candidates.append(avg90[22]) # Used - Acceptable

    # Avg365 (Capture seasonal peaks masked by recent 90-day lows)
    if len(avg365) > 2 and avg365[2] != -1: sell_candidates.append(avg365[2]) # Used
    if len(avg365) > 19 and avg365[19] != -1: sell_candidates.append(avg365[19]) # Used - Like New
    if len(avg365) > 20 and avg365[20] != -1: sell_candidates.append(avg365[20]) # Used - Very Good
    if len(avg365) > 21 and avg365[21] != -1: sell_candidates.append(avg365[21]) # Used - Good
    if len(avg365) > 22 and avg365[22] != -1: sell_candidates.append(avg365[22]) # Used - Acceptable

    if not sell_candidates:
        return False # No Used history

    # 3. Sales Velocity Check (Critical Optimization)
    # If the item has NO sales drops in the last year, it's dead inventory.
    # Rejecting here saves 20 tokens per dead deal.
    # Note: 'salesRankDrops365' might be missing in some lightweight objects, but if present, trust it.
    drops365 = stats.get('salesRankDrops365', -1)

    # Threshold: 4 drops/year (~1 per quarter).
    # Anything less is too slow/risky to waste 20 tokens on heavy analysis.
    if drops365 != -1 and drops365 < 4:
        return False

    # Also check 90 days for fresher deadness, though seasonal items might have 0 drops in 90d.
    # We'll stick to 365 to be safe for seasonal items.

    est_sell = max(sell_candidates)

    # 4. Simple Filters

    # A. Absolute Price Floor (Fees kill anything under $12)
    if est_sell < 1200:
        return False

    # B. Negative Margin (Buy > Sell)
    # Allow small buffer (e.g. 10%) just in case
    if buy_price > (est_sell * 1.1):
        return False

    # C. Gross ROI check
    # (Sell - Buy) / Buy
    # If ROI < 20%, fees will likely eat it.
    if buy_price > 0:
        gross_roi = (est_sell - buy_price) / buy_price
        if gross_roi < 0.2:
            return False

    return True

def requeue_stuck_restrictions():
    """
    Finds deals stuck in Pending (is_restricted IS NULL) for > 1 hour and re-queues them.
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            query = """
                SELECT r.asin
                FROM user_restrictions r
                JOIN deals d ON r.asin = d.asin
                WHERE r.is_restricted IS NULL
                AND d.last_seen_utc < datetime('now', '-1 hour')
            """
            cursor.execute(query)
            asins = [row[0] for row in cursor.fetchall()]

            if asins:
                logger.info(f"Ghost Restriction Sweeper: Found {len(asins)} stuck ASINs. Re-queueing.")
                celery.send_task('keepa_deals.sp_api_tasks.check_restriction_for_asins', args=[asins])
            else:
                logger.info("Ghost Restriction Sweeper: No stuck restrictions found.")

    except Exception as e:
        logger.error(f"Error in requeue_stuck_restrictions: {e}")

@celery.task(name='keepa_deals.smart_ingestor.run')
def run():
    redis_client = redis.Redis.from_url(celery.conf.broker_url)

    lock = redis_client.lock(LOCK_KEY, timeout=LOCK_TIMEOUT)
    if not lock.acquire(blocking=False):
        logger.info("--- Task: smart_ingestor is already running. Skipping execution. ---")
        return

    try:
        logger.info(f"--- Task: smart_ingestor started (Version: {SMART_INGESTOR_VERSION}) ---")

        # 0. Ghost Restriction Sweeper
        requeue_stuck_restrictions()

        create_deals_table_if_not_exists()

        api_key = os.getenv("KEEPA_API_KEY")
        xai_api_key = os.getenv("XAI_TOKEN")
        if not api_key:
            logger.error("KEEPA_API_KEY not set. Aborting.")
            return

        token_manager = TokenManager(api_key)

        # Optimization: Skip API sync if we are in deep recharge mode
        if token_manager.should_skip_sync():
            logger.info("Skipping sync (Recharge active, estimated tokens low).")
        else:
            token_manager.sync_tokens()

        logger.info("Step 1: Initializing Sync...")
        # Blocking wait (raises TokenRechargeError if wait is long)
        token_manager.request_permission_for_call(5)

        # Dynamic Deal Limit
        current_max_deals = MAX_NEW_DEALS_PER_RUN
        if token_manager.REFILL_RATE_PER_MINUTE < 20:
            current_max_deals = 50
            logger.info(f"Low Refill Rate. Reducing NEW_DEALS limit to {current_max_deals}.")

        watermark_iso = load_watermark()
        if watermark_iso is None:
            logger.error("CRITICAL: Watermark not found. Assuming fresh start/reset required but not handling here.")
            # We could default to a recent time, but backfiller used to handle this.
            # If no watermark, we should probably fetch recent deals?
            # Or default to 24 hours ago?
            # User said "Consolidating...". If this is a new deploy, maybe watermark exists.
            # If not, let's default to 24 hours ago to be safe.
            watermark_iso = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            logger.info(f"Watermark defaulted to {watermark_iso}")
            save_watermark(watermark_iso)
        else:
            # Sanity Check for Future Watermark (Self-Healing)
            try:
                wm_dt = datetime.fromisoformat(watermark_iso).astimezone(timezone.utc)
                now_utc = datetime.now(timezone.utc)
                # Apply same tolerance as save_safe_watermark
                if wm_dt > (now_utc + timedelta(hours=24)):
                    logger.warning(f"CRITICAL: Extreme Future Watermark Detected ({watermark_iso} > {now_utc.isoformat()}). Resetting to 24h ago to restore functionality.")
                    watermark_iso = (now_utc - timedelta(hours=24)).isoformat()
                    save_watermark(watermark_iso)
            except Exception as e:
                logger.error(f"Error checking watermark date: {e}")

        watermark_keepa_time = _convert_iso_to_keepa_time(watermark_iso)
        logger.info(f"Loaded watermark: {watermark_iso} (Keepa time: {watermark_keepa_time})")

        all_new_deals = []
        page = 0
        hit_new_deal_limit = False

        logger.info("Step 2: Paginating through deals to find new ones...")
        while True:
            if page >= MAX_PAGES_PER_RUN:
                logger.warning(f"Safety Limit Reached: Stopped pagination after {MAX_PAGES_PER_RUN} pages.")
                break

            if len(all_new_deals) >= current_max_deals:
                logger.warning(f"New Deal Limit Reached: Found {len(all_new_deals)} deals.")
                hit_new_deal_limit = True
                break

            token_manager.request_permission_for_call(5)

            # Hardcoded Sort Type 4 (Last Update)
            deal_response = None
            max_page_retries = 3

            for attempt in range(max_page_retries):
                try:
                    deal_response, _, tokens_left = fetch_deals_for_deals(page, api_key, sort_type=4, token_manager=token_manager)
                    if tokens_left is not None:
                        token_manager.update_after_call(tokens_left)
                    if deal_response and 'deals' in deal_response:
                        break
                except Exception as e:
                    logger.warning(f"Fetch failed on page {page} (Attempt {attempt+1}): {e}")
                    time.sleep(15 * (attempt + 1))

            if not deal_response or 'deals' not in deal_response:
                break

            if not deal_response['deals']['dr']:
                logger.info("No more deals found (empty list).")
                break

            deals_on_page = [d for d in deal_response['deals']['dr'] if validate_asin(d.get('asin'))]

            # CRITICAL: Sort Descending (Newest First) BEFORE checking watermark.
            # Keepa API response for sortType=4 is NOT strictly sorted (e.g. Index 6 can be > Index 0).
            # Without this sort, we might hit an old deal at Index 0 and stop prematurely, missing newer deals later in the list.
            deals_on_page.sort(key=lambda x: x['lastUpdate'], reverse=True)

            found_older_deal = False
            for deal in deals_on_page:
                if deal['lastUpdate'] <= watermark_keepa_time:
                    logger.info(f"Stop Trigger: Deal {deal.get('asin')} <= Watermark.")
                    found_older_deal = True
                    break
                all_new_deals.append(deal)

            if found_older_deal:
                break

            page += 1
            time.sleep(1)

        if not all_new_deals:
            logger.info("No new deals found.")
            return

        logger.info(f"Found {len(all_new_deals)} new deals. Sorting by Oldest First for incremental processing.")

        # Sort ASCENDING (Oldest -> Newest) so we can verify the watermark logic
        all_new_deals.sort(key=lambda x: x['lastUpdate'])

        # --- Check Existing ASINs ---
        asin_list = [d['asin'] for d in all_new_deals]
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
                # Zombie Data Defense (Self-Healing)
                # Check for invalid critical data
                # Use sanitized column names matching DB schema
                list_at = r['List_at']
                yr_avg = r['1yr_Avg']
                profit = r['Profit']

                is_zombie = False
                # REMOVED: Allow "Bad Data" (Missing List/Avg or Negative Profit) to remain in DB and be updated via Light Update.
                # if not list_at or str(list_at).strip() in ['-', 'N/A', '0', '0.0', '0.00']: is_zombie = True
                # elif not yr_avg or str(yr_avg).strip() in ['-', 'N/A', '0', '0.0', '0.00']: is_zombie = True
                # elif profit is not None and isinstance(profit, (int, float)) and profit <= 0: is_zombie = True

                if is_zombie:
                    logger.info(f"ASIN {r['ASIN']}: Detected as ZOMBIE/BAD DATA. Forcing heavy re-fetch.")
                else:
                    existing_asins_set.add(r['ASIN'])
                    existing_rows_map[r['ASIN']] = dict(r)
            conn_check.close()
        except Exception as e:
            logger.warning(f"Failed to check existing ASINs: {e}")

        # Processing Loop
        # Iterate chunks
        current_batch_size = SCAN_BATCH_SIZE
        # Dynamic Batch Sizing: Reduce batch size for slow connections to avoid "Deficit Lockout".
        if token_manager.REFILL_RATE_PER_MINUTE < 10:
            current_batch_size = 5
            logger.info(f"Critically Low Refill Rate ({token_manager.REFILL_RATE_PER_MINUTE}/min). Reducing SCAN_BATCH_SIZE to {current_batch_size} to match Burst Threshold (40).")
        elif token_manager.REFILL_RATE_PER_MINUTE < 20:
            current_batch_size = 20
            logger.info(f"Low Refill Rate ({token_manager.REFILL_RATE_PER_MINUTE}/min). Reducing SCAN_BATCH_SIZE to {current_batch_size} to prevent Deficit Lockout.")

        # We process large batches (50) for cheap "Peek" checks, but small batches (5) for expensive "Commits".

        with open(HEADERS_PATH) as f:
            headers = json.load(f)

        total_upserted = 0

        for i in range(0, len(all_new_deals), current_batch_size):
            chunk_deals = all_new_deals[i:i + current_batch_size]
            chunk_asins = [d['asin'] for d in chunk_deals]

            chunk_new_asins = [a for a in chunk_asins if a not in existing_asins_set]
            chunk_existing_asins = [a for a in chunk_asins if a in existing_asins_set]

            chunk_products = {}

            # --- STAGE 1: PEEK (For New/Zombie Deals) ---
            new_candidates = []
            if chunk_new_asins:
                # Estimate: 5 tokens/ASIN (since offers=0 is invalid/unsupported, we use offers=20).
                # Verification confirmed cost is ~5 tokens/ASIN. Batch 50 = 250 tokens (Safe within burst).
                token_manager.request_permission_for_call(5 * len(chunk_new_asins))
                # Use stats=365 for Peek. Explicit offers=20.
                peek_resp, _, _, tokens_left = fetch_current_stats_batch(api_key, chunk_new_asins, days=365, offers=20)
                if tokens_left: token_manager.update_after_call(tokens_left)

                if peek_resp and 'products' in peek_resp:
                    for p in peek_resp['products']:
                        if check_peek_viability(p.get('stats')):
                            new_candidates.append(p['asin'])
                        else:
                            logger.info(f"Peek Rejected: ASIN {p.get('asin')}")

            # --- STAGE 2: COMMIT (For Survivors) ---
            if new_candidates:
                # Process in sub-batches to prevent deficit shock
                for j in range(0, len(new_candidates), COMMIT_BATCH_SIZE):
                    sub_batch = new_candidates[j:j + COMMIT_BATCH_SIZE]
                    token_manager.request_permission_for_call(20 * len(sub_batch))
                    prod_resp, _, _, tokens_left = fetch_product_batch(api_key, sub_batch, days=365, history=1, offers=20)
                    if tokens_left: token_manager.update_after_call(tokens_left)
                    if prod_resp and 'products' in prod_resp:
                        for p in prod_resp['products']:
                            chunk_products[p['asin']] = p

            # --- EXISTING DEALS (Light Update) ---
            if chunk_existing_asins:
                # Estimate: 5 tokens/ASIN (offers=20)
                token_manager.request_permission_for_call(5 * len(chunk_existing_asins))
                prod_resp_light, _, _, tokens_left = fetch_current_stats_batch(api_key, chunk_existing_asins, days=180, offers=20)
                if tokens_left: token_manager.update_after_call(tokens_left)
                if prod_resp_light and 'products' in prod_resp_light:
                    for p in prod_resp_light['products']:
                        chunk_products[p['asin']] = p

            # --- PROCESS ---
            rows_to_upsert = []
            for deal in chunk_deals:
                asin = deal['asin']
                if asin not in chunk_products: continue

                product_data = chunk_products[asin]
                product_data.update(deal)

                processed_row = None
                if asin in existing_asins_set:
                     processed_row = _process_lightweight_update(existing_rows_map[asin], product_data)
                     if processed_row:
                         processed_row = clean_numeric_values(processed_row)
                         processed_row['last_seen_utc'] = datetime.now(timezone.utc).isoformat()
                         processed_row['source'] = 'smart_ingestor_light'
                else:
                     seller_data_cache = get_seller_info_for_single_deal(product_data, api_key, token_manager)
                     processed_row = _process_single_deal(product_data, seller_data_cache, xai_api_key)
                     if processed_row:
                         processed_row = clean_numeric_values(processed_row)
                         processed_row['last_seen_utc'] = datetime.now(timezone.utc).isoformat()
                         processed_row['source'] = 'smart_ingestor'

                if processed_row:
                    rows_to_upsert.append(processed_row)

            # --- UPSERT & WATERMARK RATCHET ---
            if rows_to_upsert:
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

                        # Trigger restriction check
                        new_asins = [row['ASIN'] for row in rows_to_upsert if 'ASIN' in row]
                        if new_asins:
                            celery.send_task('keepa_deals.sp_api_tasks.check_restriction_for_asins', args=[new_asins])

                        # Watermark Ratchet
                        # We are processing Oldest -> Newest.
                        # The last deal in this chunk is the "newest" we have fully processed so far.
                        last_deal_in_chunk = chunk_deals[-1] # This is safe because chunk_deals corresponds to loop
                        new_wm_iso = _convert_keepa_time_to_iso(last_deal_in_chunk['lastUpdate'])
                        save_safe_watermark(new_wm_iso)
                        logger.info(f"Watermark ratcheted to {new_wm_iso}")

                except Exception as e:
                    logger.error(f"Chunk processing/upsert failed: {e}", exc_info=True)
            else:
                 # Even if no rows upserted (all rejected), we MUST advance watermark past these deals
                 # to avoid infinite loops on rejected deals.
                 # "Scan vs Save: The watermark must track the timestamp of deals scanned, not just deals saved."
                 last_deal_in_chunk = chunk_deals[-1]
                 new_wm_iso = _convert_keepa_time_to_iso(last_deal_in_chunk['lastUpdate'])
                 save_safe_watermark(new_wm_iso)
                 logger.info(f"Watermark advanced (no deals saved) to {new_wm_iso}")


        logger.info(f"Task Complete: Processed {len(all_new_deals)} scanned, upserted {total_upserted}.")

    except TokenRechargeError as e:
        logger.warning(f"--- Task Paused: {e}. Releasing lock to free worker. ---")
        return # Exit task, releasing lock

    finally:
        if lock.locked():
            lock.release()
            logger.info("--- Task: smart_ingestor lock released. ---")
