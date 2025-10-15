# keepa_deals/recalculator.py
import json
import logging
import time
import os
import re
from dotenv import load_dotenv
from celery_config import celery
import sqlite3
from .keepa_api import fetch_product_batch
from .token_manager import TokenManager
from .field_mappings import FUNCTION_LIST
from .seller_info import get_all_seller_info
from .business_calculations import (
    load_settings as business_load_settings,
    calculate_total_amz_fees,
    calculate_all_in_cost,
    calculate_profit_and_margin,
    calculate_min_listing_price,
)
from .new_analytics import get_1yr_avg_sale_price, get_percent_discount, get_trend
from .seasonality_classifier import classify_seasonality, get_sells_period
from .processing import clean_numeric_values

logger = logging.getLogger(__name__)

def set_recalc_status(status_data):
    """Helper to write to the recalculation status file."""
    RECALC_STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'recalc_status.json')
    try:
        with open(RECALC_STATUS_FILE, 'w') as f:
            json.dump(status_data, f, indent=4)
    except IOError as e:
        logger.error(f"Error writing recalc status file: {e}")

def _sanitize_col_name(name):
    """Helper to sanitize column names for SQLite."""
    name = name.replace(' ', '_').replace('.', '').replace('-', '_').replace('%', 'Percent')
    return re.sub(r'[^a-zA-Z0-9_]', '', name)

