import os
import sys
import json
import logging
from dotenv import load_dotenv

# Add the project root to the Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from keepa_deals.keepa_api import fetch_product_batch, fetch_seller_data
from keepa_deals.seller_info import get_all_seller_info
from keepa_deals.processing import _process_single_deal

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Load environment variables
load_dotenv()
KEEPA_API_KEY = os.getenv("KEEPA_API_KEY")

if not KEEPA_API_KEY:
    logging.error("KEEPA_API_KEY not found in .env file.")
    sys.exit(1)

def run_diagnostic(asin):
    """
    Runs a diagnostic trace on a single ASIN to identify where seller info is lost.
    """
    if not asin:
        logging.error("Please provide an ASIN.")
        return

    logging.info(f"--- STARTING DIAGNOSTIC FOR ASIN: {asin} ---")

    # 1. Fetch raw product data
    logging.info("\n--- STEP 1: Fetching raw product data from Keepa API ---")
    product_data, api_info, tokens_consumed, tokens_left = fetch_product_batch(KEEPA_API_KEY, [asin])
    if not product_data or not product_data.get('products'):
        logging.error(f"Failed to fetch product data for ASIN {asin}. Response: {product_data}")
        return

    raw_product = product_data['products'][0]

    # Dump the entire raw product data to a file for forensic analysis
    dump_filepath = 'raw_asin_dump.json'
    logging.info(f"Dumping full raw product data to '{dump_filepath}'")
    with open(dump_filepath, 'w') as f:
        json.dump(raw_product, f, indent=2, default=str)

    print(f"\nFull raw product data for ASIN {asin} has been saved to {dump_filepath}")


    # 2. Build seller cache (mimicking the real process)
    logging.info("\n--- STEP 2: Building seller data cache ---")
    seller_ids = set()
    offers = raw_product.get('offers', [])
    if offers:
        for offer in offers:
            if isinstance(offer, dict) and 'sellerId' in offer:
                seller_ids.add(offer['sellerId'])

    seller_data_cache = {}
    if seller_ids:
        logging.info(f"Found {len(seller_ids)} unique seller IDs. Fetching their data.")
        seller_data_list, _, _, _ = fetch_seller_data(KEEPA_API_KEY, list(seller_ids))
        if seller_data_list and 'sellers' in seller_data_list:
             for seller_id, seller_info in seller_data_list['sellers'].items():
                 seller_data_cache[seller_id] = seller_info
        logging.info("Seller cache built.")
    else:
        logging.info("No live offers found to build seller cache from.")


    # 3. Initial analysis from seller_info.py
    logging.info("\n--- STEP 3: Running get_all_seller_info() ---")
    seller_info_result = get_all_seller_info(raw_product, seller_data_cache)
    print("\nOutput of get_all_seller_info():")
    print(json.dumps(seller_info_result, indent=2))
    if seller_info_result.get('Seller') in ['-', 'No Seller Info', '(Price from Keepa stats)']:
         logging.warning("Seller info is already missing or ambiguous at the initial processing stage.")


    # 4. Final processing from processing.py
    logging.info("\n--- STEP 4: Running _process_single_deal() ---")
    try:
        with open('settings.json', 'r') as f:
            business_settings = json.load(f)
    except FileNotFoundError:
        logging.error("settings.json not found. Cannot proceed.")
        return
    # This function requires the full list of headers/functions
    try:
        with open('keepa_deals/headers.json', 'r') as f:
            headers = json.load(f)
    except FileNotFoundError:
        logging.error("headers.json not found. Cannot proceed.")
        return
    # The function mutates the product object and also returns a dict
    final_processed_data = _process_single_deal(raw_product, seller_data_cache, os.getenv("XAI_TOKEN"), business_settings, headers)

    print("\nFinal processed data dictionary (subset of relevant fields):")
    relevant_keys = [
        "Price Now", "Seller", "Seller ID", "Seller_Quality_Score", "Trust", "List at",
        "All-in Cost", "Profit", "Margin", "Detailed_Seasonality", "Sells"
    ]

    final_output = {}
    for key in relevant_keys:
        final_output[key] = final_processed_data.get(key, 'NOT FOUND')


    print(json.dumps(final_output, indent=2))

    logging.info("\n--- DIAGNOSTIC COMPLETE ---")
    if final_output.get("Seller") in ['-', 'No Seller Info', '(Price from Keepa stats)', 'NOT FOUND']:
        logging.error("FAIL: Final processed data is missing seller information.")
    else:
        logging.info("SUCCESS: Seller information appears to be present in the final processed data.")


if __name__ == "__main__":
    # Check if an ASIN is provided as a command-line argument
    if len(sys.argv) > 1:
        input_asin = sys.argv[1]
    else:
        # Use a default ASIN if none is provided
        input_asin = "0964953005" # An ASIN known to have caused issues
        logging.warning(f"No ASIN provided. Using default: {input_asin}")

    run_diagnostic(input_asin)
