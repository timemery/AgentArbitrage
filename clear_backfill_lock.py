import sys
import os
import redis
from dotenv import load_dotenv

# Load environment variables (to ensure we have the right config if needed, though mostly for Redis URL)
load_dotenv()

def clear_lock():
    redis_url = os.getenv('CELERY_BROKER_URL', 'redis://127.0.0.1:6379/0')
    print(f"Connecting to Redis at {redis_url}...")
    
    try:
        r = redis.Redis.from_url(redis_url)
        lock_key = "backfill_deals_lock"
        
        # Check if lock exists
        lock_val = r.get(lock_key)
        if lock_val:
            print(f"Lock '{lock_key}' FOUND. Value: {lock_val}")
            print("Deleting lock...")
            r.delete(lock_key)
            print("Lock deleted successfully.")
        else:
            print(f"Lock '{lock_key}' NOT FOUND. No action needed.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    clear_lock()
