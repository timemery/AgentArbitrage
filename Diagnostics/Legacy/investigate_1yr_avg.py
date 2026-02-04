import os
import sys
import logging
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add repository root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals.keepa_api import fetch_deals_for_deals
from keepa_deals.stable_calculations import infer_sale_events
from keepa_deals.new_analytics import get_1yr_avg_sale_price
from keepa_deals.token_manager import TokenManager

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    logger.info("Starting investigation of 'Missing 1yr Avg'...")

    # Load .env
    load_dotenv()
    api_key = os.getenv('KEEPA_API_KEY')
    if not api_key:
        logger.error("KEEPA_API_KEY not found in .env")
        return

    # Initialize Token Manager
    tm = TokenManager(api_key=api_key)

    # Fetch a batch of deals (using existing query)
    # We use a standard fetch which gets full data (stats + csv)
    logger.info("Fetching a page of deals from Keepa...")

    # Corrected function call
    response_data, _, _ = fetch_deals_for_deals(page=0, api_key=api_key, token_manager=tm)

    if not response_data:
        logger.error("Failed to fetch products (API returned None).")
        return

    # Extract the deals list correctly
    products = response_data.get('deals', {}).get('dr', [])

    if not products:
        logger.error("No deals found in API response.")
        return

    logger.info(f"Fetched {len(products)} products. Analyzing...")

    failure_stats = {
        "Total": 0,
        "Success": 0,
        "Fail_NoCSV": 0,
        "Fail_NoRankHistory": 0,
        "Fail_NoOfferDrops": 0,
        "Fail_NoConfirmedSales": 0,
        "Fail_InsufficientSales": 0
    }

    for product in products:
        asin = product.get('asin', 'N/A')
        failure_stats["Total"] += 1

        # Check 1: CSV Data presence
        csv_data = product.get('csv', [])
        if not isinstance(csv_data, list) or len(csv_data) < 13:
            logger.warning(f"ASIN {asin}: FAIL - CSV data missing or incomplete.")
            failure_stats["Fail_NoCSV"] += 1
            continue

        # Check 2: Run Inference
        sale_events, total_offer_drops = infer_sale_events(product)

        if not sale_events:
            # Diagnosis why
            if total_offer_drops == 0:
                logger.warning(f"ASIN {asin}: FAIL - No offer drops found in history.")
                failure_stats["Fail_NoOfferDrops"] += 1
            else:
                logger.warning(f"ASIN {asin}: FAIL - Offer drops found ({total_offer_drops}) but NO confirmed sales (Rank drops match).")
                failure_stats["Fail_NoConfirmedSales"] += 1
            continue

        # Check 3: 1yr Avg specific check
        avg_info = get_1yr_avg_sale_price(product, logger)
        if not avg_info:
             logger.warning(f"ASIN {asin}: FAIL - Sales found ({len(sale_events)}) but insufficient for 1yr Avg (maybe all > 1 yr ago?).")
             failure_stats["Fail_InsufficientSales"] += 1
             continue

        logger.info(f"ASIN {asin}: SUCCESS - 1yr Avg: ${avg_info['1yr. Avg.']:.2f} ({len(sale_events)} sales)")
        failure_stats["Success"] += 1

    logger.info("-" * 30)
    logger.info("INVESTIGATION SUMMARY")
    logger.info(json.dumps(failure_stats, indent=2))
    logger.info("-" * 30)

if __name__ == "__main__":
    main()
