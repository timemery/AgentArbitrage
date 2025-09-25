# keepa_deals/Keepa_Deals.py
# Refactored for integration with AgentArbitrage

import json
import csv
import logging
import sys
import time
import math
import os
from celery_config import celery
from datetime import datetime

from .keepa_api import (
    fetch_deals_for_deals,
    fetch_product_batch,
    validate_asin,
)
from .token_manager import TokenManager
from .field_mappings import FUNCTION_LIST
from .seller_info import get_all_seller_info

def set_scan_status(status_data):
    """Helper to write to the status file."""
    STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scan_status.json')
    try:
        with open(STATUS_FILE, 'w') as f:
            json.dump(status_data, f, indent=4)
    except IOError as e:
        # This will be logged by the Celery worker
        print(f"Error writing status file: {e}")

@celery.task
def run_keepa_script(api_key, no_cache=False, output_dir='data', deal_limit=None, status_update_callback=None):
    """
    Main Celery task to run the Keepa deals fetching and processing script.
    """
    logger = logging.getLogger(__name__) # Use standard logging

    def _update_cli_status(status_dict):
        # Read current status, update, and write back
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

    # Overwrite the status file with a clean initial state
    initial_status = {
        "status": "Running",
        "start_time": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
        "message": "Worker has started processing the scan.",
        "task_id": run_keepa_script.request.id
    }
    set_scan_status(initial_status)

    scan_start_time = time.time() # Start timer at the very beginning
    os.makedirs(output_dir, exist_ok=True)
    CSV_PATH = os.path.join(output_dir, "Keepa_Deals_Export.csv")

    # Load headers
    try:
        # This path needs to be relative to the project structure
        with open('keepa_deals/headers.json') as f:
            HEADERS = json.load(f)
            logger.debug(f"Loaded headers: {len(HEADERS)} fields")
    except Exception as e:
        logger.error(f"Startup failed: Could not load headers.json: {str(e)}")
        return

    # Instantiate the TokenManager
    token_manager = TokenManager(api_key)

    def write_csv(rows, deals, diagnostic=False):
        logger.info(f"Entering write_csv. Number of deals to process: {len(deals)}. Number of rows generated: {len(rows)}.")
        if len(deals) != len(rows) and not diagnostic:
            logger.warning(f"Mismatch in write_csv: len(deals) is {len(deals)} but len(rows) is {len(rows)}. CSV might be incomplete or misaligned.")

        try:
            with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(HEADERS)
                if diagnostic:
                    writer.writerow(['No deals fetched'] + ['-'] * (len(HEADERS) - 1))
                    logger.info(f"Diagnostic CSV written: {CSV_PATH}")
                else:
                    num_to_write = min(len(deals), len(rows))
                    if len(deals) != len(rows):
                         logger.warning(f"write_csv: Writing {num_to_write} rows due to length mismatch between deals ({len(deals)}) and rows ({len(rows)}).")

                    for i in range(num_to_write):
                        deal_obj = deals[i]
                        row_content = rows[i]
                        asin_from_deal = deal_obj.get('asin', 'UNKNOWN_DEAL_ASIN')
                        asin_from_row = row_content.get('ASIN', 'UNKNOWN_ROW_ASIN')

                        non_hyphen_row_items = {k: v for k, v in row_content.items() if v != '-'}
                        logger.debug(f"Writing CSV row for ASIN (from deal obj): {asin_from_deal}, ASIN (from row obj): {asin_from_row}. Non-hyphen count: {len(non_hyphen_row_items)}. Keys: {list(non_hyphen_row_items.keys())}")
                        if asin_from_deal != asin_from_row and asin_from_row not in asin_from_deal :
                            logger.warning(f"ASIN mismatch when writing CSV: Deal ASIN is '{asin_from_deal}', Row ASIN is '{asin_from_row}'.")

                        try:
                            writer.writerow([row_content.get(header, '-') for header in HEADERS])
                        except Exception as e:
                            logger.error(f"Failed to write row to CSV for ASIN {asin_from_row} (from deal: {asin_from_deal}): {str(e)}")
            
            logger.info(f"CSV written: {CSV_PATH} with {num_to_write if not diagnostic else 0} data rows.")
        except Exception as e:
            logger.error(f"Failed to write CSV {CSV_PATH}: {str(e)}")

    try:
        logger.info("Starting Keepa_Deals script...")
        
        # --- Deal Fetching Loop ---
        all_deals = []
        page = 0
        TOKEN_COST_PER_DEAL_PAGE = 5  # Cost for /deal endpoint calls
        while True:
            logger.info(f"Fetching deals page {page}...")
            token_manager.request_permission_for_call(estimated_cost=TOKEN_COST_PER_DEAL_PAGE)
            
            deal_response = fetch_deals_for_deals(page, api_key)
            token_manager.update_from_response(deal_response)

            if not deal_response:
                logger.error(f"Failed to fetch deals for page {page}. Stopping deal fetch.")
                break

            deals_page = deal_response.get('deals', {}).get('dr', [])
            if not deals_page:
                logger.info(f"No more deals found on page {page}.")
                break

            all_deals.extend(deals_page)
            logger.info(f"Fetched {len(deals_page)} deals from page {page}. Total deals so far: {len(all_deals)}")

            # Exit loop if the deal_limit has been reached or exceeded
            if deal_limit and len(all_deals) >= deal_limit:
                logger.info(f"Deal limit of {deal_limit} reached. Stopping deal fetching.")
                break

            page += 1

        deals = all_deals
        logger.info(f"Total deals fetched: {len(deals)}")
        
        deals_to_process = deals
        if deal_limit is not None and deal_limit > 0:
            logger.warning(f"PROCESSING LIMIT ACTIVE: Processing only the first {deal_limit} of {len(deals)} deals.")
            deals_to_process = deals[:deal_limit]
        
        logger.info(f"Deals to process: {len(deals_to_process)}")

        if status_update_callback is None:
            status_update_callback = _update_cli_status

        if status_update_callback:
            initial_time_per_deal = 2 
            initial_etr = len(deals_to_process) * initial_time_per_deal
            status_update_callback({
                "message": f"Found {len(deals)} total deals. Applying limit of {deal_limit}." if deal_limit else f"Found {len(deals)} total deals.",
                "total_deals": len(deals_to_process),
                "processed_deals": 0,
                "etr_seconds": initial_etr
            })

        if not deals_to_process:
            logger.warning("No deals fetched or all filtered out by temporary limit, writing diagnostic CSV and clearing database.")
            write_csv([], [], diagnostic=True)
            save_to_database([], HEADERS, logger)
            logger.info("Script completed with no deals processed.")
            _update_cli_status({
                'status': 'Completed',
                'end_time': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
                'message': 'Scan finished. No deals were found matching the criteria.'
            })
            return
        
        logger.info(f"Starting ASIN processing, found {len(deals_to_process)} deals (after potential temporary limit)")

        MAX_ASINS_PER_BATCH = 50
        ESTIMATED_AVG_COST_PER_ASIN_IN_BATCH = 8
        
        valid_deals_to_process = []
        for deal_idx, deal_obj in enumerate(deals_to_process):
            asin = deal_obj.get('asin', '-')
            if not validate_asin(asin):
                logger.warning(f"Skipping invalid ASIN '{asin}' from deal object: {deal_obj}")
            else:
                valid_deals_to_process.append({'original_index': deal_idx, 'asin': asin, 'deal_obj': deal_obj})

        logger.info(f"Collected {len(valid_deals_to_process)} valid ASINs for batch processing.")

        asin_batches = [valid_deals_to_process[i:i + MAX_ASINS_PER_BATCH] for i in range(0, len(valid_deals_to_process), MAX_ASINS_PER_BATCH)]
        logger.info(f"Created {len(asin_batches)} batches for API calls.")

        all_fetched_products_map = {}
        batch_idx = 0
        max_retries_for_batch = 2
        batch_retry_counts = [0] * len(asin_batches)
        processed_deals_count = 0

        while batch_idx < len(asin_batches):
            current_batch_deals = asin_batches[batch_idx]
            batch_asins = [d['asin'] for d in current_batch_deals]
            
            logger.info(f"Processing Batch {batch_idx + 1}/{len(asin_batches)} (Attempt {batch_retry_counts[batch_idx] + 1}) with {len(batch_asins)} ASINs: {batch_asins[:3]}...")

            estimated_cost = len(batch_asins) * ESTIMATED_AVG_COST_PER_ASIN_IN_BATCH
            token_manager.request_permission_for_call(estimated_cost)

            product_data_response, api_info, _ = fetch_product_batch(api_key, batch_asins, history=1, offers=20)
            token_manager.update_from_response(product_data_response)

            batch_had_critical_error = api_info and api_info.get('error_status_code') and api_info.get('error_status_code') != 200

            if not batch_had_critical_error and product_data_response:
                batch_product_data_list = product_data_response.get('products', [])
                temp_product_map = {p['asin']: p for p in batch_product_data_list if isinstance(p, dict) and 'asin' in p}
                for deal_info in current_batch_deals:
                    asin_to_map = deal_info['asin']
                    if asin_to_map in temp_product_map:
                        all_fetched_products_map[asin_to_map] = temp_product_map[asin_to_map]
                    else:
                        logger.warning(f"ASIN {asin_to_map} was requested in batch but not found in response products. Marking as error.")
                        all_fetched_products_map[asin_to_map] = {'asin': asin_to_map, 'error': True, 'status_code': 'MISSING_IN_BATCH_RESPONSE', 'message': 'ASIN not found in successful batch response products list.'}
                
                processed_deals_count += len(current_batch_deals)
                
                if status_update_callback:
                    elapsed_seconds = time.time() - scan_start_time
                    deals_remaining = len(deals_to_process) - processed_deals_count
                    time_per_deal = elapsed_seconds / processed_deals_count if processed_deals_count > 0 else 0
                    etr_seconds = deals_remaining * time_per_deal if time_per_deal > 0 else 0
                    
                    status_update_callback({
                        "message": f"Processing... {processed_deals_count} of {len(deals_to_process)} deals complete.",
                        "processed_deals": processed_deals_count,
                        "etr_seconds": etr_seconds,
                        "debug_etr": {
                            "elapsed": elapsed_seconds,
                            "processed": processed_deals_count,
                            "time_per_deal": time_per_deal
                        }
                    })

                batch_idx += 1
            else:
                status_code = api_info.get('error_status_code') if api_info else 'UNKNOWN'
                if status_code == 429:
                    if batch_retry_counts[batch_idx] < max_retries_for_batch:
                        batch_retry_counts[batch_idx] += 1
                        logger.error(f"Batch API call received 429 error. Retrying (Attempt {batch_retry_counts[batch_idx] + 1}/3). TokenManager will handle wait.")
                        continue # Retry the same batch
                    else:
                        logger.error(f"Batch API call received 429 error on max retries. Skipping batch {batch_idx + 1}.")
                        for deal_info in current_batch_deals:
                            all_fetched_products_map[deal_info['asin']] = {'asin': deal_info['asin'], 'error': True, 'status_code': 429, 'message': 'Batch skipped after max retries due to 429 error'}
                        batch_idx += 1
                else:
                    logger.error(f"Batch API call failed with non-429 error code: {status_code}. Skipping batch.")
                    for deal_info in current_batch_deals:
                        error_msg_detail = api_info.get('message', 'Batch API call failed') if api_info else 'Batch API call failed'
                        all_fetched_products_map[deal_info['asin']] = {'asin': deal_info['asin'], 'error': True, 'status_code': status_code, 'message': error_msg_detail}
                    batch_idx += 1

        # Seller data is now fetched on-demand inside get_all_seller_info
        
        temp_rows_data = []

        for deal_info in valid_deals_to_process:
            original_deal_obj = deal_info['deal_obj']
            asin = deal_info['asin']
            
            product = all_fetched_products_map.get(asin)

            if not product or product.get('error'):
                logger.error(f"Incomplete or error in product data for ASIN {asin}. Product: {product}")
                placeholder_row_content = {'ASIN': asin}
                for header_key in HEADERS:
                    if header_key not in placeholder_row_content:
                        placeholder_row_content[header_key] = '-'
                temp_rows_data.append({'original_index': deal_info['original_index'], 'data': placeholder_row_content})
                continue

            row = {}
            try:
                for header, func in zip(HEADERS, FUNCTION_LIST):
                    if func:
                        try:
                            # Pass api_key to functions that need it
                            if func.__name__ in ['last_update', 'last_price_change']:
                                result = func(original_deal_obj, logger, product)
                            elif func.__name__ == 'deal_found':
                                result = func(original_deal_obj, logger)
                            else:
                                result = func(product)
                            
                            logger.debug(f"ASIN {asin}, Header: {header}, Func: {func.__name__}, Result: {result}")
                            row.update(result)
                        except Exception as e:
                            logger.error(f"Function {func.__name__} failed for ASIN {asin}, header '{header}': {e}")
                            row[header] = '-'
                
                if 'ASIN' not in row or row.get('ASIN') != asin:
                    row['ASIN'] = asin
                
                temp_rows_data.append({'original_index': deal_info['original_index'], 'data': row})

            except Exception as e:
                logger.error(f"Error processing ASIN {asin} (outer loop): {e}")
                placeholder_row_content = {'ASIN': asin}
                temp_rows_data.append({'original_index': deal_info['original_index'], 'data': placeholder_row_content})
        
        # --- New Seller Info Processing Loop ---
        logger.info("Starting decoupled seller information processing...")
        for item in temp_rows_data:
            row_data = item['data']
            asin = row_data.get('ASIN')
            if not asin:
                continue

            product = all_fetched_products_map.get(asin)
            if product and not product.get('error'):
                try:
                    offers_to_log = product.get('offers', [])
                    logger.debug(f"ASIN {asin}: Passing {len(offers_to_log)} offers to get_all_seller_info. Data: {json.dumps(offers_to_log)}")

                    seller_info = get_all_seller_info(product, api_key=api_key, token_manager=token_manager)
                    row_data.update(seller_info)
                    
                    logger.info(f"ASIN {asin}: Successfully processed and updated seller info.")
                except Exception as e:
                    logger.error(f"ASIN {asin}: Failed to get seller info in decoupled loop: {e}", exc_info=True)
            else:
                logger.warning(f"ASIN {asin}: Skipping seller info processing due to missing or error in product data.")
        logger.info("Finished decoupled seller information processing.")
        # --- End of New Loop ---

        # --- New Business Logic Calculations Loop ---
        from .business_calculations import (
            load_settings,
            calculate_total_amz_fees,
            calculate_all_in_cost,
            calculate_profit_and_margin,
            calculate_min_listing_price,
        )
        
        logger.info("Starting business logic calculations...")
        business_settings = load_settings()

        for item in temp_rows_data:
            row_data = item['data']
            asin = row_data.get('ASIN')
            if not asin:
                continue
            
            try:
                # Safely parse required values from the row_data dictionary
                def parse_price(value_str):
                    if isinstance(value_str, (int, float)):
                        return float(value_str)
                    if not isinstance(value_str, str) or value_str.strip() in ['-', 'N/A', '']:
                        return 0.0
                    try:
                        return float(value_str.strip().replace('$', '').replace(',', ''))
                    except ValueError:
                        logger.warning(f"Could not parse price value '{value_str}'. Defaulting to 0.0.")
                        return 0.0

                def parse_percent(value_str):
                    if isinstance(value_str, (int, float)):
                        return float(value_str)
                    if not isinstance(value_str, str) or value_str.strip() in ['-', 'N/A', '']:
                        return 0.0
                    try:
                        return float(value_str.strip().replace('%', ''))
                    except ValueError:
                        logger.warning(f"Could not parse percent value '{value_str}'. Defaulting to 0.0.")
                        return 0.0

                peak_price = parse_price(row_data.get('Expected Peak Price', '0'))
                fba_fee = parse_price(row_data.get('FBA Pick&Pack Fee', '0'))
                referral_percent = parse_percent(row_data.get('Referral Fee %', '0'))
                best_price = parse_price(row_data.get('Best Price', '0'))

                if peak_price > 0 and best_price > 0:
                    shipping_included_str = row_data.get('Shipping Included', 'no')
                    shipping_included_flag = shipping_included_str.lower() == 'yes'

                    total_amz_fees = calculate_total_amz_fees(peak_price, fba_fee, referral_percent)
                    all_in_cost = calculate_all_in_cost(best_price, total_amz_fees, business_settings, shipping_included_flag)
                    profit_margin_dict = calculate_profit_and_margin(peak_price, all_in_cost)
                    min_listing_price = calculate_min_listing_price(all_in_cost, business_settings)

                    row_data['Total AMZ fees'] = total_amz_fees
                    row_data['All-in Cost'] = all_in_cost
                    row_data['Profit'] = profit_margin_dict['profit']
                    row_data['Margin'] = profit_margin_dict['margin']
                    row_data['Min. Listing Price'] = min_listing_price
                else:
                    row_data['Total AMZ fees'] = 0.0
                    row_data['All-in Cost'] = 0.0
                    row_data['Profit'] = 0.0
                    row_data['Margin'] = 0.0
                    row_data['Min. Listing Price'] = 0.0

            except (ValueError, TypeError) as e:
                logger.error(f"ASIN {asin}: Could not perform business calculations due to a parsing error: {e}")
                row_data['Total AMZ fees'] = '-'
                row_data['All-in Cost'] = '-'
                row_data['Profit'] = '-'
                row_data['Margin'] = '-'
                row_data['Min. Listing Price'] = '-'
        
        logger.info("Finished business logic calculations.")

        # --- New Analytics Calculations Loop ---
        from .new_analytics import get_changed, get_1yr_avg_sale_price, get_percent_discount, get_trend
        logger.info("Starting new analytics calculations...")
        for item in temp_rows_data:
            row_data = item['data']
            asin = row_data.get('ASIN')
            if not asin:
                continue

            product = all_fetched_products_map.get(asin)
            if product and not product.get('error'):
                try:
                    best_price_str = row_data.get('Best Price', '-')

                    changed_info = get_changed(product, logger=logger)
                    yr_avg_price_info = get_1yr_avg_sale_price(product, logger=logger)
                    trend_info = get_trend(product, logger=logger)
                    # Now call get_percent_discount with the calculated best_price
                    percent_discount_info = get_percent_discount(product, best_price_str, logger=logger)

                    row_data.update(changed_info)
                    row_data.update(yr_avg_price_info)
                    row_data.update(trend_info)
                    row_data.update(percent_discount_info)

                    logger.info(f"ASIN {asin}: Successfully processed new analytics.")
                except Exception as e:
                    logger.error(f"ASIN {asin}: Failed to get new analytics in dedicated loop: {e}", exc_info=True)
        logger.info("Finished new analytics calculations.")
        # --- End of New Analytics Loop ---
        # --- End of Business Logic Loop ---

        final_processed_rows = [None] * len(deals_to_process)

        for item in temp_rows_data:
            idx = item['original_index']
            if 0 <= idx < len(final_processed_rows):
                final_processed_rows[idx] = item['data']
            else:
                logger.error(f"Original index {idx} from temp_rows_data is out of bounds for final_processed_rows (len: {len(final_processed_rows)}). Data: {item['data']}")

        for i, deal_obj in enumerate(deals_to_process):
            if final_processed_rows[i] is None:
                asin_for_placeholder = deal_obj.get('asin', f'UNKNOWN_ASIN_AT_INDEX_{i}')
                logger.warning(f"Creating final placeholder for ASIN '{asin_for_placeholder}' (original index {i}) as it was not in processed temp_rows_data.")
                placeholder = {'ASIN': f"SKIPPED_OR_ERROR_ASIN_{asin_for_placeholder[:10]}"}
                for header_key in HEADERS:
                    if header_key not in placeholder:
                        placeholder[header_key] = '-'
                final_processed_rows[i] = placeholder
        
        write_csv(final_processed_rows, deals_to_process)
        
        # Save results to database
        save_to_database(final_processed_rows, HEADERS, logger)

        logger.info("Script completed!")
        _update_cli_status({
            'status': 'Completed',
            'end_time': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
            'message': 'Scan completed successfully.',
            'output_file': f"{output_dir}/Keepa_Deals_Export.csv"
        })
    except Exception as e:
        logger.error(f"Main failed: {str(e)}", exc_info=True)
        _update_cli_status({
            'status': 'Failed',
            'end_time': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z',
            'message': f"An error occurred: {str(e)}"
        })

