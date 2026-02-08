
import os
import sys
import logging
import sqlite3
import json
from datetime import datetime
from dotenv import load_dotenv

# Add repo root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals.keepa_api import fetch_product_batch
from keepa_deals.processing import _process_single_deal
from keepa_deals.db_utils import DB_PATH

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_db_health():
    logger.info("--- Checking Database Health ---")
    if not os.path.exists(DB_PATH):
        logger.error(f"Database not found at {DB_PATH}")
        return

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # Count
        c.execute("SELECT COUNT(*) FROM deals")
        count = c.fetchone()[0]
        logger.info(f"Total Deals in DB: {count}")

        # Newest
        c.execute("SELECT MAX(last_seen_utc) FROM deals")
        newest = c.fetchone()[0]
        logger.info(f"Newest Deal Timestamp (last_seen_utc): {newest}")

        conn.close()
    except Exception as e:
        logger.error(f"DB Check Failed: {e}")

def test_deal_processing(asin):
    logger.info(f"--- Testing Processing Logic for ASIN: {asin} ---")
    load_dotenv()
    api_key = os.getenv("KEEPA_API_KEY")
    xai_api_key = os.getenv("XAI_TOKEN")

    if not api_key:
        logger.error("KEEPA_API_KEY not found in .env")
        return

    # Fetch
    logger.info("Fetching full product data from Keepa...")
    # Mocking TokenManager by passing None (ignoring rate limits for this single diagnostic call)
    response, _, _, _ = fetch_product_batch(api_key, [asin], days=365, history=1, offers=20)

    if not response or 'products' not in response or not response['products']:
        logger.error("Keepa returned no product data.")
        return

    product_data = response['products'][0]
    logger.info(f"Successfully fetched data for {product_data.get('title')}")

    # Process
    logger.info("Running _process_single_deal...")

    # Mock cache
    seller_cache = {}

    # Capture logs from processing
    # We can't easily capture the logger output from another module without complex setup,
    # so we will rely on the return value and inspect the product_data logic manually if needed.

    result = _process_single_deal(product_data, seller_cache, xai_api_key)

    if result:
        logger.info("SUCCESS: Deal was accepted.")
        logger.info(f"Title: {result.get('Title')}")
        logger.info(f"List at: {result.get('List at')}")
        logger.info(f"1yr. Avg.: {result.get('1yr. Avg.')}")
        logger.info(f"Price Now: {result.get('Price Now')}")
        logger.info(f"Profit: {result.get('Profit')}")
        logger.info(f"Margin: {result.get('Margin')}")
    else:
        logger.error("FAILURE: Deal was REJECTED.")
        # Try to diagnose why by inspecting raw data
        logger.info("--- Diagnostic Data Dump ---")

        # Check Critical Fields
        import keepa_deals.stable_calculations as sc
        sale_events, _ = sc.infer_sale_events(product_data)
        logger.info(f"Inferred Sale Events Found: {len(sale_events)}")

        if len(sale_events) > 0:
            logger.info(f"Sample Sale Event: {sale_events[0]}")

        # Check List At
        # We can't easily call the inner logic, but we can infer.
        if len(sale_events) == 0:
            logger.error("Reason: No inferred sales found (Rank Drops + Offer Drops).")

        # Check Profit
        # ...

if __name__ == "__main__":
    check_db_health()
    test_deal_processing("1455616133") # The known good ASIN
