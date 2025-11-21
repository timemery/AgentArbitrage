import os
import sys
import json
import logging
from dotenv import load_dotenv

# Add the project root to the Python path to allow for absolute imports
# This is necessary to import from the 'keepa_deals' package
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Now that the path is set, we can import from our application's modules
try:
    from keepa_deals.keepa_api import fetch_product_batch
except ImportError:
    print("Error: Could not import 'fetch_product_batch'.")
    print("Please ensure you are running this script from the root of the AgentArbitrage project.")
    print("Also, check that 'keepa_deals/keepa_api.py' exists and is accessible.")
    sys.exit(1)


# --- Configuration ---
LOG_FILE = 'diag_no_seller_log.json'
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def run_diagnostic(asin: str):
    """
    Fetches the raw product data for a single ASIN from the Keepa API
    and saves it to a log file.
    """
    logging.info(f"--- Starting Diagnostic for ASIN: {asin} ---")

    # 1. Load Environment Variables
    env_path = os.path.join(project_root, '.env')
    if not os.path.exists(env_path):
        logging.error(f"CRITICAL: .env file not found at '{env_path}'. Cannot proceed.")
        return
    load_dotenv(dotenv_path=env_path)
    api_key = os.getenv("KEEPA_API_KEY")
    if not api_key:
        logging.error("CRITICAL: KEEPA_API_KEY not found in .env file.")
        return
    logging.info("Successfully loaded Keepa API key.")

    # 2. Fetch Product Data
    logging.info(f"Requesting product data for ASIN '{asin}' from Keepa...")
    product_to_log = {}
    try:
        # We need to fetch a generous number of offers to ensure we see what the deal finder sees.
        # We also need the history and stats to compare.
        products_data, api_info, tokens_consumed, tokens_left = fetch_product_batch(
            api_key=api_key,
            asins_list=[asin],
            days=365,
            offers=20,
            history=1 # Use 1 for True as per the function definition
        )

        logging.info(f"API call successful. Tokens consumed: {tokens_consumed}. Tokens left: {tokens_left}.")

        if not products_data or not products_data.get('products'):
            logging.warning("API response did not contain any product data.")
            product_to_log = {"error": "No product data returned from API."}
        else:
            product_to_log = products_data['products'][0]
            logging.info("Successfully extracted product data from response.")

    except Exception as e:
        logging.error(f"An error occurred during the Keepa API call: {e}", exc_info=True)
        product_to_log = {"error": f"Exception during API call: {str(e)}"}

    # 3. Log the Raw Data
    try:
        with open(LOG_FILE, 'w') as f:
            json.dump(product_to_log, f, indent=4)
        logging.info(f"Successfully wrote raw product data to '{LOG_FILE}'.")
    except IOError as e:
        logging.error(f"Failed to write to log file '{LOG_FILE}': {e}")

    logging.info("--- Diagnostic Finished ---")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 diag_no_seller.py <ASIN>")
        sys.exit(1)
    target_asin = sys.argv[1]
    run_diagnostic(target_asin)
