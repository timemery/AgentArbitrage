#!/usr/bin/env python3
import logging
import os
import json
import sys
import time
import sqlite3
from datetime import datetime, timezone
from dotenv import load_dotenv

# Ensure the script can find the keepa_deals module
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from keepa_deals.keepa_api import fetch_product_batch, validate_asin, fetch_seller_data
from keepa_deals.token_manager import TokenManager
from keepa_deals.processing import _process_single_deal, clean_numeric_values
from keepa_deals.business_calculations import load_settings as business_load_settings
from keepa_deals.db_utils import create_deals_table_if_not_exists, sanitize_col_name

# --- CONFIGURATION ---
LOG_FILE = 'diag_single_deal.log'
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'deals.db')
TABLE_NAME = 'deals'
HEADERS_PATH = os.path.join(os.path.dirname(__file__), 'keepa_deals', 'headers.json')

# Configure logging
if os.path.exists(LOG_FILE):
    os.remove(LOG_FILE)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def run_diagnostic(asin: str):
    """
    Runs a full diagnostic for a single ASIN, from data fetching to database write.
    """
    logger.info(f"--- Starting Diagnostic for ASIN: {asin} ---")

    # 1. Load Environment and Settings
    logger.info("Step 1: Loading environment and settings...")
    # Explicitly load .env from the script's directory to avoid find_dotenv issues
    dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
    load_dotenv(dotenv_path=dotenv_path)
    api_key = os.getenv("KEEPA_API_KEY")
    xai_api_key = os.getenv("XAI_TOKEN")
    if not api_key or not xai_api_key:
        logger.error("API keys (KEEPA_API_KEY, XAI_TOKEN) not found. Aborting.")
        return
    business_settings = business_load_settings()
    with open(HEADERS_PATH) as f:
        headers = json.load(f)
    logger.info("Step 1: Complete.")

    # 2. Initialize Database and Token Manager
    logger.info("Step 2: Initializing database and token manager...")
    create_deals_table_if_not_exists()
    token_manager = TokenManager(api_key)
    token_manager.sync_tokens()
    logger.info(f"Step 2: Complete. Current tokens: {token_manager.tokens}")

    # 3. Fetch Product Data
    logger.info(f"Step 3: Fetching product data for ASIN: {asin}...")
    token_manager.request_permission_for_call(estimated_cost=25)
    product_response, _, _, tokens_left = fetch_product_batch(api_key, [asin], history=1, offers=100)
    token_manager.update_after_call(tokens_left)
    if not product_response or not product_response.get('products'):
        logger.error("Failed to fetch product data. Aborting.")
        return
    product_data = product_response['products'][0]
    logger.info("Step 3: Complete.")

    # 4. Fetch Seller Data
    logger.info("Step 4: Fetching seller data...")
    unique_seller_ids = {offer.get('sellerId') for offer in product_data.get('offers', []) if isinstance(offer, dict) and offer.get('sellerId')}
    seller_data_cache = {}
    if unique_seller_ids:
        seller_id_list = list(unique_seller_ids)
        logger.info(f"Found {len(seller_id_list)} unique seller IDs. Fetching in batches of 100...")
        for i in range(0, len(seller_id_list), 100):
            batch_ids = seller_id_list[i:i+100]
            logger.info(f"Fetching batch {i//100 + 1}/{(len(seller_id_list)-1)//100 + 1}...")
            token_manager.request_permission_for_call(estimated_cost=1)
            seller_data, _, _, tokens_left = fetch_seller_data(api_key, batch_ids)

            if tokens_left is not None:
                token_manager.update_after_call(tokens_left)

            if seller_data and 'sellers' in seller_data:
                seller_data_cache.update(seller_data['sellers'])

            if len(seller_id_list) > 100 and i + 100 < len(seller_id_list):
                logger.info("Pausing between large seller batches...")
                time.sleep(2) # Brief pause

    logger.info(f"Step 4: Complete. Found {len(seller_data_cache)} sellers.")

    # 5. Process the Single Deal
    logger.info("Step 5: Processing data...")
    deal_object = {'asin': asin, 'lastUpdate': product_data.get('lastUpdate', 0)}
    product_data.update(deal_object)
    processed_row = _process_single_deal(product_data, seller_data_cache, xai_api_key, business_settings, headers)
    if not processed_row:
        logger.error("Processing failed to return a valid row. Aborting.")
        return
    logger.info("Step 5: Complete.")
    logger.info(f"--- Processed Row Data ---\n{json.dumps(processed_row, indent=2)}\n-------------------------")

    # 6. Write to Database
    logger.info("Step 6: Writing to database...")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Clean and prepare data for DB
            processed_row = clean_numeric_values(processed_row)
            processed_row['last_seen_utc'] = datetime.now(timezone.utc).isoformat()
            processed_row['source'] = 'diagnostic'

            sanitized_headers = [sanitize_col_name(h) for h in headers]
            all_cols = sanitized_headers + ['last_seen_utc', 'source']

            # Ensure all expected columns are present in the row
            for col in all_cols:
                if col not in processed_row:
                    processed_row[col] = None

            cols_str = ', '.join(f'"{h}"' for h in all_cols)
            vals_str = ', '.join(['?'] * len(all_cols))

            values_tuple = tuple(processed_row.get(h) for h in all_cols)

            upsert_sql = f"""
                INSERT INTO {TABLE_NAME} ({cols_str})
                VALUES ({vals_str})
                ON CONFLICT(ASIN) DO UPDATE SET
                {', '.join(f'"{h}"=excluded."{h}"' for h in all_cols if h != 'ASIN')}
            """

            cursor.execute(upsert_sql, values_tuple)
            conn.commit()
            logger.info(f"Step 6: Success! Wrote 1 row for ASIN {asin} to '{TABLE_NAME}'.")

    except sqlite3.Error as e:
        logger.error(f"Step 6: FAILED. Database error: {e}", exc_info=True)
        return
    except Exception as e:
        logger.error(f"Step 6: FAILED. An unexpected error occurred: {e}", exc_info=True)
        return

    logger.info(f"--- Diagnostic for ASIN: {asin} Finished Successfully ---")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 diag_single_deal.py <ASIN>")
        sys.exit(1)

    target_asin = sys.argv[1]
    if not validate_asin(target_asin):
        print(f"Error: '{target_asin}' is not a valid ASIN.")
        sys.exit(1)

    run_diagnostic(target_asin)