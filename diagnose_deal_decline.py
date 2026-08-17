#!/usr/bin/env python3
"""
diagnose_deal_decline.py
------------------------
Comprehensive Diagnostic Tool to investigate why the deal count on the
Agent Arbitrage Dashboard dropped (e.g., from ~350 to ~120 to 48).

Checks performed:
1. Database Summary & Funnel Analysis (`deals` table: total vs dashboard visible,
   breakdown of unprofitable, missing List_at, missing 1yr_Avg, Amazon selling, etc.)
2. Deal Age & Janitor Risk (`last_seen_utc` age distribution, upcoming deletions)
3. System Watermark State (`system_state` table age and drift)
4. Keepa API & Token Manager Health (Token balance, Refill Rate from API, Redis state,
   calculated recharge wait time, burst threshold)
5. Live Pipeline Funnel Dry-Run (Sample Keepa delta fetch & stage drop-off analysis)
6. Environment & Background Process Checks (Celery workers, Redis queue length, log sizes)
7. Executive Root Cause Analysis & Recommended Solutions

Usage:
    python3 diagnose_deal_decline.py
"""

import os
import sys
import time
import json
import math
import sqlite3
import subprocess
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ANSI Color Codes for readable CLI output
HEADER = '\033[95m'
BLUE = '\033[94m'
CYAN = '\033[96m'
GREEN = '\033[92m'
WARNING = '\033[93m'
FAIL = '\033[91m'
ENDC = '\033[0m'
BOLD = '\033[1m'

def print_section(title):
    print("\n" + "="*80)
    print(f"{BOLD}{CYAN}{title}{ENDC}")
    print("="*80)

def print_sub(title):
    print(f"\n{BOLD}{BLUE}--- {title} ---{ENDC}")

def get_db_path():
    from keepa_deals.db_utils import DB_PATH
    return DB_PATH

