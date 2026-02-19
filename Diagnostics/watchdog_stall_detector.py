import os
import time
import redis
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Watchdog")

load_dotenv()

def check_for_stalls():
    redis_url = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')
    try:
        r = redis.Redis.from_url(redis_url, decode_responses=True)
        r.ping()
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        return

    # Constants
    STALL_THRESHOLD_TOKENS = 290 # Near Max
    STALL_TIMEOUT_SECONDS = 900  # 15 minutes

    # 1. Get Token Count
    tokens_str = r.get("keepa_tokens_left")
    if not tokens_str:
        logger.info("No token data in Redis. Skipping check.")
        return

    tokens = float(tokens_str)

    # 2. Get Last Heartbeat
    last_heartbeat_str = r.get("keepa_worker_last_heartbeat")
    if not last_heartbeat_str:
        logger.info("No heartbeat data in Redis. System might be cold.")
        return

    last_heartbeat = float(last_heartbeat_str)
    elapsed = time.time() - last_heartbeat

    logger.info(f"Status Check: Tokens={tokens:.2f}, Time since heartbeat={elapsed:.1f}s")

    # 3. Detection Logic
    # If tokens are full (meaning no one is using them) AND heartbeat is old (meaning worker is silent)
    if tokens > STALL_THRESHOLD_TOKENS and elapsed > STALL_TIMEOUT_SECONDS:
        logger.error(f"STALL DETECTED! Tokens ({tokens:.2f}) > {STALL_THRESHOLD_TOKENS} AND Heartbeat silent for {elapsed:.1f}s.")
        logger.error("RECOMMENDATION: Run 'kill_everything_force.sh' to restart the system.")

        # Trigger automated recovery
        logger.warning("Initiating automated system restart...")
        os.system("./kill_everything_force.sh")
    else:
        logger.info("System appears healthy.")

if __name__ == "__main__":
    check_for_stalls()
