# keepa_deals/Keepa_Deals.py
# Refactored for integration with AgentArbitrage

import json
import csv
import logging
import sys
import time
import math
import os

from .keepa_api import (
    fetch_deals_for_deals,
    fetch_product_batch,
    validate_asin,
    update_and_check_quota,
)
from .field_mappings import FUNCTION_LIST

def run_keepa_script(api_key, logger, no_cache=False, output_dir='data', deal_limit=None, status_update_callback=None):
    """
    Main function to run the Keepa deals fetching and processing script.
    """
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

    # --- Jules: Local Quota Management Constants & State ---
    MAX_QUOTA_TOKENS = 300
    TOKENS_PER_MINUTE_REFILL = 5
    REFILL_CALCULATION_INTERVAL_SECONDS = 60
    ESTIMATED_AVG_COST_PER_ASIN_IN_BATCH = 6
    TOKEN_COST_PER_DEAL_PAGE = 1
    MIN_QUOTA_THRESHOLD_BEFORE_PAUSE = 25
    DEFAULT_LOW_QUOTA_PAUSE_SECONDS = 900
    MIN_TIME_SINCE_LAST_CALL_SECONDS = 60

    current_available_tokens = MAX_QUOTA_TOKENS
    last_refill_calculation_time = time.time()
    LAST_API_CALL_TIMESTAMP = time.time()

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
        
        all_deals = []
        page = 0
        while True:
            current_available_tokens, last_refill_calculation_time = update_and_check_quota(logger, current_available_tokens, last_refill_calculation_time, MIN_QUOTA_THRESHOLD_BEFORE_PAUSE, DEFAULT_LOW_QUOTA_PAUSE_SECONDS, TOKENS_PER_MINUTE_REFILL, REFILL_CALCULATION_INTERVAL_SECONDS, MAX_QUOTA_TOKENS)
            
            required_tokens_for_deal_page = TOKEN_COST_PER_DEAL_PAGE
            if current_available_tokens < required_tokens_for_deal_page:
                tokens_needed = required_tokens_for_deal_page - current_available_tokens
                refill_rate_per_minute = TOKENS_PER_MINUTE_REFILL 
                wait_time_seconds = 0
                if refill_rate_per_minute > 0:
                    wait_time_seconds = math.ceil((tokens_needed / refill_rate_per_minute) * 60)
                else:
                    wait_time_seconds = DEFAULT_LOW_QUOTA_PAUSE_SECONDS 
                
                logger.warning(
                    f"Insufficient tokens for fetching deal page {page}. "
                    f"Have: {current_available_tokens:.2f}, Need: {required_tokens_for_deal_page}. "
                    f"Waiting for approx. {wait_time_seconds // 60} minutes for tokens to refill."
                )
                time.sleep(wait_time_seconds)
                current_available_tokens, last_refill_calculation_time = update_and_check_quota(logger, current_available_tokens, last_refill_calculation_time, MIN_QUOTA_THRESHOLD_BEFORE_PAUSE, DEFAULT_LOW_QUOTA_PAUSE_SECONDS, TOKENS_PER_MINUTE_REFILL, REFILL_CALCULATION_INTERVAL_SECONDS, MAX_QUOTA_TOKENS)

            logger.info(f"Fetching deals page {page}...")
            
            current_time_deal_call = time.time()
            time_since_last_api_call = current_time_deal_call - LAST_API_CALL_TIMESTAMP
            if time_since_last_api_call < MIN_TIME_SINCE_LAST_CALL_SECONDS:
                deal_wait_duration = MIN_TIME_SINCE_LAST_CALL_SECONDS - time_since_last_api_call
                logger.info(f"Pre-emptive pause for deal page fetch: Last API call was {time_since_last_api_call:.2f}s ago. Waiting {deal_wait_duration:.2f}s.")
                time.sleep(deal_wait_duration)
            
            deals_page = fetch_deals_for_deals(page, api_key)
            LAST_API_CALL_TIMESTAMP = time.time()

            if deals_page:
                current_available_tokens -= TOKEN_COST_PER_DEAL_PAGE
                logger.info(f"Token consumed for deal page {page}. Cost: {TOKEN_COST_PER_DEAL_PAGE}. Tokens remaining: {current_available_tokens:.2f}")
            
            if not deals_page:
                logger.info(f"No more deals found on page {page}.")
                break
            all_deals.extend(deals_page)
            logger.info(f"Fetched {len(deals_page)} deals from page {page}. Total deals so far: {len(all_deals)}")
            page += 1

        deals = all_deals
        logger.info(f"Total deals fetched: {len(deals)}")
        
        deals_to_process = deals
        if deal_limit is not None and deal_limit > 0:
            logger.warning(f"PROCESSING LIMIT ACTIVE: Processing only the first {deal_limit} of {len(deals)} deals.")
            deals_to_process = deals[:deal_limit]
        
        logger.info(f"Deals to process: {len(deals_to_process)}")

        # Initial status update with total deals
        if status_update_callback:
            # Provide a rough initial ETR based on a conservative guess of time per deal
            # This avoids showing "Calculating..." for a long time.
            # 1.2s/deal is based on 60s API delay per 50 deals. Let's use 2s for a buffer.
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
            return
        
        logger.info(f"Starting ASIN processing, found {len(deals_to_process)} deals (after potential temporary limit)")

        MAX_ASINS_PER_BATCH = 50
        
        valid_deals_to_process = []
        for deal_idx, deal_obj in enumerate(deals_to_process):
            asin = deal_obj.get('asin', '-')
            if not validate_asin(asin):
                logger.warning(f"Skipping invalid ASIN '{asin}' from deal object: {deal_obj}")
            else:
                valid_deals_to_process.append({'original_index': deal_idx, 'asin': asin, 'deal_obj': deal_obj})

        logger.info(f"Collected {len(valid_deals_to_process)} valid ASINs for batch processing.")

        asin_batches = []
        for i in range(0, len(valid_deals_to_process), MAX_ASINS_PER_BATCH):
            batch_deals = valid_deals_to_process[i:i + MAX_ASINS_PER_BATCH]
            asin_batches.append(batch_deals)

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

            current_available_tokens, last_refill_calculation_time = update_and_check_quota(logger, current_available_tokens, last_refill_calculation_time, MIN_QUOTA_THRESHOLD_BEFORE_PAUSE, DEFAULT_LOW_QUOTA_PAUSE_SECONDS, TOKENS_PER_MINUTE_REFILL, REFILL_CALCULATION_INTERVAL_SECONDS, MAX_QUOTA_TOKENS)

            required_tokens_for_batch = len(batch_asins) * ESTIMATED_AVG_COST_PER_ASIN_IN_BATCH
            if current_available_tokens < required_tokens_for_batch:
                tokens_needed_for_batch = required_tokens_for_batch - current_available_tokens
                refill_rate_per_minute_batch = TOKENS_PER_MINUTE_REFILL
                wait_time_seconds_batch = 0
                if refill_rate_per_minute_batch > 0:
                    wait_time_seconds_batch = math.ceil((tokens_needed_for_batch / refill_rate_per_minute_batch) * 60)
                else:
                    wait_time_seconds_batch = DEFAULT_LOW_QUOTA_PAUSE_SECONDS

                logger.warning(
                    f"Insufficient tokens for product batch {batch_idx + 1}. "
                    f"Have: {current_available_tokens:.2f}, Need: {required_tokens_for_batch}. "
                    f"Waiting for approx. {wait_time_seconds_batch // 60} minutes for tokens to refill."
                )
                time.sleep(wait_time_seconds_batch)
                current_available_tokens, last_refill_calculation_time = update_and_check_quota(logger, current_available_tokens, last_refill_calculation_time, MIN_QUOTA_THRESHOLD_BEFORE_PAUSE, DEFAULT_LOW_QUOTA_PAUSE_SECONDS, TOKENS_PER_MINUTE_REFILL, REFILL_CALCULATION_INTERVAL_SECONDS, MAX_QUOTA_TOKENS)

            current_time_batch_call = time.time()
            time_since_last_api_call_batch = current_time_batch_call - LAST_API_CALL_TIMESTAMP
            if time_since_last_api_call_batch < MIN_TIME_SINCE_LAST_CALL_SECONDS:
                batch_wait_duration = MIN_TIME_SINCE_LAST_CALL_SECONDS - time_since_last_api_call_batch
                logger.info(f"Pre-emptive pause for product batch: Last API call was {time_since_last_api_call_batch:.2f}s ago. Waiting {batch_wait_duration:.2f}s.")
                time.sleep(batch_wait_duration)

            batch_product_data_list, api_info, actual_batch_cost = fetch_product_batch(api_key, batch_asins, history=1, offers=20)
            LAST_API_CALL_TIMESTAMP = time.time()

            batch_had_critical_error = False
            if api_info.get('error_status_code') and api_info.get('error_status_code') != 200:
                batch_had_critical_error = True
                logger.error(f"Batch API call for ASINs {batch_asins[:3]}... failed with status code: {api_info.get('error_status_code')}.")

            if not batch_had_critical_error:
                current_available_tokens -= actual_batch_cost
                logger.info(f"Tokens consumed for BATCH. Cost: {actual_batch_cost}. Tokens remaining: {current_available_tokens:.2f}.")
                
                temp_product_map = {p['asin']: p for p in batch_product_data_list if isinstance(p, dict) and 'asin' in p}
                for deal_info in current_batch_deals:
                    asin_to_map = deal_info['asin']
                    if asin_to_map in temp_product_map:
                        all_fetched_products_map[asin_to_map] = temp_product_map[asin_to_map]
                    else:
                        logger.warning(f"ASIN {asin_to_map} was requested in batch but not found in response products. Marking as error.")
                        all_fetched_products_map[asin_to_map] = {'asin': asin_to_map, 'error': True, 'status_code': 'MISSING_IN_BATCH_RESPONSE', 'message': 'ASIN not found in successful batch response products list.'}
                
                processed_deals_count += len(current_batch_deals)
                
                # Update status with progress
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
                if batch_idx < len(asin_batches):
                    batch_retry_counts[batch_idx] = 0 
                continue

            else:
                if actual_batch_cost > 0:
                    current_available_tokens -= actual_batch_cost
                    logger.warning(
                        f"Batch fetch critically failed (status: {api_info.get('error_status_code')}) but Keepa reported {actual_batch_cost} tokens consumed for this attempt. "
                        f"Deducting. Tokens remaining: {current_available_tokens:.2f}."
                    )
                else:
                    logger.error(
                        f"Batch fetch critically failed for ASINs: {batch_asins[:3]}... "
                        f"No tokens reported by Keepa as consumed for this specific failed attempt (Reported cost for attempt: {actual_batch_cost}, status: {api_info.get('error_status_code')})."
                    )
                
                if api_info.get('error_status_code') == 429:
                    if batch_retry_counts[batch_idx] < max_retries_for_batch:
                        batch_retry_counts[batch_idx] += 1
                        
                        pause_duration_seconds = 0
                        if batch_retry_counts[batch_idx] == 1:
                            pause_duration_seconds = 900
                        elif batch_retry_counts[batch_idx] == 2:
                            pause_duration_seconds = 1800
                        
                        logger.error(f"Batch API call received 429 error. Attempt {batch_retry_counts[batch_idx] + 1}/3 for this batch. Initiating {pause_duration_seconds // 60}-minute recovery pause.")
                        time.sleep(pause_duration_seconds)
                        logger.info(f"Recovery pause complete ({pause_duration_seconds // 60} mins). Updating quota before retrying batch.")
                        current_available_tokens, last_refill_calculation_time = update_and_check_quota(logger, current_available_tokens, last_refill_calculation_time, MIN_QUOTA_THRESHOLD_BEFORE_PAUSE, DEFAULT_LOW_QUOTA_PAUSE_SECONDS, TOKENS_PER_MINUTE_REFILL, REFILL_CALCULATION_INTERVAL_SECONDS, MAX_QUOTA_TOKENS)
                    else:
                        logger.error(f"Batch API call received 429 error on attempt 3/3 for batch {batch_idx + 1}. Max retries reached. Skipping this batch.")
                        for deal_info in current_batch_deals:
                            all_fetched_products_map[deal_info['asin']] = {'asin': deal_info['asin'], 'error': True, 'status_code': 429, 'message': 'Batch skipped after max retries due to 429 error'}
                        batch_idx += 1
                        if batch_idx < len(asin_batches):
                            batch_retry_counts[batch_idx] = 0
                else:
                    for deal_info in current_batch_deals:
                        error_msg_detail = api_info.get('message', 'Batch API call failed with non-429 error')
                        all_fetched_products_map[deal_info['asin']] = {'asin': deal_info['asin'], 'error': True, 'status_code': api_info.get('error_status_code', 'BATCH_CALL_FAILED_NON_429'), 'message': error_msg_detail}
                    batch_idx += 1
                    if batch_idx < len(asin_batches):
                        batch_retry_counts[batch_idx] = 0
                continue

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
                            if func.__name__ == 'last_update' or func.__name__ == 'last_price_change':
                                result = func(original_deal_obj, logger, product)
                            elif func.__name__ == 'deal_found':
                                result = func(original_deal_obj, logger)
                            elif func.__name__ in ['get_best_price', 'get_seller_rank', 'get_seller_quality_score']:
                                result = func(product, api_key=api_key)
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
    except Exception as e:
        logger.error(f"Main failed: {str(e)}")

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
        for row_dict in rows:
            row_tuple = []
            for header in headers:  # Use original headers to look up in dict
                value = row_dict.get(header, None)
                
                # Special handling for ASIN to ensure it's always a string
                if header == 'ASIN':
                    row_tuple.append(str(value) if value is not None else None)
                    continue

                # Sanitize other data for DB insertion
                if isinstance(value, str):
                    if value == '-':
                        row_tuple.append(None)
                    else:
                        try:
                            cleaned_value = value.replace('$', '').replace(',', '').replace('%', '')
                            row_tuple.append(float(cleaned_value))
                        except (ValueError, TypeError):
                            row_tuple.append(value)
                else:
                    row_tuple.append(value)
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