def check_database():
    print_section("1. DATABASE SUMMARY & DASHBOARD FUNNEL")
    db_path = get_db_path()
    
    if not os.path.exists(db_path):
        print(f"{FAIL}Error: Database file '{db_path}' not found!{ENDC}")
        return

    try:
        from keepa_deals.db_utils import get_db_connection
        with get_db_connection(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Check if deals table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='deals'")
            if not cursor.fetchone():
                print(f"{WARNING}Table 'deals' does not exist in '{db_path}'.{ENDC}")
                return

            # 1. Total Raw Rows
            cursor.execute("SELECT COUNT(*) FROM deals")
            total_raw = cursor.fetchone()[0]
            print(f"Total Raw Rows in 'deals' table: {BOLD}{total_raw}{ENDC}")

            if total_raw == 0:
                print(f"{WARNING}Database table 'deals' is currently empty in this environment.{ENDC}")
                return

            # 2. Dashboard Visible Deals
            # Dashboard SQL query condition:
            # Profit > 0 (sanitized) AND List_at IS NOT NULL AND List_at > 0 AND 1yr_Avg IS NOT NULL AND 1yr_Avg NOT IN ('-', 'N/A', '', '0', '0.00', '$0.00')
            sanitized_profit = "CAST(REPLACE(REPLACE(\"Profit\", '$', ''), ',', '') AS REAL)"
            sanitized_list_at = "CAST(REPLACE(REPLACE(\"List_at\", '$', ''), ',', '') AS REAL)"
            
            visible_sql = f"""
                SELECT COUNT(*) FROM deals 
                WHERE {sanitized_profit} > 0 
                  AND "List_at" IS NOT NULL 
                  AND {sanitized_list_at} > 0 
                  AND "1yr_Avg" IS NOT NULL 
                  AND "1yr_Avg" NOT IN ('-', 'N/A', '', '0', '0.00', '$0.00')
                  AND "1yr_Avg" != 0
            """
            cursor.execute(visible_sql)
            dashboard_visible = cursor.fetchone()[0]
            
            pct_visible = (dashboard_visible / total_raw * 100) if total_raw > 0 else 0
            print(f"Dashboard Visible Deals (Default Filters): {BOLD}{GREEN}{dashboard_visible}{ENDC} ({pct_visible:.1f}% of DB)")

            # 3. Breakdown of Excluded Deals
            print_sub("Breakdown of Excluded Deals in Database")
            
            # Profit <= 0 or NULL
            cursor.execute(f"SELECT COUNT(*) FROM deals WHERE {sanitized_profit} <= 0 OR \"Profit\" IS NULL")
            no_profit_cnt = cursor.fetchone()[0]
            print(f"  • Non-positive or Missing Profit (Profit <= $0): {WARNING}{no_profit_cnt}{ENDC}")

            # Missing List_at
            cursor.execute(f"SELECT COUNT(*) FROM deals WHERE \"List_at\" IS NULL OR {sanitized_list_at} <= 0")
            no_list_at_cnt = cursor.fetchone()[0]
            print(f"  • Missing or Invalid 'List_at' Price: {WARNING}{no_list_at_cnt}{ENDC}")

            # Missing 1yr_Avg
            cursor.execute("""
                SELECT COUNT(*) FROM deals 
                WHERE "1yr_Avg" IS NULL 
                   OR "1yr_Avg" IN ('-', 'N/A', '', '0', '0.00', '$0.00')
                   OR "1yr_Avg" = 0
            """)
            no_1yr_avg_cnt = cursor.fetchone()[0]
            print(f"  • Missing or Invalid '1yr_Avg' (No Inferred Sales): {WARNING}{no_1yr_avg_cnt}{ENDC}")

            # Amazon Selling (AMZ = '⚠️')
            cursor.execute("SELECT COUNT(*) FROM deals WHERE \"AMZ\" = '⚠️'")
            amz_selling_cnt = cursor.fetchone()[0]
            print(f"  • Amazon is Selling Item (AMZ = ⚠️): {amz_selling_cnt}")

            # Restricted Deals
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_restrictions'")
            if cursor.fetchone():
                cursor.execute("""
                    SELECT COUNT(*) FROM deals d 
                    JOIN user_restrictions ur ON d.ASIN = ur.asin 
                    WHERE ur.is_restricted = 1
                """)
                restricted_cnt = cursor.fetchone()[0]
                print(f"  • Restricted Deals (Gated): {restricted_cnt}")

            # 4. Age Breakdown (last_seen_utc) & Janitor Impact
            print_sub("Deal Freshness & Janitor Risk (last_seen_utc)")
            now_utc = datetime.now(timezone.utc)
            cutoff_24h = (now_utc - timedelta(hours=24)).isoformat()
            cutoff_48h = (now_utc - timedelta(hours=48)).isoformat()
            cutoff_72h = (now_utc - timedelta(hours=72)).isoformat()

            cursor.execute("SELECT COUNT(*) FROM deals WHERE last_seen_utc >= ?", (cutoff_24h,))
            seen_24h = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM deals WHERE last_seen_utc < ? AND last_seen_utc >= ?", (cutoff_24h, cutoff_48h))
            seen_24_48h = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM deals WHERE last_seen_utc < ? AND last_seen_utc >= ?", (cutoff_48h, cutoff_72h))
            seen_48_72h = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM deals WHERE last_seen_utc < ?", (cutoff_72h,))
            seen_over_72h = cursor.fetchone()[0]

            print(f"  • Updated in last 24 hours: {BOLD}{GREEN}{seen_24h}{ENDC}")
            print(f"  • Updated 24h - 48h ago: {seen_24_48h}")
            print(f"  • Updated 48h - 72h ago (At Risk): {WARNING}{seen_48_72h}{ENDC}")
            print(f"  • Older than 72 hours (Janitor Imminent Deletion): {FAIL}{seen_over_72h}{ENDC}")

            # 5. Ingestion Rate vs Pruning Rate
            print_sub("Recent Ingestion Activity (New/Updated Deals)")
            for hours in [1, 6, 12, 24, 48]:
                c_time = (now_utc - timedelta(hours=hours)).isoformat()
                cursor.execute("SELECT COUNT(*) FROM deals WHERE last_seen_utc >= ?", (c_time,))
                cnt = cursor.fetchone()[0]
                print(f"  • Ingested / Refreshed in last {hours}h: {cnt}")

    except Exception as e:
        print(f"{FAIL}Database query failed: {e}{ENDC}")

def check_system_watermark():
    print_section("2. SYSTEM WATERMARK & STATE")
    try:
        from keepa_deals.db_utils import load_watermark
        wm_iso = load_watermark()
        print(f"Current Watermark (ISO): {BOLD}{wm_iso}{ENDC}")
        
        if wm_iso:
            wm_dt = datetime.fromisoformat(wm_iso).astimezone(timezone.utc)
            now_utc = datetime.now(timezone.utc)
            delta = now_utc - wm_dt
            hours_behind = delta.total_seconds() / 3600.0

            if hours_behind < -1:
                print(f"{FAIL}WARNING: Watermark is set IN THE FUTURE by {abs(hours_behind):.2f} hours! (This prevents new delta fetches){ENDC}")
            elif hours_behind > 24:
                print(f"{WARNING}WARNING: Watermark is {hours_behind:.1f} hours behind current time. Ingestor has significant catch-up work.{ENDC}")
            else:
                print(f"{GREEN}Watermark is healthy ({hours_behind:.2f} hours behind current time).{ENDC}")
        else:
            print(f"{WARNING}Watermark is missing or None. Smart Ingestor will default to 24h ago.{ENDC}")
    except Exception as e:
        print(f"{FAIL}Failed to check watermark: {e}{ENDC}")

def check_keepa_and_tokens():
    print_section("3. KEEPA API & TOKEN MANAGER HEALTH")
    api_key = os.getenv('KEEPA_API_KEY', '').strip('"').strip("'")
    if not api_key:
        print(f"{FAIL}Error: KEEPA_API_KEY environment variable not set!{ENDC}")
        return

    # 1. Live Keepa API Status
    print_sub("Live Keepa API Query (/token)")
    try:
        from keepa_deals.keepa_api import get_token_status
        status = get_token_status(api_key)
        if status and 'tokensLeft' in status:
            tokens_left = status.get('tokensLeft')
            refill_rate = status.get('refillRate')
            print(f"  • Real-Time Tokens Left: {BOLD}{CYAN}{tokens_left}{ENDC}")
            print(f"  • Real-Time Refill Rate: {BOLD}{CYAN}{refill_rate}{ENDC} tokens/minute")

            if refill_rate and refill_rate < 10:
                print(f"  • {WARNING}Note: Refill rate is low ({refill_rate}/min). Systems will use burst threshold of 40 tokens.{ENDC}")
            elif refill_rate and refill_rate >= 20:
                print(f"  • {GREEN}Upgraded Plan Detected ({refill_rate}/min). Higher throughput capacity available.{ENDC}")
        else:
            print(f"  • {FAIL}Could not retrieve live token status from Keepa API.{ENDC}")
    except Exception as e:
        print(f"  • {FAIL}Failed Keepa API query: {e}{ENDC}")

    # 2. Redis Shared Token State
    print_sub("Redis Shared State (TokenManager)")
    try:
        from keepa_deals.token_manager import TokenManager
        tm = TokenManager(api_key)
        
        print(f"  • Redis Connected: {GREEN if tm.redis_client else FAIL}{tm.redis_client is not None}{ENDC}")
        if tm.redis_client:
            r_tokens = tm.redis_client.get(TokenManager.REDIS_KEY_TOKENS)
            r_rate = tm.redis_client.get(TokenManager.REDIS_KEY_RATE)
            r_recharge = tm.redis_client.get(TokenManager.REDIS_KEY_RECHARGE_MODE)
            r_last_sync = tm.redis_client.get(TokenManager.REDIS_KEY_LAST_SYNC_TIMESTAMP)

            print(f"  • Redis Cached Tokens: {r_tokens}")
            print(f"  • Redis Refill Rate: {r_rate}")
            print(f"  • Recharge Mode Active: {r_recharge}")
            print(f"  • Effective Burst Threshold: {tm.BURST_THRESHOLD}")
            print(f"  • Effective Max Deficit: {tm.MAX_DEFICIT}")

            # Calculate wait time if low
            curr_t = float(r_tokens) if r_tokens is not None else tm.tokens
            rate_val = float(r_rate) if r_rate is not None else tm.REFILL_RATE_PER_MINUTE
            target = tm.BURST_THRESHOLD
            if curr_t < target and rate_val > 0:
                needed = target - curr_t
                wait_sec = math.ceil((needed / rate_val) * 60)
                print(f"  • {WARNING}Estimated Recharge Time to Burst ({target} tokens): {wait_sec}s ({wait_sec/60:.1f} mins){ENDC}")
                if wait_sec > 60:
                    print(f"  • {FAIL}CRITICAL LIKELY CAUSE: Wait time {wait_sec}s > 60s will trigger TokenRechargeError! Smart Ingestor task will exit every 1min without processing deals until tokens reach {target}.{ENDC}")
    except Exception as e:
        print(f"  • {FAIL}Failed TokenManager inspection: {e}{ENDC}")

def check_live_pipeline_funnel():
    print_section("4. PIPELINE FUNNEL DRY-RUN")
    api_key = os.getenv('KEEPA_API_KEY', '').strip('"').strip("'")
    if not api_key:
        print(f"{WARNING}Skipping pipeline dry-run (No Keepa API key).{ENDC}")
        return

    try:
        from keepa_deals.keepa_api import fetch_deals_for_deals, fetch_product_batch
        from keepa_deals.smart_ingestor import check_peek_viability, _convert_iso_to_keepa_time
        from keepa_deals.processing import _process_single_deal
        from keepa_deals.db_utils import load_watermark

        wm_iso = load_watermark()
        if not wm_iso:
            wm_iso = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
        
        watermark_keepa_min = _convert_iso_to_keepa_time(wm_iso)
        print(f"Querying Keepa API for 1 sample page of deals since watermark ({wm_iso})...")

        from keepa_deals.token_manager import TokenManager
        tm = TokenManager(api_key)

        res, tokens_consumed, tokens_left = fetch_deals_for_deals(page=0, api_key=api_key, token_manager=tm, sort_type=4)
        deals_list = res.get('deals', []) if isinstance(res, dict) else []
        deals_count = len(deals_list)
        print(f"Keepa returned {BOLD}{deals_count}{ENDC} candidate deals in delta feed.")

        if deals_count == 0:
            print(f"{WARNING}No candidate deals returned by Keepa for current watermark.{ENDC}")
            return

        sample_deals = deals_list[:20]
        asins = [d['asin'] for d in sample_deals if 'asin' in d]
        print(f"Sampling {len(asins)} ASINs for processing funnel dry-run...")

        # Fetch product batch
        batch_res = fetch_product_batch(asins, token_manager=tm, stats=365, days=365, history=1)
        products = batch_res[0].get('products', []) if isinstance(batch_res, tuple) else []

        print(f"Keepa product data returned for {len(products)} ASINs.")

        peek_pass = 0
        used_offer_pass = 0
        inferred_sales_pass = 0
        profitable_pass = 0

        for p in products:
            stats = p.get('stats', {})
            # 1. Peek viability check
            if check_peek_viability(stats):
                peek_pass += 1
            
            # 2. Process deal dry-run
            deal_obj = next((d for d in sample_deals if d.get('asin') == p.get('asin')), {})
            try:
                processed = _process_single_deal(p, deal_obj)
                if processed:
                    # Check Used Offer
                    if processed.get('Price Now') is not None:
                        used_offer_pass += 1
                    
                    # Check 1yr_Avg
                    yr1 = processed.get('1yr. Avg.')
                    if yr1 is not None and yr1 not in ['-', 'N/A', '', '0', '0.00', '$0.00', 0]:
                        inferred_sales_pass += 1
                    
                    # Check Profit
                    profit = processed.get('Profit', 0)
                    if profit and profit > 0:
                        profitable_pass += 1
            except Exception as e:
                pass

        print_sub("Funnel Survival Rates on Sample Batch")
        print(f"  1. Returned by Keepa: {len(products)}")
        print(f"  2. Passed Peek Viability Check: {peek_pass} / {len(products)} ({(peek_pass/len(products)*100 if products else 0):.1f}%)")
        print(f"  3. Valid Winning Used Offer Found: {used_offer_pass} / {len(products)} ({(used_offer_pass/len(products)*100 if products else 0):.1f}%)")
        print(f"  4. Passed Inferred Sales (1yr_Avg != None): {inferred_sales_pass} / {len(products)} ({(inferred_sales_pass/len(products)*100 if products else 0):.1f}%)")
        print(f"  5. Dashboard Eligible (Profit > $0): {BOLD}{GREEN}{profitable_pass}{ENDC} / {len(products)} ({(profitable_pass/len(products)*100 if products else 0):.1f}%)")

        if inferred_sales_pass < len(products) * 0.3:
            print(f"  • {WARNING}HIGH DROP-OFF AT INFERRED SALES: Many products have 0 confirmed sale rank drops or sparse sales history, returning 1yr_Avg = None (and excluded from Dashboard).{ENDC}")

    except Exception as e:
        print(f"{FAIL}Failed live pipeline funnel dry-run: {e}{ENDC}")

def check_environment_and_processes():
    print_section("5. ENVIRONMENT & BACKGROUND PROCESSES")
    
    # 1. Celery Workers
    try:
        res = subprocess.run(["pgrep", "-af", "celery"], capture_output=True, text=True)
        celery_procs = res.stdout.strip().split('\n') if res.stdout.strip() else []
        print(f"Active Celery Processes: {BOLD}{len(celery_procs)}{ENDC}")
        for p in celery_procs[:5]:
            if p:
                print(f"  • {p}")
        if not celery_procs or not any('worker' in p for p in celery_procs):
            print(f"  • {FAIL}CRITICAL: Celery Worker process is NOT RUNNING! Background ingestion is stopped!{ENDC}")
        if not any('beat' in p for p in celery_procs):
            print(f"  • {WARNING}WARNING: Celery Beat process is NOT RUNNING! Scheduled tasks will not trigger.{ENDC}")
    except Exception as e:
        print(f"Failed to check Celery processes: {e}")

    # 2. Redis Queue Length
    try:
        import redis
        redis_url = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')
        r = redis.Redis.from_url(redis_url, decode_responses=True)
        q_len = r.llen('celery')
        print(f"Celery Redis Queue Length ('celery'): {BOLD}{q_len}{ENDC}")
        if q_len > 100:
            print(f"  • {WARNING}Queue backlog detected ({q_len} tasks pending). Workers may be slow or stuck.{ENDC}")
    except Exception as e:
        print(f"Failed to check Redis queue: {e}")

    # 3. Log File Sizes
    print_sub("Log File Size Check")
    for log_name in ['celery_worker.log', 'celery_beat.log', 'app.log', 'celery.log']:
        if os.path.exists(log_name):
            size_mb = os.path.getsize(log_name) / (1024 * 1024)
            color = FAIL if size_mb > 50 else (WARNING if size_mb > 10 else GREEN)
            print(f"  • {log_name}: {color}{size_mb:.2f} MB{ENDC}")
            if size_mb > 50:
                print(f"    {FAIL}WARNING: {log_name} is very large ({size_mb:.1f} MB). Truncate to free disk space.{ENDC}")

def synthesize_and_recommend():
    print_section("6. EXECUTIVE DIAGNOSTIC SUMMARY & RECOMMENDATIONS")
    
    print(f"{BOLD}Summary of Likely Root Causes for Deal Count Drop:~{ENDC}\n")

    print(f"1. {BOLD}The TokenManager Recharge Livelock Loop:{ENDC}")
    print("   • When switching or running tasks with a low token balance relative to BURST_THRESHOLD (e.g. 150 or 280),")
    print("     the calculated wait time exceeds 60s. Smart Ingestor raises `TokenRechargeError` and exits immediately.")
    print("   • Every 1 minute, Celery Beat re-triggers Smart Ingestor, which finds tokens still below threshold and exits again.")
    print("   • Result: Smart Ingestor NEVER finishes fetching or inserting new deals into `deals.db`!")

    print(f"\n2. {BOLD}Janitor Asymmetric Pruning Rate:{ENDC}")
    print("   • The Janitor process runs every 4 hours and deletes any deal where `last_seen_utc` is older than 72 hours.")
    print("   • Because the Smart Ingestor is livelocked and not updating `last_seen_utc` on existing deals or adding new ones,")
    print("     the Janitor steadily deletes ~20-30% of the database every run, causing total deals to drop from 350 -> 120 -> 48.")

    print(f"\n3. {BOLD}Strict Inferred Sales Data Filter (March 2026 Spec):{ENDC}")
    print("   • Unverified Keepa Stats listing averages ('Silver Standard') were strictly removed from calculations.")
    print("   • Any deal lacking at least 1 true inferred sale event returns `1yr_Avg = None` or `List_at = None`.")
    print("   • These deals are saved in `deals.db` but strictly hidden from the Dashboard query (`1yr_Avg IS NOT NULL`).")

    print_sub("ACTIONABLE RESOLUTION STEPS")
    print(f"{BOLD}Step 1. Force Reset Tokens & Clear Zombie Locks:{ENDC}")
    print("   Execute the clean restart script:")
    print("   `sudo ./kill_everything_force.sh`")
    print("   `redis-cli FLUSHALL && redis-cli SAVE`")
    print("   `sudo ./start_celery.sh`")

    print(f"\n{BOLD}Step 2. Adjust Ingestion Frequency (Prevent Livelock):{ENDC}")
    print("   In `celery_config.py`, change `smart-ingestor-run` schedule from `*` (every 1 min) to `*/5` (every 5 min).")
    print("   This gives Keepa tokens adequate time to recharge past BURST_THRESHOLD between task runs.")

    print(f"\n{BOLD}Step 3. Reset Watermark to Fetch Fresh Deals:{ENDC}")
    print("   Run Python to reset watermark to 24 hours ago:")
    print("   `python3 -c \"from keepa_deals.db_utils import save_watermark; from datetime import datetime, timezone, timedelta; save_watermark((datetime.now(timezone.utc) - timedelta(hours=24)).isoformat())\"`")

    print(f"\n{BOLD}Step 4. Run Manual Smart Ingestor Test Run:{ENDC}")
    print("   `python3 -c \"from keepa_deals.smart_ingestor import smart_ingestor_run; smart_ingestor_run()\"`")
    print("   Check output to confirm deals are being written and dashboard count rises.")

def main():
    print(f"{BOLD}{HEADER}")
    print("================================================================================")
    print("          AGENT ARBITRAGE - DASHBOARD DEAL DECLINE DIAGNOSTIC TOOL              ")
    print("================================================================================")
    print(f"{ENDC}")
    
    check_database()
    check_system_watermark()
    check_keepa_and_tokens()
    check_live_pipeline_funnel()
    check_environment_and_processes()
    synthesize_and_recommend()

    print("\n" + "="*80)
    print(f"{BOLD}{GREEN}Diagnostic check complete.{ENDC}")
    print("="*80 + "\n")

if __name__ == '__main__':
    main()
