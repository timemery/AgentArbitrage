#!/usr/bin/env python3
import os
import sys
import time
import json
import sqlite3
import subprocess
import requests
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Try to import redis, but handle if missing (so script doesn't crash immediately)
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# Ensure project root is in sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
load_dotenv()

# --- Config ---
IS_PROD = os.path.exists('/var/www/agentarbitrage')
PROD_ROOT = '/var/www/agentarbitrage'

# Correct Log Paths based on start_celery.sh
WORKER_LOG = os.path.join(PROD_ROOT, 'celery_worker.log') if IS_PROD else 'celery_worker.log'
BEAT_LOG = os.path.join(PROD_ROOT, 'celery_beat.log') if IS_PROD else 'celery_beat.log'
MONITOR_LOG = os.path.join(PROD_ROOT, 'celery_monitor.log') if IS_PROD else 'celery_monitor.log'
# Fallback for historical analysis
LEGACY_LOG = os.path.join(PROD_ROOT, 'celery.log') if IS_PROD else 'celery.log'

DB_PATH = os.path.join(PROD_ROOT, 'deals.db') if IS_PROD else os.path.join(os.path.dirname(__file__), '..', 'deals.db')
KEEPA_API_KEY = os.getenv("KEEPA_API_KEY")

def print_header(title):
    print(f"\n{'='*40}")
    print(f" {title}")
    print(f"{'='*40}")

def tail_file(filepath, n=20):
    """Returns the last n lines of a file."""
    if not os.path.exists(filepath):
        return [f"[WARNING] File not found: {filepath}"]
    try:
        cmd = ['tail', '-n', str(n), filepath]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout.splitlines()
    except Exception as e:
        return [f"[ERROR] Could not read file: {e}"]

def check_code_version():
    print_header("CODE VERSION CHECK")

    # Determine path to simple_task.py
    if IS_PROD:
        simple_task_path = os.path.join(PROD_ROOT, 'keepa_deals', 'simple_task.py')
    else:
        simple_task_path = os.path.join(os.path.dirname(__file__), '..', 'keepa_deals', 'simple_task.py')

    print(f"Checking file: {simple_task_path}")

    if not os.path.exists(simple_task_path):
         print(f"[ERROR] simple_task.py not found at {simple_task_path}")
         return

    try:
        with open(simple_task_path, 'r') as f:
            content = f.read()
            if 'SORT_TYPE_LAST_UPDATE = 4' in content:
                print("[PASS] simple_task.py contains 'SORT_TYPE_LAST_UPDATE = 4'.")
            else:
                print("[FAIL] simple_task.py does NOT contain 'SORT_TYPE_LAST_UPDATE = 4'. Disk code is incorrect!")
    except Exception as e:
        print(f"[ERROR] Could not read simple_task.py: {e}")

def analyze_active_logs():
    print_header("ACTIVE WORKER LOG ANALYSIS")

    print(f"Checking Worker Log: {WORKER_LOG}")
    if not os.path.exists(WORKER_LOG):
        print(f"[WARNING] Worker log not found at {WORKER_LOG}")
        # Try checking monitor log if worker log is missing
        print(f"Checking Monitor Log instead: {MONITOR_LOG}")
        print("\n--- Last 20 lines of Monitor Log ---")
        for line in tail_file(MONITOR_LOG, 20):
            print(line)
        return

    # Analyze Worker Log
    logs = tail_file(WORKER_LOG, 100) # Get last 100 lines for analysis

    count_sort_0 = 0
    count_sort_4 = 0
    last_sort_0_ts = None
    last_sort_4_ts = None

    for line in logs:
        if 'Sort: 0' in line:
            count_sort_0 += 1
            last_sort_0_ts = line.split(' ')[0] if line else "Unknown"
        if 'Sort: 4' in line:
            count_sort_4 += 1
            last_sort_4_ts = line.split(' ')[0] if line else "Unknown"

    print(f"Found 'Sort: 0' (Old/Bad): {count_sort_0} times. Last: {last_sort_0_ts}")
    print(f"Found 'Sort: 4' (New/Good): {count_sort_4} times. Last: {last_sort_4_ts}")

    if count_sort_4 > 0:
        print("\n[PASS] 'Sort: 4' detected in recent logs. Correct code is running.")
    elif count_sort_0 > 0:
        print("\n[FAIL] 'Sort: 0' detected in recent logs. Stale code is running!")
    else:
        print("\n[INFO] No Sort Type logs found in the last 100 lines. The worker might be idle or crashing.")

    # Always print the last few lines to see crashes
    print("\n--- Last 20 lines of Worker Log ---")
    for line in logs[-20:]:
        print(line)

def check_redis_locks():
    print_header("REDIS LOCK STATUS")

    if not REDIS_AVAILABLE:
        print("[WARNING] Redis module not installed. Skipping Python check.")
        # Try redis-cli
        try:
             res = subprocess.run(['redis-cli', 'keys', '*lock*'], capture_output=True, text=True)
             if res.returncode == 0:
                 print("Found keys via redis-cli:")
                 print(res.stdout)
             else:
                 print("redis-cli failed.")
        except FileNotFoundError:
             print("redis-cli not found.")
        return

    try:
        r = redis.Redis.from_url('redis://127.0.0.1:6379/0', socket_connect_timeout=2)
        r.ping() # Check connection

        # Backfill Lock
        backfill_key = "backfill_deals_lock"
        if r.exists(backfill_key):
            ttl = r.ttl(backfill_key)
            print(f"[LOCKED] Backfill Lock ({backfill_key}) IS held.")
            print(f"       TTL: {ttl} seconds ({ttl/3600:.1f} hours).")
        else:
            print(f"[FREE] Backfill Lock ({backfill_key}) is NOT held.")

        # Upserter Lock
        upsert_key = "update_recent_deals_lock"
        if r.exists(upsert_key):
            ttl = r.ttl(upsert_key)
            print(f"[LOCKED] Upserter Lock ({upsert_key}) IS held.")
            print(f"       TTL: {ttl} seconds.")
        else:
            print(f"[FREE] Upserter Lock ({upsert_key}) is NOT held.")

    except redis.exceptions.ConnectionError:
        print("[ERROR] Could not connect to Redis at 127.0.0.1:6379.")
    except Exception as e:
        print(f"[ERROR] Redis check failed: {e}")

def check_token_status():
    print_header("KEEPA TOKEN STATUS")
    if not KEEPA_API_KEY:
        print("[ERROR] KEEPA_API_KEY not found in .env")
        return

    url = f"https://api.keepa.com/token?key={KEEPA_API_KEY}"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            tokens = data.get('tokensLeft')
            print(f"[OK] Tokens Left: {tokens}")
            print(f"     Refill Rate: {data.get('refillRate')}/min")
        else:
            print(f"[ERROR] API Request failed: {response.status_code}")
    except Exception as e:
        print(f"[ERROR] Token check failed: {e}")

def check_celery_processes():
    print_header("CELERY PROCESSES")
    try:
        # pgrep -af celery
        cmd = ['pgrep', '-af', 'celery']
        result = subprocess.run(cmd, capture_output=True, text=True)
        processes = result.stdout.splitlines()

        worker_running = False
        beat_running = False

        for p in processes:
            # print(f"Process: {p}") # Noisy
            # Robust check: look for 'celery' AND 'worker'/'beat' keywords independently
            if ('celery' in p and 'worker' in p) or 'celery@' in p:
                worker_running = True
            if 'celery' in p and 'beat' in p:
                beat_running = True

        # Check monitor specifically
        monitor_cmd = ['pgrep', '-f', 'monitor_and_restart']
        monitor_res = subprocess.run(monitor_cmd, capture_output=True, text=True)
        monitor_running = bool(monitor_res.stdout.strip())

        if monitor_running:
             print("[PASS] Resiliency Monitor (monitor_and_restart) is RUNNING.")
        else:
             print("[CRITICAL] Resiliency Monitor is NOT RUNNING.")

        if not worker_running:
            print("[CRITICAL] Celery WORKER is NOT running!")
        if not beat_running:
            print("[CRITICAL] Celery BEAT is NOT running!")
        if worker_running and beat_running:
            print("[PASS] Both Worker and Beat appear to be running.")

    except Exception as e:
        print(f"[ERROR] Process check failed: {e}")

def check_db_health():
    print_header("DATABASE HEALTH")
    if not os.path.exists(DB_PATH):
        print(f"[ERROR] Database not found at {DB_PATH}")
        return

    print(f"Checking DB: {DB_PATH}")

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Count deals
        try:
            cursor.execute("SELECT count(*) FROM deals")
            count = cursor.fetchone()[0]
            print(f"Total Deals: {count}")
        except sqlite3.OperationalError:
            print(f"[ERROR] Could not count deals.")

        # Check system state
        try:
            cursor.execute("SELECT key, value FROM system_state")
            rows = cursor.fetchall()
            print("\n--- System State ---")
            for r in rows:
                print(f"{r[0]}: {r[1]}")
        except sqlite3.OperationalError:
             print("\n[WARNING] system_state table not found.")

        # Check age distribution
        print("\n--- Deal Freshness (last_seen_utc) ---")
        now_utc = datetime.now(timezone.utc)

        try:
            cursor.execute("SELECT last_seen_utc FROM deals")
            rows = cursor.fetchall()

            age_dist = {
                '< 1h': 0,
                '1-24h': 0,
                '24-48h': 0,
                '48-72h': 0,
                '> 72h': 0
            }

            valid_dates = 0
            for r in rows:
                ts_str = r[0]
                if not ts_str: continue
                try:
                    # Handle ISO strings with Z or offset
                    ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                    # Ensure aware
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)

                    age = now_utc - ts
                    hours = age.total_seconds() / 3600

                    if hours < 1: age_dist['< 1h'] += 1
                    elif hours < 24: age_dist['1-24h'] += 1
                    elif hours < 48: age_dist['24-48h'] += 1
                    elif hours < 72: age_dist['48-72h'] += 1
                    else: age_dist['> 72h'] += 1
                    valid_dates += 1
                except Exception:
                    pass

            for k, v in age_dist.items():
                print(f"{k}: {v}")

            if valid_dates > 0 and age_dist['< 1h'] == 0:
                # Check for Backfill Lock to provide context
                backfill_active = False
                if REDIS_AVAILABLE:
                    try:
                        r = redis.Redis.from_url('redis://127.0.0.1:6379/0', socket_connect_timeout=2)
                        if r.exists("backfill_deals_lock"):
                            backfill_active = True
                    except:
                        pass

                if backfill_active:
                    print("[INFO] No deals seen in the last hour, but Backfill Lock is active. Ingestion is paused for backfill (Expected).")
                else:
                    print("[WARNING] No deals seen in the last hour. Ingestion is STALLED.")
        except sqlite3.OperationalError:
             print("[WARNING] Could not check deal age.")

        conn.close()
    except Exception as e:
        print(f"[ERROR] DB check failed: {e}")

def main():
    print("Running Comprehensive Health Check (v2 - Log Logic Fixed)...")
    print(f"Time (UTC): {datetime.now(timezone.utc)}")

    check_code_version()
    check_celery_processes()
    check_redis_locks()
    check_token_status()
    analyze_active_logs()
    check_db_health()

    print_header("DIAGNOSIS COMPLETE")

if __name__ == "__main__":
    main()
