import sqlite3
import json
import os
import logging
import time
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Add project root to Python path to allow module imports
import sys
sys.path.append(os.getcwd())

from keepa_deals.keepa_api import fetch_product_batch, fetch_seller_data
from keepa_deals.seller_info import get_all_seller_info
from keepa_deals.token_manager import TokenManager

def diagnose_seller_issues():
    """
    Diagnoses issues where deals have "No Seller Info" or other related problems by
    re-fetching and re-processing the data for failing ASINs.
    """
    db_path = 'deals.db'
    if not os.path.exists(db_path):
        logger.error(f"Database not found at '{db_path}'. Please run the backfiller first.")
        return

    api_key = os.getenv("KEEPA_API_KEY")
    if not api_key:
        logger.error("KEEPA_API_KEY not found in environment variables.")
        return

    token_manager = TokenManager(api_key)
    token_manager.sync_tokens()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Find a sample of ASINs with the specified issues
    try:
        cursor.execute("""
            SELECT ASIN FROM deals
            WHERE Seller = 'No Seller Info' OR Seller = '-' OR Price_Now = '-'
            LIMIT 10
        """)
        failing_asins = [row['ASIN'] for row in cursor.fetchall()]
    finally:
        conn.close()

    if not failing_asins:
        logger.info("No deals found with 'No Seller Info', '-', or missing 'Price_Now'. Nothing to diagnose.")
        return

    logger.info(f"Found {len(failing_asins)} failing ASINs to investigate: {failing_asins}")

    diagnostic_results = []

    # 1. Fetch all product data for the failing ASINs
    all_fetched_products = {}
    logger.info("Fetching product data for all failing ASINs...")
    product_data_fetched = False
    while not product_data_fetched:
        estimated_cost = 12 * len(failing_asins)  # Rough estimate
        token_manager.request_permission_for_call(estimated_cost)
        product_response, _, _, tokens_left = fetch_product_batch(api_key, failing_asins, history=0, offers=20)
        token_manager.update_after_call(tokens_left)
        if product_response and 'products' in product_response:
            all_fetched_products = {p['asin']: p for p in product_response['products']}
            product_data_fetched = True
            logger.info("Successfully fetched product data.")
        else:
            logger.warning(f"Failed to fetch product data batch (tokens left: {tokens_left}), retrying in 15 seconds...")
            time.sleep(15)

    # 2. Collect all unique seller IDs from all fetched products
    all_unique_seller_ids = set()
    for product in all_fetched_products.values():
        offers = product.get('offers', [])
        if not isinstance(offers, list):
            logger.warning(f"ASIN {product.get('asin')}: 'offers' is not a list, it's a {type(offers)}. Skipping seller ID collection.")
            continue
        for offer in offers:
            if isinstance(offer, dict) and offer.get('sellerId'):
                all_unique_seller_ids.add(offer['sellerId'])

    # 3. Fetch all seller data in batches to build a complete cache
    seller_data_cache = {}
    if all_unique_seller_ids:
        seller_id_list = list(all_unique_seller_ids)
        logger.info(f"Found {len(seller_id_list)} unique seller IDs. Fetching their data in batches...")
        for i in range(0, len(seller_id_list), 100):
            batch_ids = seller_id_list[i:i+100]
            batch_fetched = False
            while not batch_fetched:
                logger.info(f"Attempting to fetch seller data for a batch of {len(batch_ids)} IDs.")
                token_manager.request_permission_for_call(estimated_cost=1)
                seller_data, _, _, tokens_left = fetch_seller_data(api_key, batch_ids)
                token_manager.update_after_call(tokens_left)
                if seller_data and 'sellers' in seller_data and seller_data['sellers']:
                    seller_data_cache.update(seller_data['sellers'])
                    batch_fetched = True
                    logger.info(f"Successfully fetched seller batch. Total sellers in cache: {len(seller_data_cache)}")
                else:
                    logger.warning(f"Failed to fetch a seller batch or data was empty. Tokens left: {tokens_left}. Retrying in 15 seconds...")
                    time.sleep(15)

    # 4. Process each failing ASIN individually using the complete cache
    for asin in failing_asins:
        logger.info(f"--- Diagnosing ASIN: {asin} ---")
        product_data = all_fetched_products.get(asin)

        if not product_data:
            logger.warning(f"Could not find fetched product data for ASIN {asin}. Skipping.")
            continue

        # Re-run the specific logic to determine the best price and seller
        calculated_seller_info = get_all_seller_info(product_data, seller_data_cache)

        diagnostic_results.append({
            "failing_asin": asin,
            "calculated_seller_info": calculated_seller_info,
            "raw_product_data": product_data,
        })
        logger.info(f"Finished diagnosis for ASIN: {asin}")

    # Add the raw seller cache to the final log for full context
    final_log = {
        "diagnosed_asins": diagnostic_results,
        "raw_seller_data_cache": seller_data_cache
    }

    # Write diagnostic results to a file
    output_filename = 'diag_seller_issue_log.json'
    with open(output_filename, 'w') as f:
        json.dump(final_log, f, indent=4)

    logger.info(f"Diagnostic complete. Results saved to '{output_filename}'")

if __name__ == "__main__":
    diagnose_seller_issues()
