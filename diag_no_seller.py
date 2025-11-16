import sqlite3
import os
import json
import logging
from dotenv import load_dotenv
from keepa_deals.keepa_api import fetch_product_batch, fetch_seller_data
from keepa_deals.seller_info import get_all_seller_info
from keepa_deals.token_manager import TokenManager

# --- Configuration ---
DB_PATH = 'deals.db'
TABLE_NAME = 'deals'
LOG_FILE = 'diag_no_seller_log.json'
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_diagnostic():
    """
    Diagnoses the "No Seller Info" issue by fetching and processing data for specific ASINs
    found in the local database.
    """
    load_dotenv()
    api_key = os.getenv("KEEPA_API_KEY")
    if not api_key:
        logging.error("KEEPA_API_KEY not found in .env file. Aborting.")
        return

    token_manager = TokenManager(api_key)
    token_manager.sync_tokens()

    # Wait if we are in a token deficit
    if token_manager.tokens <= 0:
        wait_time = token_manager.get_refill_time_in_seconds(1)
        logging.warning(f"Initial token balance is {token_manager.tokens}. Waiting {wait_time} seconds to ensure a positive balance.")
        time.sleep(wait_time)

    # 1. Find 5 ASINs with "No Seller Info" from the local database
    logging.info(f"Connecting to database at '{DB_PATH}' to find failing ASINs...")
    asin_to_test = []
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # The column name is sanitized in the db, so we use the sanitized version.
        cursor.execute(f"SELECT ASIN FROM {TABLE_NAME} WHERE Seller = 'No Seller Info' LIMIT 5")
        rows = cursor.fetchall()
        asin_to_test = [row[0] for row in rows]
        conn.close()
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        return

    if not asin_to_test:
        logging.warning("No ASINs with 'No Seller Info' found in the database.")
        return

    logging.info(f"Found {len(asin_to_test)} ASINs to diagnose: {asin_to_test}")

    # Clear previous log file
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)
        logging.info(f"Removed old log file: {LOG_FILE}")

    # 2. Process each ASIN
    for asin in asin_to_test:
        logging.info(f"--- Processing ASIN: {asin} ---")

        # a. Fetch full product data
        logging.info(f"Fetching product data for {asin} from Keepa...")
        est_cost = 12 # Estimate for a single product call
        token_manager.request_permission_for_call(est_cost)
        product_data_response, _, _, tokens_left = fetch_product_batch(api_key, [asin], history=1, offers=20)
        if tokens_left is not None:
            token_manager.update_after_call(tokens_left)

        if not product_data_response or not product_data_response.get('products'):
            logging.error(f"Failed to fetch product data for {asin}.")
            continue

        product_data = product_data_response['products'][0]

        # b. Pre-fetch seller data
        seller_ids = {offer['sellerId'] for offer in product_data.get('offers', []) if isinstance(offer, dict) and 'sellerId' in offer}
        seller_data_cache = {}
        if seller_ids:
            seller_id_list = list(seller_ids)
            logging.info(f"Found {len(seller_id_list)} unique seller IDs to fetch for this ASIN.")
            for i in range(0, len(seller_id_list), 100):
                batch_ids = seller_id_list[i:i+100]
                token_manager.request_permission_for_call(1)
                seller_data, _, _, tokens_left = fetch_seller_data(api_key, batch_ids)
                if tokens_left is not None:
                    token_manager.update_after_call(tokens_left)
                if seller_data and 'sellers' in seller_data:
                    seller_data_cache.update(seller_data['sellers'])

        # c. Call the seller info function
        logging.info(f"Calling get_all_seller_info for {asin}...")
        seller_info = get_all_seller_info(product_data, seller_data_cache)

        # d. Log everything for analysis
        logging.info(f"Logging all data for failing ASIN {asin} to {LOG_FILE}")
        with open(LOG_FILE, 'a') as f:
            log_data = {
                "failing_asin": asin,
                "calculated_seller_info": seller_info,
                "raw_product_data": product_data
            }
            f.write(json.dumps(log_data, indent=2) + "\n\n")

    logging.info(f"Diagnostic complete. See {LOG_FILE} for raw data.")

if __name__ == '__main__':
    import time
    run_diagnostic()
