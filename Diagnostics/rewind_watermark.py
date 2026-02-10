
import os
import sys
import sqlite3
import redis
from datetime import datetime, timedelta, timezone

# Add repo root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals.db_utils import load_watermark, save_watermark, DB_PATH
from keepa_deals.smart_ingestor import LOCK_KEY

def main():
    print("--- Watermark Rewind Tool ---")

    # 1. Check current watermark
    current_wm = load_watermark()
    print(f"Current Watermark: {current_wm}")

    if not current_wm:
        print("No watermark found! Nothing to rewind.")
        return

    # 2. Calculate rewind target (24 hours ago)
    # If watermark is recent, rewind 24h from *now*.
    # If watermark is old, we might just want to leave it? No, user wants data NOW.
    # Safe bet: Set it to 24 hours ago from NOW to catch anything missed recently.

    now_utc = datetime.now(timezone.utc)
    target_time = now_utc - timedelta(hours=24)
    target_iso = target_time.isoformat()

    print(f"Target Watermark (24h ago): {target_iso}")

    # 3. Apply Rewind
    print("Rewinding watermark...")
    save_watermark(target_iso)

    # 4. Verify
    new_wm = load_watermark()
    print(f"New Watermark in DB: {new_wm}")

    if new_wm == target_iso:
        print("SUCCESS: Watermark rewound.")
    else:
        print("FAILURE: Watermark update failed.")

    # 5. Clear Redis Lock to force immediate run?
    # The diagnostic showed lock was free (in the second run), but let's be safe.
    try:
        r = redis.Redis.from_url('redis://localhost:6379/0')
        if r.get(LOCK_KEY):
            print("Clearing Smart Ingestor Lock to ensure immediate pickup...")
            r.delete(LOCK_KEY)
            print("Lock cleared.")
        else:
            print("Smart Ingestor Lock is already free.")
    except Exception as e:
        print(f"Redis error (non-critical): {e}")

if __name__ == "__main__":
    main()
