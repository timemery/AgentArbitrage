# Restore Dashboard Functionality

import json
import csv
import logging
import sys
import time
import math
import os
from dotenv import load_dotenv
from datetime import datetime

from .keepa_api import (
    fetch_deals_for_deals,
    fetch_product_batch,
    validate_asin,
    fetch_seller_data,
)
from .token_manager import TokenManager
from .field_mappings import FUNCTION_LIST
from .processing import _process_single_deal
from .stable_calculations import infer_sale_events, analyze_sales_performance
from .seller_info import get_all_seller_info
import sqlite3
from .business_calculations import (
    load_settings as business_load_settings,
)

MAX_ASINS_PER_BATCH = 100

def set_scan_status(status_data):
    """Helper to write to the status file."""
    STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scan_status.json')
    try:
        with open(STATUS_FILE, 'w') as f:
            json.dump(status_data, f, indent=4)
    except IOError as e:
        # This will be logged by the Celery worker
        print(f"Error writing status file: {e}")


def run_keepa_script(api_key, no_cache=False, output_dir='data', deal_limit=None, status_update_callback=None):
    """
    Main script to run the Keepa deals fetching and processing script.
    """
    logger = logging.getLogger(__name__) # Use standard logging
    load_dotenv()
    XAI_API_KEY = os.getenv("XAI_TOKEN")
    scan_start_time = time.time()

    def _update_cli_status(status_dict):
        current_status = {}
        STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scan_status.json')
        if os.path.exists(STATUS_FILE):
            try:
                with open(STATUS_FILE, 'r') as f:
                    current_status = json.load(f)
            except (IOError, json.JSONDecodeError):
                pass
        current_status.update(status_dict)
        set_scan_status(current_status)

    try:
        initial_status = {
            "status": "Running",
            "start_time": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
            "message": "Worker has started processing the scan.",
            "task_id": run_keepa_script.request.id
        }
        set_scan_status(initial_status)

        os.makedirs(output_dir, exist_ok=True)
        CSV_PATH = os.path.join(output_dir, "Keepa_Deals_Export.csv")

        with open('keepa_deals/headers.json') as f:
            HEADERS = json.load(f)
            logger.debug(f"Loaded headers: {len(HEADERS)} fields")

        token_manager = TokenManager(api_key)

        def write_csv(rows, deals, diagnostic=False):
            logger.info(f"Entering write_csv. Number of deals: {len(deals)}. Number of rows: {len(rows)}.")
            if len(deals) != len(rows) and not diagnostic:
                logger.warning(f"Mismatch in write_csv: len(deals) is {len(deals)} but len(rows) is {len(rows)}.")

            with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(HEADERS)
                if diagnostic:
                    writer.writerow(['No deals fetched'] + ['-'] * (len(HEADERS) - 1))
                else:
                    for row in rows:
                        row_to_write = []
                        for header in HEADERS:
                            value = row.get(header, '-')
                            if header == 'ASIN' and value != '-':
                                # Apply spreadsheet-specific formatting only for the CSV
                                row_to_write.append(f'="{value}"')
                            else:
                                row_to_write.append(value)
                        writer.writerow(row_to_write)
            logger.info(f"CSV written: {CSV_PATH}")

        logger.info("Starting Keepa_Deals script...")
        
        all_deals = []
        page = 0
        TOKEN_COST_PER_DEAL_PAGE = 5
        while True:
            logger.info(f"Fetching deals page {page}...")
            token_manager.request_permission_for_call(estimated_cost=TOKEN_COST_PER_DEAL_PAGE)
            
            deal_response, _, tokens_left = fetch_deals_for_deals(page, api_key)
            token_manager.update_after_call(tokens_left)

            if not deal_response:
                logger.error(f"Failed to fetch deals for page {page}.")
                break
            deals_page = deal_response.get('deals', {}).get('dr', [])
            if not deals_page:
                logger.info(f"No more deals found on page {page}.")
                break
            all_deals.extend(deals_page)
            if deal_limit and len(all_deals) >= deal_limit:
                break
            page += 1

        deals = all_deals
        deals_to_process = deals[:deal_limit] if deal_limit is not None else deals
        
        if status_update_callback is None:
            status_update_callback = _update_cli_status
        status_update_callback({
            "message": f"Found {len(deals)} total deals. Processing {len(deals_to_process)}.",
            "total_deals": len(deals_to_process), "processed_deals": 0
        })

        if not deals_to_process:
            write_csv([], [], diagnostic=True)
            save_to_database([], HEADERS, logger)
            _update_cli_status({'status': 'Completed', 'message': 'No deals found.'})
            return

        valid_deals_to_process = [d for d in deals_to_process if validate_asin(d.get('asin'))]
        asin_batches = [valid_deals_to_process[i:i + MAX_ASINS_PER_BATCH] for i in range(0, len(valid_deals_to_process), MAX_ASINS_PER_BATCH)]

        # --- Comprehensive Token Safety Check ---
        # This is a critical guard to prevent runaway token usage.
        # It calculates the total estimated cost for the entire process before starting.

        # Force a token refill to ensure the internal count is up-to-date before the check.
        token_manager.refill()

        # Cost to fetch product history (most expensive part)
        COST_PER_PRODUCT = 17  # Approximate cost for history=1, offers=20
        product_fetch_cost = len(valid_deals_to_process) * COST_PER_PRODUCT

        # Cost to fetch seller data (1 token per 100 sellers)
        # This is an estimate, as we don't know the exact number of unique sellers yet.
        # We assume a worst-case of 1 unique seller per product.
        seller_fetch_cost = math.ceil(len(valid_deals_to_process) / 100.0)

        total_estimated_cost = product_fetch_cost + seller_fetch_cost

        # --- Enhanced Logging for Token Debugging ---
        logger.info(f"PRE-FLIGHT TOKEN CHECK: Deals to process={len(valid_deals_to_process)}")
        logger.info(f"PRE-FLIGHT TOKEN CHECK: Calculated total_estimated_cost={total_estimated_cost}")
        logger.info(f"PRE-FLIGHT TOKEN CHECK: Token manager balance BEFORE check={token_manager.tokens}")

        if not token_manager.has_enough_tokens(total_estimated_cost):
            error_msg = f"Insufficient tokens for full run. Estimated Cost: {total_estimated_cost}, Available: {token_manager.tokens}. Aborting task."
            logger.error(error_msg)
            _update_cli_status({'status': 'Failed', 'message': error_msg})
            return  # Hard stop to prevent any token spend

        # --- Product Data Fetching ---
        all_fetched_products_map = {}
        for batch in asin_batches:
            batch_asins = [d['asin'] for d in batch]

            # CRITICAL FIX: Restore the throttling mechanism. This waits if the refill rate is slower than the request rate.
            token_manager.request_permission_for_call(estimated_cost=len(batch_asins) * COST_PER_PRODUCT)

            product_data_response, _, _, tokens_left = fetch_product_batch(api_key, batch_asins, history=1, offers=20)
            token_manager.update_after_call(tokens_left)
            if product_data_response and 'products' in product_data_response:
                for p in product_data_response['products']:
                    all_fetched_products_map[p['asin']] = p

        # --- Seller Data Fetching ---
        unique_seller_ids = {
            offer['sellerId']
            for p in all_fetched_products_map.values()
            for offer in p.get('offers', [])
            if isinstance(offer, dict) and offer.get('sellerId')
        }
        seller_data_cache = {}
        if unique_seller_ids:
            seller_id_list = list(unique_seller_ids)

            # This is a secondary, more accurate check just for the seller part.
            seller_cost = math.ceil(len(seller_id_list) / 100.0)
            if not token_manager.has_enough_tokens(seller_cost):
                 logger.warning(f"Insufficient tokens for seller data fetch. Cost: {seller_cost}, Available: {token_manager.tokens}. Skipping seller info.")
            else:
                for i in range(0, len(seller_id_list), 100):
                    batch_ids = seller_id_list[i:i+100]
                    # Add the throttling back here as well
                    token_manager.request_permission_for_call(estimated_cost=len(batch_ids) / 100.0)
                    seller_data, _, _, tokens_left = fetch_seller_data(api_key, batch_ids)
                    token_manager.update_after_call(tokens_left)
                    if seller_data and 'sellers' in seller_data:
                        seller_data_cache.update(seller_data['sellers'])

        # =================================================================
        # NEW: Multi-stage processing pipeline
        # =================================================================

        # --- Stage 1: Analytics Pre-calculation ---
        # Run analytics first to get data needed for later stages (e.g., seasonality)
        logger.info("Starting Stage 1: Analytics Pre-calculation")
        for asin, product in all_fetched_products_map.items():
            try:
                sale_events, _ = infer_sale_events(product)
                analysis_results = analyze_sales_performance(product, sale_events)
                # Store results back into the main product object
                product['analytics_cache'] = analysis_results
            except Exception as e:
                logger.error(f"ASIN {asin}: Analytics pre-calculation failed: {e}", exc_info=True)
                product['analytics_cache'] = {} # Ensure the key exists
        logger.info("Finished Stage 1.")


        # --- Stage 2: Main Data Processing ---
        logger.info("Starting Stage 2: Main Data Processing")
        business_settings = business_load_settings()
        final_rows = []
        processed_count = 0

        for deal in deals_to_process:
            asin = deal['asin']
            product_data = all_fetched_products_map.get(asin)

            if not product_data:
                final_rows.append({'ASIN': asin, 'Title': 'Product data not found'})
                continue

            try:
                # Combine the original deal info with the full product data
                product_data.update(deal)

                # Call the centralized processing function from processing.py
                processed_row = _process_single_deal(
                    product_data,
                    seller_data_cache=seller_data_cache,
                    xai_api_key=XAI_API_KEY,
                    business_settings=business_settings,
                    headers=HEADERS
                )

                if processed_row:
                    final_rows.append(processed_row)

            except Exception as e:
                logger.error(f"ASIN {asin}: Critical error in main processing loop for deal: {e}", exc_info=True)
                final_rows.append({'ASIN': asin, 'Title': f"Processing Error: {e}"})

            processed_count += 1
            if processed_count % 10 == 0:
                 status_update_callback({"processed_deals": processed_count})

        logger.info("Finished Stage 2.")

        # --- Stage 3: Save to Database ---
        logger.info("Starting Stage 3: Saving to Database")
        write_csv(final_rows, deals_to_process) # Still useful for debugging
        save_to_database(final_rows, HEADERS, logger)
        logger.info("Finished Stage 3.")

        _update_cli_status({'status': 'Completed', 'message': 'Scan completed successfully.'})

    except Exception as e:
        logger.error(f"Main failed: {str(e)}", exc_info=True)
        _update_cli_status({'status': 'Failed', 'message': f"An error occurred: {str(e)}"})

