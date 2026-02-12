import os
import sys
import logging
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals.keepa_api import fetch_product_batch
from keepa_deals.new_analytics import get_1yr_avg_sale_price

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test():
    load_dotenv()
    api_key = os.getenv("KEEPA_API_KEY")
    asin = "1454919108"

    logger.info(f"Fetching {asin}...")
    response, _, _, _ = fetch_product_batch(api_key, [asin], days=365, history=1, offers=20)

    if not response or 'products' not in response:
        logger.error("Failed fetch")
        return

    product = response['products'][0]

    # Dump relevant stats for debugging
    stats = product.get('stats', {})
    avg365 = stats.get('avg365', [])
    logger.info(f"Stats - avg365[2] (Used): {avg365[2] if len(avg365)>2 else 'N/A'}")
    logger.info(f"Stats - avg365[21] (Used-Good): {avg365[21] if len(avg365)>21 else 'N/A'}")

    logger.info("Testing get_1yr_avg_sale_price...")
    result = get_1yr_avg_sale_price(product, logger)
    logger.info(f"Result: {result}")

    if result is None:
        logger.error("Returned None!")
    else:
        logger.info("Success!")

if __name__ == "__main__":
    test()
