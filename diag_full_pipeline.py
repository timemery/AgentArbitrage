# diag_full_pipeline.py
# A comprehensive diagnostic script to test and POPULATE the database.

import logging
import os
import sys
import sqlite3
from dotenv import load_dotenv
import json
from datetime import datetime, timezone

# --- Constants ---
DEAL_LIMIT = 500 # Process this many deals to populate the DB
DB_PATH = 'deals.db'

# --- 1. Setup & Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
sys.path.append(os.getcwd())
logger.info("--- STARTING FULL PIPELINE DIAGNOSTIC SCRIPT (DB POPULATION MODE) ---")

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
    if not KEEPA_API_KEY: raise ValueError("KEEPA_API_KEY not found.")
    if not XAI_API_KEY: logger.warning("XAI_TOKEN not found.")
except Exception as e:
    logger.error(f"Failed during environment setup: {e}", exc_info=True)
    sys.exit(1)

# --- 3. Core Module Import Check ---
logger.info("\nStep 3: Importing Core Modules...")
try:
    from keepa_deals.keepa_api import fetch_deals_for_deals, fetch_product_batch, fetch_seller_data
    from keepa_deals.processing import _process_single_deal, clean_numeric_values
    from keepa_deals.business_calculations import load_settings as business_load_settings
    from keepa_deals.db_utils import recreate_deals_table, sanitize_col_name
    from keepa_deals.token_manager import TokenManager
    logger.info("All core modules imported successfully.")
except ImportError as e:
    logger.error(f"Failed to import a core module: {e}", exc_info=True)
    sys.exit(1)

def save_to_db(processed_row):
    """Saves a single processed row dictionary to the database."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            sanitized_row = {sanitize_col_name(k): v for k, v in processed_row.items()}

            # Ensure ASIN is present for the unique key
            if 'ASIN' not in sanitized_row:
                logger.error("Skipping row - missing ASIN.")
                return

            cols = ', '.join(f'"{k}"' for k in sanitized_row.keys())
            placeholders = ', '.join('?' for _ in sanitized_row)

            sql = f"INSERT OR REPLACE INTO deals ({cols}) VALUES ({placeholders})"
            cursor.execute(sql, list(sanitized_row.values()))
            conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Database error while saving ASIN {processed_row.get('ASIN')}: {e}", exc_info=True)

# --- 4. Main Execution ---
def run_pipeline():
    logger.info("\nStep 4: Preparing Database...")
    recreate_deals_table()

    token_manager = TokenManager(KEEPA_API_KEY)
    token_manager.sync_tokens()
    business_settings = business_load_settings()
    with open('keepa_deals/headers.json') as f:
        headers = json.load(f)

    logger.info(f"\nStep 5: Fetching up to {DEAL_LIMIT} deals...")
    deal_response, _, tokens_left = fetch_deals_for_deals(0, KEEPA_API_KEY, use_deal_settings=True)
    token_manager.update_after_call(tokens_left)

    if not (deal_response and 'deals' in deal_response and deal_response['deals']['dr']):
        logger.error("Deal fetching failed or returned no deals. Aborting.")
        return

    all_deals = deal_response['deals']['dr'][:DEAL_LIMIT]
    logger.info(f"Successfully fetched {len(all_deals)} deals. Now fetching product data...")

    all_asins = [d['asin'] for d in all_deals]

    # Correctly use the token manager
    estimated_cost = 12 * len(all_asins) # A reasonable estimate for product calls with offers
    token_manager.request_permission_for_call(estimated_cost)
    product_response, _, tokens_consumed, tokens_left = fetch_product_batch(KEEPA_API_KEY, all_asins, history=1, offers=20)
    token_manager.update_after_call(tokens_left)

    if not (product_response and 'products' in product_response):
        logger.error("Product data fetching failed. Aborting.")
        return

    all_products_map = {p['asin']: p for p in product_response['products']}
    logger.info(f"Successfully fetched product data for {len(all_products_map)} ASINs.")

    logger.info("\nStep 6: Pre-fetching all seller data...")
    all_seller_ids = {
        offer['sellerId']
        for p in all_products_map.values()
        for offer in p.get('offers', []) if isinstance(offer, dict) and offer.get('sellerId')
    }
    seller_data_cache = {}
    if all_seller_ids:
        seller_id_list = list(all_seller_ids)
        for i in range(0, len(seller_id_list), 100):
            batch_ids = seller_id_list[i:i+100]
            token_manager.request_permission_for_call(estimated_cost=1)
            seller_data, _, tokens_consumed, tokens_left = fetch_seller_data(KEEPA_API_KEY, batch_ids)
            # CRITICAL: Check for None before updating, as a failed call returns None
            if tokens_left is not None:
                token_manager.update_after_call(tokens_left)

            if seller_data and 'sellers' in seller_data:
                seller_data_cache.update(seller_data['sellers'])
    logger.info(f"Fetched data for {len(seller_data_cache)} unique sellers.")

    logger.info(f"\nStep 7: Processing {len(all_deals)} deals and saving to database...")
    processed_count = 0
    for deal in all_deals:
        asin = deal['asin']
        if asin not in all_products_map:
            continue

        product_data = all_products_map[asin]
        # Merge deal data into product data for processing
        product_data.update(deal)

        processed_row = _process_single_deal(product_data, seller_data_cache, XAI_API_KEY, business_settings, headers)

        if processed_row:
            processed_row = clean_numeric_values(processed_row)
            processed_row['last_seen_utc'] = datetime.now(timezone.utc).isoformat()
            processed_row['source'] = 'diag_pipeline'
            save_to_db(processed_row)
            processed_count += 1
            logger.info(f"Processed and saved ASIN {asin} ({processed_count}/{len(all_deals)})")
        else:
            logger.warning(f"Skipping ASIN {asin} as it returned no data from processing.")

    logger.info(f"\n--- DIAGNOSTIC SCRIPT COMPLETED ---")
    logger.info(f"Successfully processed and saved {processed_count} deals to '{DB_PATH}'.")

if __name__ == "__main__":
    run_pipeline()
