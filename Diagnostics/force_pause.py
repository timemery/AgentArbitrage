import redis
import os
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
        print("Set 'keepa_recharge_mode_active' to '1'. System is now PAUSED until tokens reach 280.")

    except Exception as e:
        print(f"[ERROR] Could not connect to Redis: {e}")

if __name__ == "__main__":
    force_pause()
