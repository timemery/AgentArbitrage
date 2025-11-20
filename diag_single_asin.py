#!/usr/bin/env python3
import logging
import os
import json
import sys
import time
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Ensure the script can find the keepa_deals module
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from keepa_deals.keepa_api import fetch_product_batch, validate_asin, fetch_seller_data
from keepa_deals.token_manager import TokenManager
from keepa_deals.processing import _process_single_deal
from keepa_deals.business_calculations import load_settings as business_load_settings

# --- LOG FILE ---
LOG_FILE = 'diag_single_asin.log'

# Configure logging
if os.path.exists(LOG_FILE):
    os.remove(LOG_FILE)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout) # Explicitly log to stdout as well
    ]
)
logger = logging.getLogger(__name__)

def run_single_asin_diagnostic(asin: str):
    """
    Runs a full diagnostic for a single ASIN, logging every step.
    """
    logger.info(f"--- Starting Diagnostic for ASIN: {asin} ---")

    # 1. Load Environment and Settings
    logger.info("Loading environment variables...")
    load_dotenv()
    api_key = os.getenv("KEEPA_API_KEY")
    xai_api_key = os.getenv("XAI_TOKEN")
    if not api_key or not xai_api_key:
        logger.error("API keys (KEEPA_API_KEY, XAI_TOKEN) not found. Aborting.")
        return
    logger.info("API keys loaded.")

    logger.info("Loading business settings...")
    business_settings = business_load_settings()
    logger.info("Business settings loaded.")

    logger.info("Loading headers...")
    headers_path = os.path.join(os.path.dirname(__file__), 'keepa_deals', 'headers.json')
    with open(headers_path) as f:
        headers = json.load(f)
    logger.info("Headers loaded.")

    # 2. Initialize Token Manager
    token_manager = TokenManager(api_key)
    token_manager.sync_tokens()
    logger.info(f"Token Manager initialized. Current tokens: {token_manager.tokens}")

    # 3. Fetch Product Data
    logger.info(f"Fetching product data for ASIN: {asin}...")
    estimated_cost = 25 # Increased estimate for safety
    while token_manager.tokens < estimated_cost:
        wait_time = (estimated_cost - token_manager.tokens) * 12 + 12
        logger.warning(f"Insufficient tokens for product data fetch. Have: {token_manager.tokens:.2f}, Need: {estimated_cost}. Waiting for {int(wait_time)} seconds.")
        time.sleep(int(wait_time))
        token_manager.sync_tokens()
        logger.info(f"Tokens refilled. Current tokens: {token_manager.tokens:.2f}")

    product_response, _, _, tokens_left = fetch_product_batch(api_key, [asin], history=1, offers=100)
    token_manager.update_after_call(tokens_left)

    if not product_response or not product_response.get('products'):
        logger.error("Failed to fetch product data after waiting. Aborting.")
        return

    product_data = product_response['products'][0]
    logger.info("--- RAW PRODUCT DATA ---")
    logger.info(json.dumps(product_data, indent=2))
    logger.info("--- END RAW PRODUCT DATA ---")

    # 4. Fetch Seller Data
    logger.info("Extracting unique seller IDs...")
    unique_seller_ids = set()
    for offer in product_data.get('offers', []):
        if isinstance(offer, dict) and offer.get('sellerId'):
            unique_seller_ids.add(offer['sellerId'])

    seller_data_cache = {}
    if unique_seller_ids:
        logger.info(f"Found {len(unique_seller_ids)} unique seller IDs.")
        seller_id_list = list(unique_seller_ids)

        cost = len(seller_id_list) // 100 + 1
        while token_manager.tokens < cost:
            wait_time = (cost - token_manager.tokens) * 12 + 12
            logger.warning(f"Insufficient tokens for seller data fetch. Have: {token_manager.tokens:.2f}, Need: {cost}. Waiting for {int(wait_time)} seconds.")
            time.sleep(int(wait_time))
            token_manager.sync_tokens()
            logger.info(f"Tokens refilled. Current tokens: {token_manager.tokens:.2f}")

        seller_data, _, _, tokens_left = fetch_seller_data(api_key, seller_id_list)
        token_manager.update_after_call(tokens_left)

        if seller_data and 'sellers' in seller_data:
            seller_data_cache.update(seller_data['sellers'])
        logger.info("--- RAW SELLER DATA ---")
        logger.info(json.dumps(seller_data_cache, indent=2))
        logger.info("--- END RAW SELLER DATA ---")
    else:
        logger.warning("No seller IDs found in the offers list.")

    # 5. Process the Single Deal
    logger.info("Starting processing with _process_single_deal...")
    deal_object = {'asin': asin, 'lastUpdate': product_data.get('lastUpdate', 0)}
    product_data.update(deal_object)

    processed_row = _process_single_deal(product_data, seller_data_cache, xai_api_key, business_settings, headers)

    logger.info("--- FINAL PROCESSED ROW ---")
    logger.info(json.dumps(processed_row, indent=2))
    logger.info("--- END FINAL PROCESSED ROW ---")

    logger.info(f"--- Diagnostic for ASIN: {asin} Finished ---")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 diag_single_asin.py <ASIN>")
        sys.exit(1)

    target_asin = sys.argv[1]
    if not validate_asin(target_asin):
        print(f"Error: '{target_asin}' is not a valid ASIN.")
        sys.exit(1)

    run_single_asin_diagnostic(target_asin)