def save_to_database(rows, headers, logger):
    import sqlite3
    import re
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'deals.db')
    TABLE_NAME = 'deals'
    
    logger.info(f"Connecting to database at {DB_PATH}...")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        def sanitize_col_name(name):
            return re.sub(r'[^a-zA-Z0-9_]', '', name.replace(' ', '_').replace('.', '').replace('-', '_').replace('%', 'Percent'))

        sanitized_headers = [sanitize_col_name(h) for h in headers]
        
        cursor.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}")

        cols_sql = []
        for header in sanitized_headers:
            col_type = 'TEXT'
            if 'Price' in header or 'Fee' in header or 'Margin' in header or 'Percent' in header or 'Profit' in header:
                col_type = 'REAL'
            elif 'Rank' in header or 'Count' in header or 'Drops' in header:
                 col_type = 'INTEGER'
            cols_sql.append(f'"{header}" {col_type}')
        
        create_table_sql = f"CREATE TABLE {TABLE_NAME} (id INTEGER PRIMARY KEY AUTOINCREMENT, {', '.join(cols_sql)})"
        cursor.execute(create_table_sql)

        column_names = ', '.join(f'"{h}"' for h in sanitized_headers)
        placeholders = ', '.join(['?'] * len(sanitized_headers))
        insert_sql = f"INSERT INTO {TABLE_NAME} ({column_names}) VALUES ({placeholders})"

        data_to_insert = []
        for row_dict in rows:
            row_tuple = [row_dict.get(h) for h in headers]
            data_to_insert.append(tuple(row_tuple))

        cursor.executemany(insert_sql, data_to_insert)
        conn.commit()
    except Exception as e:
        logger.error(f"Database error: {e}", exc_info=True)
    finally:
        if conn:
            conn.close()

# Other functions like recalculate_deals would go here
