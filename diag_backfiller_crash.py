#!/usr/bin/env python3
import logging
import os
import json
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Ensure the script can find the keepa_deals module
import sys
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from keepa_deals.db_utils import recreate_deals_table, save_watermark
from keepa_deals.keepa_api import fetch_deals_for_deals, fetch_product_batch, validate_asin, fetch_seller_data
from keepa_deals.token_manager import TokenManager
from keepa_deals.processing import _process_single_deal, clean_numeric_values
from keepa_deals.business_calculations import load_settings as business_load_settings
from keepa_deals.stable_calculations import clear_analysis_cache

# Configure logging to file and console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s', filename='diag_crash.log', filemode='w')
logger = logging.getLogger(__name__)

logger.info("Script started. Basic logging configured.")

# Load environment variables
logger.info("Loading environment variables...")
load_dotenv()
logger.info("Environment variables loaded.")

# --- DIAGNOSTIC LIMIT ---
# Limit the number of deals to process to find the crash quickly.
DEAL_LIMIT = 100

# --- Constants ---
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'deals.db')
TABLE_NAME = 'deals'
HEADERS_PATH = os.path.join(os.path.dirname(__file__), 'keepa_deals', 'headers.json')
MAX_ASINS_PER_BATCH = 20
CRASH_LOG_FILE = 'crash_log.json'

def _process_and_save_deal_page(deals_on_page, api_key, xai_api_key, token_manager, business_settings, headers, all_fetched_products, seller_data_cache):
    """
    Processes a single page of deals and saves them to a temporary JSON file.
    Includes robust error handling to catch and log crashes.
    """
    rows_to_upsert = []
    logger.info(f"Processing {len(deals_on_page)} deals for this page.")

    for deal in deals_on_page:
        asin = deal.get('asin')
        try:
            if not asin or not validate_asin(asin):
                logger.warning(f"Skipping invalid ASIN: {asin}")
                continue

            if asin not in all_fetched_products:
                logger.warning(f"No product data found for ASIN: {asin}. Skipping.")
                continue

            product_data = all_fetched_products[asin]
            product_data.update(deal)

            processed_row = _process_single_deal(product_data, seller_data_cache, xai_api_key, business_settings, headers)

            if processed_row:
                processed_row = clean_numeric_values(processed_row)
                processed_row['last_seen_utc'] = datetime.now(timezone.utc).isoformat()
                processed_row['source'] = 'diag_backfiller_crash'
                rows_to_upsert.append(processed_row)

            time.sleep(1) # Delay to prevent overwhelming APIs/CPU

        except Exception as e:
            logger.error(f"CRASH DETECTED on ASIN: {asin}. Logging error and full data to {CRASH_LOG_FILE}", exc_info=True)
            error_log = {
                'asin': asin,
                'error_type': type(e).__name__,
                'error_message': str(e),
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'deal_data': deal,
                'product_data': all_fetched_products.get(asin, 'PRODUCT_DATA_NOT_FOUND')
            }
            with open(CRASH_LOG_FILE, 'a') as f:
                json.dump(error_log, f, indent=4)
                f.write('\n---\n')
            continue # Continue to the next deal

    if rows_to_upsert:
        logger.info(f"Appending {len(rows_to_upsert)} successfully processed deals to temp_deals.json.")
        try:
            with open('temp_deals.json', 'r') as f:
                existing_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            existing_data = []

        existing_data.extend(rows_to_upsert)
        with open('temp_deals.json', 'w') as f:
            json.dump(existing_data, f, indent=4)