@celery.task
def recalculate_deals():
    """
    Celery task to perform a full data refresh for all deals in the database.
    This version is refactored for clarity, robustness, and better error handling.
    """
    load_dotenv()
    KEEPA_API_KEY = os.getenv("KEEPA_API_KEY")
    XAI_API_KEY = os.getenv("XAI_TOKEN")
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'deals.db')

    set_recalc_status({"status": "Running", "message": "Starting full data refresh..."})
    task_start_time = time.time()

    try:
        # 1. Fetch all ASINs from the database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT asin FROM deals")
        asins_to_refresh = [row[0] for row in cursor.fetchall()]
        conn.close()

        if not asins_to_refresh:
            logger.info("Recalculation: No deals found in the database.")
            set_recalc_status({"status": "Completed", "message": "No deals to recalculate."})
            return

        total_deals = len(asins_to_refresh)
        logger.info(f"Recalculation: Found {total_deals} deals to refresh.")
        set_recalc_status({
            "status": "Running",
            "message": f"Found {total_deals} deals. Fetching fresh data...",
            "total_deals": total_deals, "processed_deals": 0
        })

        # 2. Initialize Managers and Settings
        token_manager = TokenManager(KEEPA_API_KEY)
        token_manager.sync_tokens() # Explicitly sync tokens at the start
        business_settings = business_load_settings()

        # 3. Fetch fresh product data in batches
        MAX_ASINS_PER_BATCH = 50
        asin_batches = [asins_to_refresh[i:i + MAX_ASINS_PER_BATCH] for i in range(0, len(asins_to_refresh), MAX_ASINS_PER_BATCH)]
        all_fetched_products_map = {}
        processed_count = 0

        for i, batch_asins in enumerate(asin_batches):
            logger.info(f"Recalculation: Fetching product data for Batch {i + 1}/{len(asin_batches)}")
            # A more realistic token estimation
            token_manager.request_permission_for_call(estimated_cost=len(batch_asins) * 10)

            product_data_response, api_info, _, tokens_left = fetch_product_batch(KEEPA_API_KEY, batch_asins, history=1, offers=20)
            if tokens_left is not None:
                token_manager.update_after_call(tokens_left)

            if not (api_info and api_info.get('error_status_code') and api_info.get('error_status_code') != 200) and product_data_response:
                batch_products = {p['asin']: p for p in product_data_response.get('products', []) if 'asin' in p}
                all_fetched_products_map.update(batch_products)
            else:
                logger.error(f"Recalculation: API call for batch {i+1} failed. Error: {api_info.get('message', 'Unknown API Error')}. Skipping batch.")

            processed_count += len(batch_asins)
            set_recalc_status({
                "status": "Running",
                "message": f"Step 1/3: Fetched data for {processed_count}/{total_deals} deals.",
                "total_deals": total_deals, "processed_deals": processed_count
            })

        # 4. Process data in stages, creating a list of row dictionaries
        logger.info("Recalculation: Starting data enrichment pipeline...")
        all_rows_data = []
        for asin, product_data in all_fetched_products_map.items():
            if not product_data or product_data.get('error'):
                logger.warning(f"Recalculation: Skipping ASIN {asin} due to fetch error.")
                continue

            # Create a base row dictionary to be enriched
            row = {'ASIN': asin}
            all_rows_data.append(row)

        # STAGE 1: Base product info from field_mappings.py
        set_recalc_status({"status": "Running", "message": "Step 2/3: Processing deal data..."})
        try:
            with open('keepa_deals/headers.json') as f:
                HEADERS = json.load(f)
        except Exception as e:
            logger.error(f"Recalc (Stage 1): Could not load headers.json. Aborting. Error: {e}", exc_info=True)
            set_recalc_status({"status": "Failed", "message": "Could not load headers.json."})
            return

        for row in all_rows_data:
            asin = row['ASIN']
            product_data = all_fetched_products_map.get(asin)
            if not product_data: continue

            try:
                for header, func in zip(HEADERS, FUNCTION_LIST):
                    if func:
                        result = func(product_data)
                        row.update(result)
            except Exception as e:
                logger.error(f"Recalc (Stage 1): Error processing base info for ASIN {asin}. Error: {e}", exc_info=True)

        # STAGE 2: Pre-fetch all seller data for efficiency
        set_recalc_status({"status": "Running", "message": "Step 2/4: Pre-fetching seller data..."})
        logger.info("Recalculation: Pre-fetching all seller data...")
        unique_seller_ids = set()
        for product in all_fetched_products_map.values():
            for offer in product.get('offers', []):
                if offer.get('sellerId'):
                    unique_seller_ids.add(offer['sellerId'])

        from .keepa_api import fetch_seller_data
        seller_data_cache = {}
        if unique_seller_ids:
            seller_id_list = list(unique_seller_ids)
            for i in range(0, len(seller_id_list), 100):
                batch_seller_ids = seller_id_list[i:i+100]
                seller_data_response, _, _, tokens_left = fetch_seller_data(KEEPA_API_KEY, batch_seller_ids)
                if tokens_left is not None:
                    token_manager.update_after_call(tokens_left)
                if seller_data_response and 'sellers' in seller_data_response:
                    seller_data_cache.update(seller_data_response['sellers'])
        logger.info(f"Recalculation: Fetched data for {len(seller_data_cache)} unique sellers.")


        # STAGE 3: Process Analytics, Business Calcs, and Seasonality
        set_recalc_status({"status": "Running", "message": "Step 3/4: Processing analytics and costs..."})

        for i, row in enumerate(all_rows_data):
            asin = row['ASIN']
            product_data = all_fetched_products_map.get(asin)
            if not product_data: continue

            # Seller Info (using the pre-fetched cache)
            try:
                row.update(get_all_seller_info(product_data, seller_data_cache=seller_data_cache))
            except Exception as e:
                logger.error(f"Recalc (Seller): Error for ASIN {asin}. Error: {e}", exc_info=True)

            # Business Calculations
            try:
                peak_price = float(str(row.get('Expected Peak Price', '0')).replace('$', '').replace(',', ''))
                best_price = float(str(row.get('Best Price', '0')).replace('$', '').replace(',', ''))
                if peak_price > 0 and best_price > 0:
                    total_fees = calculate_total_amz_fees(peak_price, float(str(row.get('FBA Pick&Pack Fee','0')).replace(',','')), float(str(row.get('Referral Fee %', '0')).replace('%','')))
                    all_cost = calculate_all_in_cost(best_price, total_fees, business_settings, str(row.get('Shipping Included', 'no')).lower() == 'yes')
                    profit_margin = calculate_profit_and_margin(peak_price, all_cost)
                    row.update({'Total AMZ fees': total_fees, 'All-in Cost': all_cost, 'Profit': profit_margin['profit'], 'Margin': profit_margin['margin'], 'Min. Listing Price': calculate_min_listing_price(all_cost, business_settings)})
            except Exception as e:
                 logger.error(f"Recalc (Biz Calcs): Error for ASIN {asin}. Error: {e}", exc_info=True)

            # New Analytics
            try:
                row.update(get_1yr_avg_sale_price(product_data, logger=logger))
                row.update(get_trend(product_data, logger=logger))
                row.update(get_percent_discount(row.get('1yr. Avg.', '-'), row.get('Best Price', '-'), logger=logger))
            except Exception as e:
                logger.error(f"Recalc (Analytics): Error for ASIN {asin}. Error: {e}", exc_info=True)

            # Seasonality
            try:
                detailed_season = classify_seasonality(row.get('Title', ''), row.get('Categories - Sub', ''), row.get('Manufacturer', ''), xai_api_key=XAI_API_KEY)
                row['Detailed_Seasonality'], row['Sells'] = ("None", "All Year") if detailed_season == "Year-round" else (detailed_season, get_sells_period(detailed_season))
            except Exception as e:
                logger.error(f"Recalc (Seasonality): Error for ASIN {asin}. Error: {e}", exc_info=True)

            # Clean the numeric values
            row = clean_numeric_values(row)

            if (i + 1) % 10 == 0: # Update status every 10 deals
                 set_recalc_status({
                    "status": "Running",
                    "message": f"Step 3/4: Processing analytics for {i+1}/{total_deals} deals.",
                    "total_deals": total_deals, "processed_deals": processed_count + i + 1
                })


        # 5. Update the database
        logger.info("Recalculation: Starting database update...")
        set_recalc_status({"status": "Running", "message": "Step 4/4: Saving updated data to database..."})
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        update_count = 0
        for row in all_rows_data:
            try:
                update_dict = {_sanitize_col_name(k): v for k, v in row.items() if v is not None and k != 'ASIN'}
                # Ensure we don't try to update with an empty dict
                if not update_dict:
                    continue

                set_clauses = ', '.join([f'"{col}" = :{col}' for col in update_dict.keys()])
                update_dict['ASIN'] = row['ASIN']

                cursor.execute(f"UPDATE deals SET {set_clauses} WHERE ASIN = :ASIN", update_dict)
                update_count += 1
            except Exception as e:
                logger.error(f"Recalculation: Failed to update database for ASIN {row.get('ASIN', 'UNKNOWN')}. Error: {e}", exc_info=True)

        conn.commit()
        conn.close()

        task_duration = time.time() - task_start_time
        logger.info(f"Recalculation finished in {task_duration:.2f}s. Attempted to update {update_count} rows.")
        set_recalc_status({"status": "Completed", "message": f"Full data refresh complete. Updated {update_count} of {total_deals} deals."})

    except Exception as e:
        logger.error(f"Recalculation task failed catastrophically: {e}", exc_info=True)
        set_recalc_status({"status": "Failed", "message": f"An unexpected error occurred: {e}"})
