import redis
import os
from dotenv import load_dotenv

load_dotenv()

def force_resume():
    print("--- FORCING RESUME OF DEAL COLLECTION ---")

    redis_url = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')
    try:
        r = redis.Redis.from_url(redis_url, decode_responses=True)
        r.ping()
        print("Connected to Redis.")
    except Exception as e:
        print(f"[ERROR] Could not connect to Redis: {e}")
        return

    KEY_RECHARGE = "keepa_recharge_mode_active"
    KEY_START_TIME = "keepa_recharge_start_time"

    # Check current state
    if r.exists(KEY_RECHARGE):
        print(f"Recharge Mode Key Found: {r.get(KEY_RECHARGE)}")
        r.delete(KEY_RECHARGE)
        print("Deleted 'keepa_recharge_mode_active'.")
    else:
        print("Recharge Mode Key NOT found (Already running?).")

    if r.exists(KEY_START_TIME):
        print(f"Recharge Start Time Found: {r.get(KEY_START_TIME)}")
        r.delete(KEY_START_TIME)
        print("Deleted 'keepa_recharge_start_time'.")

    print("System state cleared. Workers should resume immediately on next cycle.")

if __name__ == "__main__":
    force_resume()
