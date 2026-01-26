import os
import sys
import sqlite3
import redis
import json
import subprocess
from datetime import datetime, timedelta, timezone

# Add parent directory to path to allow imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import DB_PATH from keepa_deals.db_utils
# We'll try to import, but if it fails due to environment, we'll hardcode/guess
try:
    from keepa_deals.db_utils import DB_PATH
except ImportError:
    DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'deals.db')

# Version Check: Diagnostic Tool
def get_redis_client():
    return redis.Redis.from_url('redis://127.0.0.1:6379/0')

def check_scheduler_process():
    """Checks if Celery Beat (scheduler) is running."""
    try:
        # pgrep -f matches the full command line
        result = subprocess.run(['pgrep', '-f', 'celery beat'], capture_output=True, text=True)
        return result.returncode == 0
    except Exception:
        return False

def check_locks(r):
    print("\n--- LOCK STATUS ---")

    # Check Backfill Lock
    backfill_lock_key = "backfill_deals_lock"
    backfill_ttl = r.ttl(backfill_lock_key)
    if backfill_ttl == -2:
        print(f"[FREE] Backfill Lock ({backfill_lock_key}) is NOT held.")
        backfill_active = False
    else:
        print(f"[LOCKED] Backfill Lock ({backfill_lock_key}) IS held. TTL: {backfill_ttl} seconds remaining.")
        backfill_active = True

    # Check Upserter Lock
    upserter_lock_key = "update_recent_deals_lock"
    upserter_ttl = r.ttl(upserter_lock_key)
    if upserter_ttl == -2:
        print(f"[FREE] Upserter Lock ({upserter_lock_key}) is NOT held.")
    else:
        print(f"[LOCKED] Upserter Lock ({upserter_lock_key}) IS held. TTL: {upserter_ttl} seconds remaining.")

    return backfill_active

def analyze_db_state():
    print("\n--- DATABASE STATE ---")
    if not os.path.exists(DB_PATH):
        print(f"ERROR: Database not found at {DB_PATH}")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # 1. Total Deals
        cursor.execute("SELECT COUNT(*) FROM deals")
        total_deals = cursor.fetchone()[0]
        print(f"Total Deals: {total_deals}")

        if total_deals == 0:
            print("Database is empty.")
            return

        # 2. System State (Backfill Page)
        try:
            cursor.execute("SELECT value FROM system_state WHERE key = 'backfill_page'")
            row = cursor.fetchone()
            backfill_page = row[0] if row else "Not Found"
            print(f"Current Backfill Page: {backfill_page}")
        except sqlite3.OperationalError:
            print("Could not read system_state table (might not exist).")

        # 3. Watermark
        try:
            cursor.execute("SELECT value FROM system_state WHERE key = 'watermark_iso'")
            row = cursor.fetchone()
            watermark = row[0] if row else "Not Found"
            print(f"Current Watermark: {watermark}")
        except sqlite3.OperationalError:
            pass

        # 4. Age Analysis
        print("\n--- DEAL AGE ANALYSIS (last_seen_utc) ---")
        cursor.execute("SELECT last_seen_utc FROM deals")
        timestamps = []
        invalid_ts = 0
        now = datetime.now(timezone.utc)

        for (ts_str,) in cursor.fetchall():
            if not ts_str:
                invalid_ts += 1
                continue
            try:
                # Handle varying ISO formats if necessary
                dt = datetime.fromisoformat(ts_str)
                # Ensure timezone aware
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                timestamps.append(dt)
            except ValueError:
                invalid_ts += 1

        if invalid_ts:
            print(f"WARNING: {invalid_ts} deals have invalid/missing timestamps.")

        if not timestamps:
            print("No valid timestamps found.")
            return

        ages_hours = [(now - dt).total_seconds() / 3600 for dt in timestamps]

        # Buckets
        buckets = {
            "< 1 hour": 0,
            "1 - 24 hours": 0,
            "24 - 48 hours": 0,
            "48 - 70 hours": 0,
            "> 70 hours (DANGER ZONE)": 0,
            "> 72 hours (EXPIRED/JANITOR)": 0
        }

        oldest_age = 0
        newest_age = 999999

        for age in ages_hours:
            if age > oldest_age: oldest_age = age
            if age < newest_age: newest_age = age

            if age < 1: buckets["< 1 hour"] += 1
            elif age < 24: buckets["1 - 24 hours"] += 1
            elif age < 48: buckets["24 - 48 hours"] += 1
            elif age < 70: buckets["48 - 70 hours"] += 1
            elif age < 72: buckets["> 70 hours (DANGER ZONE)"] += 1
            else: buckets["> 72 hours (EXPIRED/JANITOR)"] += 1

        for label, count in buckets.items():
            print(f"{label}: {count}")

        print(f"\nNewest Deal Age: {newest_age:.2f} hours")
        print(f"Oldest Deal Age: {oldest_age:.2f} hours")

    except Exception as e:
        print(f"Error analyzing database: {e}")
    finally:
        if conn: conn.close()

def main():
    print("Running Diagnostic Script: diagnose_dwindling_deals.py")
    print(f"Time (UTC): {datetime.now(timezone.utc)}")

    r = get_redis_client()
    try:
        r.ping()
        print("Redis connection successful.")
    except redis.ConnectionError:
        print("ERROR: Could not connect to Redis.")
        return

    backfill_active = check_locks(r)
    analyze_db_state()

    print("\n--- DIAGNOSIS SUMMARY ---")

    scheduler_running = check_scheduler_process()
    if scheduler_running:
        print(f"[OK] Scheduled Upserter (Celery Beat) is RUNNING.")
    else:
        print(f"[WARNING] Scheduled Upserter (Celery Beat) is NOT RUNNING.")

    if backfill_active:
        print("1. The BACKFILLER is currently RUNNING (Lock held).")
        print("   -> This blocks the Upserter (Simple Task) from running.")
        print("   -> New deals will NOT be collected while Backfiller runs.")
    else:
        print("1. The Backfiller is NOT running.")
        print("   -> The Upserter should be able to run (if scheduled).")

    print("\nRECOMMENDATION:")
    print("Check the 'Deal Age' distribution above.")
    print("- If many deals are > 70 hours, the Backfiller is too slow or stuck, and Janitor will delete them soon.")
    print("- If 'Backfill Lock' is held for hours/days without 'Current Backfill Page' changing, the Backfiller is stuck.")

if __name__ == "__main__":
    main()