def save_to_database(rows, headers, logger):
    import sqlite3
    import re

    # Use a path relative to the app's instance folder if possible, or root for now.
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'deals.db')
    TABLE_NAME = 'deals'
    
    logger.info(f"Connecting to database at {DB_PATH}...")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Sanitize headers for column names
        def sanitize_col_name(name):
            # Replace spaces and special characters with underscores
            name = name.replace(' ', '_').replace('.', '').replace('-', '_').replace('%', 'Percent')
            # Remove any other non-alphanumeric characters except underscore
            return re.sub(r'[^a-zA-Z0-9_]', '', name)

        sanitized_headers = [sanitize_col_name(h) for h in headers]
        
        # Create table schema
        # Drop table if it exists to ensure a fresh start
        logger.info(f"Dropping existing '{TABLE_NAME}' table if it exists.")
        cursor.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}")

        # Create table with sanitized column names
        create_table_sql = f"CREATE TABLE {TABLE_NAME} (id INTEGER PRIMARY KEY AUTOINCREMENT, "
        cols_sql = []
        for header in sanitized_headers:
            # Simple type inference
            if 'Price' in header or 'Fee' in header or 'Margin' in header or 'Percent' in header or 'Profit' in header:
                cols_sql.append(f'"{header}" REAL')
            elif 'Rank' in header or 'Count' in header or 'Drops' in header:
                 cols_sql.append(f'"{header}" INTEGER')
            else:
                cols_sql.append(f'"{header}" TEXT')
        create_table_sql += ", ".join(cols_sql) + ")"
        
        logger.info(f"Creating new '{TABLE_NAME}' table.")
        logger.debug(f"CREATE TABLE statement: {create_table_sql}")
        cursor.execute(create_table_sql)

        # Insert data
        logger.info(f"Inserting {len(rows)} rows into '{TABLE_NAME}' table.")
        
        # Corrected f-string syntax to avoid backslash issue.
        # This wraps each sanitized header in double quotes for the SQL statement.
        column_names = ', '.join(f'"{h}"' for h in sanitized_headers)
        placeholders = ', '.join(['?'] * len(sanitized_headers))
        insert_sql = f"INSERT INTO {TABLE_NAME} ({column_names}) VALUES ({placeholders})"
        logger.debug(f"INSERT statement: {insert_sql}")

        data_to_insert = []
        # Get the schema to check column types
        cursor.execute(f"PRAGMA table_info({TABLE_NAME})")
        schema_info = {row[1]: row[2] for row in cursor.fetchall()} # Maps sanitized_col_name -> type

        for row_dict in rows:
            row_tuple = []
            for header in headers:
                sanitized_header = sanitize_col_name(header)
                col_type = schema_info.get(sanitized_header, 'TEXT')
                is_numeric_column = 'REAL' in col_type or 'INT' in col_type

                value = row_dict.get(header)

                if is_numeric_column:
                    if value is None or (isinstance(value, str) and value in ['-', 'N/A', '']):
                        row_tuple.append(None)
                    else:
                        try:
                            cleaned_value = str(value).replace('$', '').replace(',', '').replace('%', '').strip()
                            row_tuple.append(float(cleaned_value))
                        except (ValueError, TypeError):
                            logger.warning(f"Could not convert value '{value}' to float for numeric column '{header}'. Storing as NULL.")
                            row_tuple.append(None)
                else:
                    if value is None or (isinstance(value, str) and value == '-'):
                        row_tuple.append(None)
                    else:
                        row_tuple.append(str(value))
            data_to_insert.append(tuple(row_tuple))

        cursor.executemany(insert_sql, data_to_insert)
        
        conn.commit()
        logger.info(f"Successfully inserted {cursor.rowcount} rows into the database.")

    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred during database operation: {e}")
    finally:
        if conn:
            conn.close()
            logger.info("Database connection closed.")