def run_diagnostic_backfill():
    """
    A standalone, crash-proof version of the backfill_deals task.
    """
    logger.info("--- Diagnostic Backfiller Crash Test Started ---")

    if os.path.exists('temp_deals.json'):
        os.remove('temp_deals.json')
    if os.path.exists(CRASH_LOG_FILE):
        os.remove(CRASH_LOG_FILE)

    logger.info("Clearing analysis cache...")
    clear_analysis_cache()
    logger.info("Analysis cache cleared.")
    # We don't need to recreate the whole table for this diagnostic
    # recreate_deals_table()

    logger.info("Getting API keys from environment...")
    api_key = os.getenv("KEEPA_API_KEY")
    xai_api_key = os.getenv("XAI_TOKEN")
    if not api_key:
        logger.error("KEEPA_API_KEY not set. Aborting.")
        return

    logger.info("Initializing TokenManager...")
    token_manager = TokenManager(api_key)
    logger.info("Syncing tokens...")
    token_manager.sync_tokens()
    logger.info("Tokens synced.")

    logger.info("Loading business settings...")
    business_settings = business_load_settings()
    logger.info("Business settings loaded.")

    logger.info("Loading headers...")
    with open(HEADERS_PATH) as f:
        headers = json.load(f)
    logger.info("Headers loaded.")

    page = 0
    total_deals_processed = 0
    all_deals_on_all_pages = []

    # 1. First, collect all deals up to the limit
    logger.info(f"Collecting up to {DEAL_LIMIT} deals from Keepa...")
    while True:
        logger.info(f"Fetching page {page} of deals...")
        token_manager.request_permission_for_call(estimated_cost=5)
        deal_response, _, tokens_left = fetch_deals_for_deals(page, api_key, use_deal_settings=True)
        token_manager.update_after_call(tokens_left)

        if not deal_response or 'deals' not in deal_response or not deal_response['deals']['dr']:
            logger.info("No more deals found.")
            break

        deals_on_page = [d for d in deal_response['deals']['dr'] if validate_asin(d.get('asin'))]

        if total_deals_processed + len(deals_on_page) > DEAL_LIMIT:
            deals_to_take = DEAL_LIMIT - total_deals_processed
            all_deals_on_all_pages.extend(deals_on_page[:deals_to_take])
            total_deals_processed += deals_to_take
            break
        else:
            all_deals_on_all_pages.extend(deals_on_page)
            total_deals_processed += len(deals_on_page)

        page += 1
        time.sleep(1)

    logger.info(f"Collected a total of {total_deals_processed} deals.")

    # 2. Fetch all product data in batches
    all_fetched_products = {}
    asin_list = [d['asin'] for d in all_deals_on_all_pages]
    logger.info("Fetching all product data...")
    for i in range(0, len(asin_list), MAX_ASINS_PER_BATCH):
        batch_asins = asin_list[i:i + MAX_ASINS_PER_BATCH]
        estimated_cost = 12 * len(batch_asins)
        token_manager.request_permission_for_call(estimated_cost)
        product_response, _, _, tokens_left = fetch_product_batch(api_key, batch_asins, history=1, offers=20)
        token_manager.update_after_call(tokens_left)
        if product_response and 'products' in product_response:
            all_fetched_products.update({p['asin']: p for p in product_response['products']})
        logger.info(f"Fetched product data for batch {i//MAX_ASINS_PER_BATCH + 1}/{(len(asin_list) + MAX_ASINS_PER_BATCH - 1)//MAX_ASINS_PER_BATCH}")

    # 3. Pre-fetch all seller data
    logger.info("Fetching all seller data...")
    unique_seller_ids = set()
    for product in all_fetched_products.values():
        for offer in product.get('offers', []):
            if isinstance(offer, dict) and offer.get('sellerId'):
                unique_seller_ids.add(offer['sellerId'])

    seller_data_cache = {}
    if unique_seller_ids:
        seller_id_list = list(unique_seller_ids)
        for i in range(0, len(seller_id_list), 100):
            batch_ids = seller_id_list[i:i+100]
            token_manager.request_permission_for_call(estimated_cost=1)
            seller_data, _, _, tokens_left = fetch_seller_data(api_key, batch_ids)
            token_manager.update_after_call(tokens_left)
            if seller_data and 'sellers' in seller_data:
                seller_data_cache.update(seller_data['sellers'])
    logger.info(f"Fetched data for {len(seller_data_cache)} unique sellers.")


    # 4. Now, process all deals with crash handling
    logger.info("Starting the processing of all collected deals...")
    _process_and_save_deal_page(all_deals_on_all_pages, api_key, xai_api_key, token_manager, business_settings, headers, all_fetched_products, seller_data_cache)
    logger.info("Processing of all collected deals is complete.")

    logger.info(f"--- Diagnostic Backfiller Crash Test Finished ---")
    if os.path.exists(CRASH_LOG_FILE):
        logger.warning(f"A crash was detected! Check '{CRASH_LOG_FILE}' for details.")
    else:
        logger.info("No crashes were detected during the run.")


if __name__ == "__main__":
    logger.info("Starting script execution from __main__.")
    try:
        run_diagnostic_backfill()
    except Exception as e:
        logger.error("An unhandled exception occurred at the top level.", exc_info=True)
    finally:
        logger.info("Script execution finished.")
