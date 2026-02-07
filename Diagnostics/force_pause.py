import redis
import os
import time
from dotenv import load_dotenv

load_dotenv()

def force_pause():
    print("--- Forcing Recharge Mode (Pause) ---")

    redis_url = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')
    try:
        r = redis.Redis.from_url(redis_url, decode_responses=True)
        r.ping()

        # Set the key to '1' (Active)
        r.set("keepa_recharge_mode_active", "1")

        # Set the start time for timeout detection
        start_time = time.time()
        r.set("keepa_recharge_start_time", str(start_time))

        print(f"Set 'keepa_recharge_mode_active' to '1'. System is now PAUSED until tokens reach 280.")
        print(f"Set 'keepa_recharge_start_time' to {start_time}. Timeout set to 60 minutes.")

    except Exception as e:
        print(f"[ERROR] Could not connect to Redis: {e}")

if __name__ == "__main__":
    force_pause()
