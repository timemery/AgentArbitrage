import redis
import logging
import os
import sys
from dotenv import load_dotenv

# Explicitly load .env from the project root
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(project_root, '.env'))

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

LOCK_KEYS = [
    "backfill_deals_lock",
    "update_recent_deals_lock"
]

def force_clear_locks():
    redis_url = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')
    logger.info(f"Connecting to Redis at: {redis_url} to clear specific locks.")

    try:
        r = redis.Redis.from_url(redis_url, decode_responses=True)

        # 1. Test Connection
        try:
            r.ping()
        except Exception as e:
            logger.error(f"❌ Connection Failed: {e}")
            sys.exit(1)

        # 2. Delete Locks
        for key in LOCK_KEYS:
            if r.exists(key):
                r.delete(key)
                logger.info(f"✅ Deleted lock key: {key}")
            else:
                logger.info(f"ℹ️ Lock key not found (already clean): {key}")

    except Exception as e:
        logger.error(f"❌ Error clearing locks: {e}")
        sys.exit(1)

if __name__ == "__main__":
    force_clear_locks()
