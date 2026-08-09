import redis
import sqlite3
import os
import sys
import time
from datetime import datetime, timezone

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# Paths
LOG_FILE = "/var/www/agentarbitrage/celery_worker.log"
DB_PATH = "/var/www/agentarbitrage/deals.db"

def check_redis():
    print("\n--- 1. Redis Token State ---")
    try:
        r = redis.Redis.from_url('redis://127.0.0.1:6379/0', decode_responses=True)
        tokens = r.get("keepa_tokens_left")

        if tokens:
            print(f"Current Tokens in Redis: {tokens}")
            if float(tokens) > 0:
                print("✅ [PASS] Tokens are positive. Sync likely occurred.")
                return True
            else:
                print("⚠️ [WARN] Tokens are still negative or zero.")
                return False
        else:
            print("❌ [FAIL] Redis key 'keepa_tokens_left' not found.")
            return False
    except Exception as e:
        print(f"❌ [ERROR] Redis check failed: {e}")
        return False

def check_logs():
    print("\n--- 2. Log Verification (Last 2000 lines) ---")
    if not os.path.exists(LOG_FILE):
        print(f"❌ [ERROR] Log file not found at {LOG_FILE}")
        return False

    try:
        # Use simple file read for last 2000 lines
        with open(LOG_FILE, 'r') as f:
            lines = f.readlines()
            last_lines = lines[-2000:] if len(lines) > 2000 else lines
            output = "".join(last_lines)

        found_sync = "Executing FORCE SYNC" in output
        found_recovery = "Burst threshold reached after Force Sync" in output
        found_upsert = "Upserting" in output
        found_recharge_exit = "Exiting Recharge Mode" in output

        print("Searching for key phrases in logs...")

        if found_sync:
            print("✅ [PASS] Found 'Executing FORCE SYNC' log. Fix logic triggered.")
        else:
            print("ℹ️ [INFO] 'Executing FORCE SYNC' not found. (System might have recovered naturally or not run yet).")

        if found_recovery:
            print("✅ [PASS] Found 'Burst threshold reached after Force Sync'. RECOVERY CONFIRMED.")

        if found_recharge_exit:
            print("✅ [PASS] Found 'Exiting Recharge Mode'. System is active.")

        if found_upsert:
             print("✅ [PASS] Found 'Upserting' logs. Ingestion is active.")

        if not (found_sync or found_recovery or found_upsert or found_recharge_exit):
            print("⚠️ [WARN] No signs of activity/recovery found yet. Wait a few minutes.")
            return False

        return True

    except Exception as e:
        print(f"❌ [ERROR] Log check failed: {e}")
        return False

def check_db_freshness():
    print("\n--- 3. Database Freshness ---")
    if not os.path.exists(DB_PATH):
        print(f"❌ [ERROR] DB file not found at {DB_PATH}")
        return False

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(last_seen_utc) FROM deals")
        result = cursor.fetchone()

        if result and result[0]:
            last_seen_str = result[0]
            print(f"Newest Deal Timestamp: {last_seen_str}")

            # Check if very recent
            last_seen_dt = datetime.fromisoformat(last_seen_str).replace(tzinfo=timezone.utc)
            now_dt = datetime.now(timezone.utc)
            diff = (now_dt - last_seen_dt).total_seconds() / 60

            print(f"Age: {diff:.1f} minutes ago")

            if diff < 15:
                print("✅ [PASS] Deal ingestion is active (updated < 15 mins ago).")
                return True
            else:
                print("⚠️ [WARN] Latest deal is older than 15 minutes.")
                return False
        else:
            print("⚠️ [WARN] No deals found in DB.")
            return False

    except Exception as e:
        print(f"❌ [ERROR] DB check failed: {e}")
        return False

def main():
    print("=== Verification of Fix: Recharge Loop Recovery ===")
    print("Run this script ~5 minutes after deployment.")

    redis_ok = check_redis()
    logs_ok = check_logs()
    db_ok = check_db_freshness()

    print("\n--- SUMMARY ---")
    if redis_ok and (logs_ok or db_ok):
        print("✅ SUCCESS: The fix appears to be working. System recovered from recharge loop.")
    else:
        print("⚠️ INCONCLUSIVE / FAIL: Check individual sections above.")

if __name__ == "__main__":
    main()
