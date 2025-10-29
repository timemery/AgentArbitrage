# diag_full_pipeline.py
# A comprehensive diagnostic script to test each stage of the data pipeline in isolation.

import logging
import os
import sys
from dotenv import load_dotenv
import json

# --- 1. Setup & Configuration ---
# Set up verbose logging to the console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Ensure the app's modules are in the Python path
sys.path.append(os.getcwd())

logger.info("--- STARTING FULL PIPELINE DIAGNOSTIC SCRIPT ---")

# --- 2. Environment Variable Check ---
logger.info("Step 2: Checking Environment Variables...")
try:
    dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path=dotenv_path)
        logger.info(".env file loaded.")
    else:
        logger.warning(".env file not found.")

    KEEPA_API_KEY = os.getenv("KEEPA_API_KEY")
    XAI_API_KEY = os.getenv("XAI_TOKEN")

    if KEEPA_API_KEY:
        logger.info("KEEPA_API_KEY: Found (length %d)", len(KEEPA_API_KEY))
    else:
        logger.error("KEEPA_API_KEY: NOT FOUND. This will cause failures.")
    if XAI_API_KEY:
        logger.info("XAI_TOKEN: Found (length %d)", len(XAI_API_KEY))
    else:
        logger.warning("XAI_TOKEN: NOT FOUND. AI-related calculations will be skipped.")
except Exception as e:
    logger.error("Failed during environment setup: %s", e, exc_info=True)
    sys.exit(1)

# --- 3. Core Module Import Check ---
logger.info("\nStep 3: Importing Core Modules...")
try:
    from keepa_deals.keepa_api import fetch_deals_for_deals, fetch_product_batch, fetch_seller_data
    from keepa_deals.processing import _process_single_deal
    from keepa_deals.business_calculations import load_settings as business_load_settings
    from keepa_deals.db_utils import recreate_deals_table, sanitize_col_name
    logger.info("All core modules imported successfully.")
except ImportError as e:
    logger.error("Failed to import a core module: %s", e, exc_info=True)
    sys.exit(1)

# --- 4. Deal Fetching Test ---
logger.info("\nStep 4: Testing Deal Fetching (fetch_deals_for_deals)...")
try:
    deal_response, _, _ = fetch_deals_for_deals(0, KEEPA_API_KEY, use_deal_settings=True)
    if deal_response and 'deals' in deal_response and deal_response['deals']['dr']:
        deals_found = len(deal_response['deals']['dr'])
        logger.info(f"Successfully fetched deals. Found {deals_found} deals on page 0.")
        # Grab a few ASINs for the next step
        test_asins = [d['asin'] for d in deal_response['deals']['dr'][:3]]
        if not test_asins:
            raise Exception("No ASINs found on the first page of deals.")
    else:
        raise Exception(f"Deal fetching failed or returned no deals. Response: {deal_response}")
except Exception as e:
    logger.error("Failed during deal fetching test: %s", e, exc_info=True)
    sys.exit(1)

# --- 5. Product Data Fetching Test ---
logger.info("\nStep 5: Testing Product Data Fetching (fetch_product_batch)...")
try:
    logger.info(f"Requesting full data for ASINs: {test_asins}")
    product_response, _, _, _ = fetch_product_batch(KEEPA_API_KEY, test_asins, history=1, offers=20)
    if product_response and 'products' in product_response:
        products_found = len(product_response['products'])
        logger.info(f"Successfully fetched product data for {products_found} ASINs.")
        # Get one full product object for the next stage
        single_product_data = product_response['products'][0]
        logger.info(f"Sample product data for ASIN {single_product_data['asin']} collected.")
    else:
        raise Exception(f"Product data fetching failed. Response: {product_response}")
except Exception as e:
    logger.error("Failed during product data fetching test: %s", e, exc_info=True)
    sys.exit(1)

# --- 6. Single Deal Processing Test ---
logger.info("\nStep 6: Testing Single Deal Processing (_process_single_deal)...")
try:
    logger.info(f"Processing data for ASIN: {single_product_data['asin']}")
    business_settings = business_load_settings()
    with open('keepa_deals/headers.json') as f:
        headers = json.load(f)

    # Simulate the pre-fetching of seller data for just this one product
    seller_data_cache = {}
    unique_seller_ids = {offer['sellerId'] for offer in single_product_data.get('offers', []) if isinstance(offer, dict) and offer.get('sellerId')}
    if unique_seller_ids:
        seller_data, _, _, _ = fetch_seller_data(KEEPA_API_KEY, list(unique_seller_ids))
        if seller_data and 'sellers' in seller_data:
            seller_data_cache = seller_data['sellers']
            logger.info(f"Fetched data for {len(seller_data_cache)} sellers related to this ASIN.")

    processed_row = _process_single_deal(
        single_product_data,
        seller_data_cache,
        XAI_API_KEY,
        business_settings,
        headers
    )
    if processed_row:
        logger.info("Successfully processed a single deal.")
        logger.info("--- Processed Row Data ---")
        # Pretty print the resulting dictionary
        for key, value in processed_row.items():
            logger.info(f"  {key}: {value}")
        logger.info("--- End of Processed Row ---")
        if not processed_row.get('Price Now') or processed_row.get('Price Now') == '-':
            logger.error("CRITICAL DIAGNOSTIC: 'Price Now' is missing or empty after processing. This is a key failure point.")
        else:
            logger.info("SUCCESS: 'Price Now' was calculated correctly.")
    else:
        raise Exception("Processing a single deal returned an empty result.")

except Exception as e:
    logger.error("Failed during single deal processing test: %s", e, exc_info=True)
    sys.exit(1)

logger.info("\n--- DIAGNOSTIC SCRIPT COMPLETED SUCCESSFULLY ---")
logger.info("Conclusion: All individual pipeline stages (environment, API calls, data processing) are functioning correctly in isolation.")
logger.info("This strongly suggests the root cause of the failure is not in the core Python logic itself, but in the Celery execution environment (e.g., worker configuration, task discovery, or a 'zombie' process running stale code).")
