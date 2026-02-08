
import os
import sys
import logging
import json
from dotenv import load_dotenv

# Add repo root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals.keepa_api import fetch_current_stats_batch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def inspect_peek(asin):
    load_dotenv()
    api_key = os.getenv("KEEPA_API_KEY")
    if not api_key:
        logger.error("No API Key")
        return

    logger.info(f"Peeking at {asin}...")
    # Mock TokenManager
    response, _, _, _ = fetch_current_stats_batch(api_key, [asin], days=90)

    if response and 'products' in response:
        prod = response['products'][0]
        logger.info("--- Peek Data ---")
        logger.info(f"Title: {prod.get('title')}")

        stats = prod.get('stats', {})
        current = stats.get('current', [])
        avg90 = stats.get('avg90', [])

        # Keepa Indices:
        # 0: Amazon
        # 1: New
        # 2: Used

        logger.info(f"Current Amazon: {current[0] if len(current) > 0 else '?'}")
        logger.info(f"Current New: {current[1] if len(current) > 1 else '?'}")
        logger.info(f"Current Used: {current[2] if len(current) > 2 else '?'}")

        logger.info(f"Avg90 Amazon: {avg90[0] if len(avg90) > 0 else '?'}")
        logger.info(f"Avg90 New: {avg90[1] if len(avg90) > 1 else '?'}")
        logger.info(f"Avg90 Used: {avg90[2] if len(avg90) > 2 else '?'}")

    else:
        logger.error("No data returned")

if __name__ == "__main__":
    inspect_peek("1455616133")
