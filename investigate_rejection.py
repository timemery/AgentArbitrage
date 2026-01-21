import os
import json
import logging
import sys
from dotenv import load_dotenv

# Configure detailed logging to stdout
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', stream=sys.stdout)
logger = logging.getLogger("investigate_rejection")

# Load environment variables
load_dotenv()
keepa_api_key = os.getenv("KEEPA_API_KEY")
xai_api_key = os.getenv("XAI_TOKEN")

if not keepa_api_key:
    logger.error("KEEPA_API_KEY not found in environment.")
    sys.exit(1)

from keepa_deals.keepa_api import fetch_product_batch
from keepa_deals.processing import _process_single_deal

def investigate():
    logger.info("Starting investigation with HARDCODED ASINs...")

    # Selected ASINs:
    # 0743273567 - The Great Gatsby (Classic, High Velocity)
    # 0061122416 - The Alchemist (Classic, High Velocity)
    # 0878873414 - The one that failed previously (Low Velocity, High Price)
    asins = ['0743273567', '0061122416', '0878873414']
    logger.info(f"Selected ASINs for investigation: {asins}")

    # 2. Fetch full product data
    # offers=20, history=1 are crucial for calculations
    product_response, _, _, _ = fetch_product_batch(keepa_api_key, asins, days=365, offers=20, rating=1, history=1)

    if not product_response or 'products' not in product_response:
        logger.error("Failed to fetch product details (Keepa might be out of tokens).")
        return

    products = product_response['products']
    logger.info(f"Fetched details for {len(products)} products.")

    # 3. Process each product
    for product in products:
        asin = product.get('asin')
        title = product.get('title', 'Unknown')
        stats = product.get('stats', {})
        current_rank = stats.get('current', [-1, -1, -1, -1])[3]

        logger.info(f"\n=== Processing ASIN: {asin} ===")
        logger.info(f"Title: {title}")
        logger.info(f"Current Rank: {current_rank}")

        seller_cache = {}

        try:
            result = _process_single_deal(product, seller_cache, xai_api_key)

            if result:
                logger.info(f"✅ SUCCESS: Processed.")
                logger.info(f"   List at: {result.get('List at')}")
                logger.info(f"   Price Now: {result.get('Price Now')}")
                logger.info(f"   Profit Confidence: {result.get('Profit Confidence')}")
                logger.info(f"   1yr. Avg.: {result.get('1yr. Avg.')}")
            else:
                logger.warning(f"❌ REJECTED.")
                # If rejected, we want to know why. processing.py logs it, so it should be in stdout.

        except Exception as e:
            logger.error(f"EXCEPTION: {e}", exc_info=True)

if __name__ == "__main__":
    investigate()
