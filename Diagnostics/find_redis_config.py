import redis
import logging
import os
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def find_redis_config():
    redis_url = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')
    try:
        r = redis.Redis.from_url(redis_url, decode_responses=True)

        # 1. Ask Redis where it stores data
        try:
            config_dir = r.config_get('dir').get('dir')
            db_filename = r.config_get('dbfilename').get('dbfilename')
            full_path = os.path.join(config_dir, db_filename)

            logger.info(f"--- REDIS CONFIGURATION ---")
            logger.info(f"Data Directory:  {config_dir}")
            logger.info(f"DB Filename:     {db_filename}")
            logger.info(f"Full Dump Path:  {full_path}")

            if os.path.exists(full_path):
                 logger.info(f"✅ Verified: File exists on disk.")
            else:
                 logger.info(f"❌ Warning: File path returned by config does not exist. Permissions issue?")

        except Exception as e:
            logger.error(f"Could not retrieve CONFIG from Redis (might be restricted): {e}")

        # 2. Check currently held locks
        logger.info(f"\n--- ACTIVE LOCKS ---")
        locks = [
            "backfill_deals_lock",
            "update_recent_deals_lock",
            "homogenization_status"
        ]
        for lock in locks:
            if r.exists(lock):
                ttl = r.ttl(lock)
                logger.info(f"[LOCKED] {lock} (TTL: {ttl}s)")
            else:
                logger.info(f"[FREE]   {lock}")

    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")

if __name__ == "__main__":
    find_redis_config()
