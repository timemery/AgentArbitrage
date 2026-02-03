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

def nuclear_redis_wipe():
    redis_url = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')
    logger.info(f"Connecting to Redis at: {redis_url}")

    try:
        r = redis.Redis.from_url(redis_url, decode_responses=True)

        # 1. Test Connection
        try:
            r.ping()
            logger.info("✅ Redis Connection Successful.")
        except redis.exceptions.AuthenticationError:
            logger.error("❌ Authentication Failed. Check REDIS_URL/password.")
            sys.exit(1)
        except Exception as e:
            logger.error(f"❌ Connection Failed: {e}")
            sys.exit(1)

        # 2. FLUSHALL
        logger.info("💥 Executing FLUSHALL (Wiping Memory)...")
        r.flushall()
        logger.info("✅ FLUSHALL Complete.")

        # 3. SAVE
        logger.info("💾 Executing SAVE (Persisting Empty State)...")
        try:
            r.save()
            logger.info("✅ SAVE Complete. Disk is now clean.")
        except redis.exceptions.ResponseError as e:
            logger.warning(f"⚠️ SAVE Failed (Background save might be running): {e}")
            # Try BGSAVE if SAVE fails, though we prefer sync SAVE for kill scripts
            try:
                r.bgsave()
                logger.info("✅ BGSAVE Triggered instead.")
            except:
                pass

    except Exception as e:
        logger.error(f"❌ Critical Error during wipe: {e}")
        sys.exit(1)

if __name__ == "__main__":
    nuclear_redis_wipe()
