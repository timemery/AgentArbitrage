import redis
import os
import time
from dotenv import load_dotenv

load_dotenv()

def force_pause():
    print("--- Checking Deployment State ---")

    redis_url = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')
    try:
        r = redis.Redis.from_url(redis_url, decode_responses=True)
        r.ping()

        # Check if we are doing a "Hot Swap" (Update while running) vs "Fresh Start"
        # If the Smart Ingestor lock was active recently, maybe we don't need a full pause?
        # BUT: deploy_update.sh calls kill_everything_force.sh which WIPES Redis.
        # So we can't rely on old keys.

        # However, to be safe against Livelock (restarting with 40 tokens and burning them instantly),
        # we MUST enforce the pause on a fresh boot.

        # Set the key to '1' (Active)
        r.set("keepa_recharge_mode_active", "1")

        # Set the start time for timeout detection
        start_time = time.time()
        r.set("keepa_recharge_start_time", str(start_time))

        print(f"Set 'keepa_recharge_mode_active' to '1'. System is now PAUSED until tokens reach Burst Threshold.")
        print(f"Set 'keepa_recharge_start_time' to {start_time}. Timeout set to 60 minutes.")
        print("NOTE: This pause is CRITICAL to prevent token starvation loops on restart.")

    except Exception as e:
        print(f"[ERROR] Could not connect to Redis: {e}")

if __name__ == "__main__":
    force_pause()
