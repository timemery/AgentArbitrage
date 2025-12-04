# diag_seller_info.py
import os
import json
from dotenv import load_dotenv
from keepa_deals.keepa_api import fetch_product_batch, fetch_seller_data
from keepa_deals.seller_info import get_all_seller_info

# Load environment variables
load_dotenv()

# --- Configuration ---
ASIN_TO_TEST = '0375970746'  # A known ASIN from the previous logs
API_KEY = os.getenv("KEEPA_API_KEY")

def run_diagnostic():
    """
    Fetches data for a single ASIN and inspects the output of get_all_seller_info.
    """
    print("--- Running Seller Info Diagnostic ---")

    if not API_KEY:
        print("ERROR: KEEPA_API_KEY not found in .env file.")
        return

    # 1. Fetch product data
    print(f"Fetching product data for ASIN: {ASIN_TO_TEST}...")
    product_response, _, _, _ = fetch_product_batch(API_KEY, [ASIN_TO_TEST], history=1, offers=20)

    if not product_response or 'products' not in product_response or not product_response['products']:
        print("ERROR: Failed to fetch product data.")
        return

    product_data = product_response['products'][0]
    print("Product data fetched successfully.")

    # 2. Pre-fetch seller data (mimicking the backfiller task)
    print("Fetching seller data...")
    unique_seller_ids = set()
    for offer in product_data.get('offers', []):
        if offer.get('sellerId'):
            unique_seller_ids.add(offer['sellerId'])

    seller_data_cache = {}
    if unique_seller_ids:
        seller_id_list = list(unique_seller_ids)
        seller_data, _, _, _ = fetch_seller_data(API_KEY, seller_id_list)
        if seller_data and 'sellers' in seller_data:
            seller_data_cache.update(seller_data['sellers'])
            print(f"Fetched data for {len(seller_data_cache)} unique sellers.")
    else:
        print("No seller IDs found in offers to fetch.")

    # 3. Run the target function
    print("\n--- Testing get_all_seller_info() ---")
    seller_info_output = get_all_seller_info(product_data, seller_data_cache)

    # 4. Print the raw output
    print("\nRaw output from get_all_seller_info:")
    print(json.dumps(seller_info_output, indent=2))
    print("\n--- Diagnostic Complete ---")

if __name__ == "__main__":
    run_diagnostic()
