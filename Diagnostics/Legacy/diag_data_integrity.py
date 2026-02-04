import logging
import json
from dotenv import load_dotenv
import os
import sys

# Add the project root to the Python path to allow for absolute imports
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '.'))
sys.path.insert(0, project_root)

from keepa_deals.keepa_api import fetch_product_batch
from keepa_deals.processing import _process_single_deal
from keepa_deals.token_manager import TokenManager
from keepa_deals.seller_info import get_seller_info_for_single_deal

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def diagnose_asin(asin: str):
    """
    Fetches data for a single ASIN and runs it through the processing pipeline
    with extensive logging to trace data integrity.
    """
    logger.info(f"--- Starting diagnosis for ASIN: {asin} ---")

    # 1. Load Environment & API Keys
    env_path = os.path.join(project_root, '.env')
    if not os.path.exists(env_path):
        logger.error(f".env file not found at {env_path}. Please create one.")
        # As a fallback for sandbox, check the parent directory
        env_path = os.path.join(project_root, '..', '.env')
        if not os.path.exists(env_path):
             logger.error(f"Also not found at {env_path}. Aborting.")
             return
    load_dotenv(dotenv_path=env_path)

    api_key = os.getenv("KEEPA_API_KEY")
    xai_api_key = os.getenv("XAI_API_KEY")

    if not api_key:
        logger.error(f"KEEPA_API_KEY not found in {env_path}. Aborting.")
        return

    # 2. Setup API and Token Manager
    token_manager = TokenManager(api_key)
    logger.info("Syncing tokens with Keepa API...")
    try:
        token_manager.sync_tokens()
        logger.info(f"Initial token count: {token_manager.tokens}")
    except Exception as e:
        logger.error(f"Failed to sync tokens: {e}")
        return

    # 3. Fetch Product Data
    logger.info(f"Fetching product data for ASIN {asin}...")
    product_data = None
    try:
        product_data_list, _, tokens_consumed, tokens_left = fetch_product_batch(
            api_key, [asin], offers=20, days=365
        )
        token_manager.update_after_call(tokens_left)
        logger.info(f"Successfully fetched product data. Tokens consumed: {tokens_consumed}. Tokens left: {tokens_left}")

        logger.info(f"--- Type of returned product_data_list: {type(product_data_list)} ---")
        logger.info(f"--- Raw returned product_data_list ---")
        logger.info(json.dumps(product_data_list, indent=2, default=str))
        logger.info(f"------------------------------------")

        product_data = product_data_list['products'][0] if product_data_list and 'products' in product_data_list else None

    except Exception as e:
        logger.error(f"Failed to fetch product data from Keepa: {e}", exc_info=True)
        return

    if not product_data:
        logger.error("Keepa API returned no product data.")
        return

    logger.info("--- Raw Product Data Received ---")
    logger.info(json.dumps(product_data, indent=2, default=str))
    logger.info("-----------------------------------------------------")

    # Log the specific 'offers' array that is causing issues
    logger.info("--- Raw 'offers' Array ---")
    logger.info(json.dumps(product_data.get('offers', []), indent=2, default=str))
    logger.info("----------------------------")

    # 4. Fetch Seller Data (simulating the backfiller's cache generation)
    logger.info("Fetching seller data for the lowest-priced used offer...")
    try:
        seller_data_cache = get_seller_info_for_single_deal(product_data, api_key, token_manager)
        logger.info("--- Seller Data Cache ---")
        logger.info(json.dumps(seller_data_cache, indent=2, default=str))
        logger.info("---------------------------")
    except Exception as e:
        logger.error(f"Failed to get seller_data_cache: {e}", exc_info=True)
        seller_data_cache = {}

    # 5. Process the Deal
    logger.info("--- Calling _process_single_deal ---")
    try:
        processed_data = _process_single_deal(product_data, seller_data_cache, xai_api_key)
    except Exception as e:
        logger.error(f"An unexpected error occurred during _process_single_deal: {e}", exc_info=True)
        processed_data = None

    logger.info("--- Final Processed Data ---")
    if processed_data:
        # Sort the keys for consistent output
        sorted_data = dict(sorted(processed_data.items()))
        logger.info(json.dumps(sorted_data, indent=2, default=str))
    else:
        logger.error("Processing failed. No data was returned.")
    logger.info("----------------------------")
    logger.info("Diagnosis complete.")

if __name__ == "__main__":
    # A known-good ASIN for a textbook that should have used offers
    target_asin = "0134494164"
    if len(sys.argv) > 1:
        target_asin = sys.argv[1]
    diagnose_asin(target_asin)
