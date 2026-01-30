import redis
import sys
import os

def clear_locks():
    print("Connecting to Redis...")
    try:
        r = redis.Redis.from_url('redis://127.0.0.1:6379/0')
        r.ping()
        print("Connected.")

        locks = ["backfill_deals_lock", "update_recent_deals_lock"]
        for lock in locks:
            if r.exists(lock):
                print(f"Deleting lock: {lock}")
                r.delete(lock)
            else:
                print(f"Lock not found (already free): {lock}")

        print("\nAll locks cleared.")

    except Exception as e:
        print(f"Error clearing locks: {e}")
        sys.exit(1)

if __name__ == "__main__":
    clear_locks()
