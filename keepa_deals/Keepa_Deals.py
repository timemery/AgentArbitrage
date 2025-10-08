# keepa_deals/Keepa_Deals.py
# Refactored for integration with AgentArbitrage

import json
import csv
import logging
import sys
import time
import math
import os
from dotenv import load_dotenv
from celery_config import celery
from datetime import datetime
import sqlite3

# --- Local Imports ---
from .keepa_api import (
    fetch_deals_for_deals,
    fetch_product_batch,
    validate_asin,
    fetch_seller_data
)
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
from .db_utils import sanitize_col_name

# --- Helper Functions from tasks.py (to avoid circular imports) ---
def _parse_price(value_str):
    if isinstance(value_str, (int, float)): return float(value_str)
    if not isinstance(value_str, str) or value_str.strip() in ['-', 'N/A', '']: return 0.0
    try: return float(value_str.strip().replace('$', '').replace(',', ''))
    except ValueError: return 0.0

def _parse_percent(value_str):
    if isinstance(value_str, (int, float)): return float(value_str)
    if not isinstance(value_str, str) or value_str.strip() in ['-', 'N/A', '']: return 0.0
    try: return float(value_str.strip().replace('%', ''))
    except ValueError: return 0.0

def _process_single_deal_for_recalc(product_data, seller_cache, xai_api_key, business_settings, headers, logger):
    asin = product_data.get('asin')
    if not asin: return None
    row_data = {'ASIN': asin}
    for header, func in zip(headers, FUNCTION_LIST):
        if func and func.__name__ != 'get_all_seller_info':
            try:
                if func.__name__ in ['get_condition', 'last_update', 'last_price_change', 'deal_found']:
                    result = func(product_data, logger_param=logger)
                else:
                    result = func(product_data)
                row_data.update(result)
            except Exception as e:
                logger.warning(f"Processing function {func.__name__} failed for ASIN {asin}: {e}")

    row_data.update(get_all_seller_info(product_data, seller_data_cache=seller_cache))
    try:
        peak_price = _parse_price(row_data.get('Expected Peak Price', '0'))
        fba_fee = _parse_price(row_data.get('FBA Pick&Pack Fee', '0'))
        referral_percent = _parse_percent(row_data.get('Referral Fee %', '0'))
        best_price = _parse_price(row_data.get('Best Price', '0'))
        shipping_included_flag = str(row_data.get('Shipping Included', 'no')).lower() == 'yes'
        total_amz_fees = calculate_total_amz_fees(peak_price, fba_fee, referral_percent)
        all_in_cost = calculate_all_in_cost(best_price, total_amz_fees, business_settings, shipping_included_flag)
        profit_margin = calculate_profit_and_margin(peak_price, all_in_cost)
        min_listing = calculate_min_listing_price(all_in_cost, business_settings)
        row_data.update({'Total AMZ fees': total_amz_fees, 'All-in Cost': all_in_cost, 'Profit': profit_margin['profit'], 'Margin': profit_margin['margin'], 'Min. Listing Price': min_listing})
    except Exception as e:
        logger.warning(f"Business calculation failed for ASIN {asin}: {e}")

    try:
        yr_avg_info = get_1yr_avg_sale_price(product_data, logger=logger)
        trend_info = get_trend(product_data, logger=logger)
        row_data.update(yr_avg_info); row_data.update(trend_info)
        discount_info = get_percent_discount(row_data.get('1yr. Avg.'), row_data.get('Best Price'), logger=logger)
        row_data.update(discount_info)
    except Exception as e:
        logger.warning(f"Analytics calculation failed for ASIN {asin}: {e}")

    try:
        title = row_data.get('Title', ''); categories = row_data.get('Categories - Sub', ''); manufacturer = row_data.get('Manufacturer', '')
        detailed_season = classify_seasonality(title, categories, manufacturer, xai_api_key=xai_api_key)
        row_data['Detailed_Seasonality'] = "None" if detailed_season == "Year-round" else detailed_season
        row_data['Sells'] = get_sells_period(detailed_season)
    except Exception as e:
        logger.warning(f"Seasonality calculation failed for ASIN {asin}: {e}")

    return row_data

# --- Celery Tasks ---

def set_recalc_status(status_data):
    RECALC_STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'recalc_status.json')
    try:
        with open(RECALC_STATUS_FILE, 'w') as f:
            json.dump(status_data, f, indent=4)
    except IOError as e:
        logging.getLogger(__name__).error(f"Error writing recalc status file: {e}")

@celery.task
def recalculate_deals():
    logger = logging.getLogger(__name__)
    load_dotenv()
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'deals.db')
    TABLE_NAME = 'deals'
    HEADERS_PATH = os.path.join(os.path.dirname(__file__), 'headers.json')
    BATCH_SIZE = 50
    api_key = os.getenv("KEEPA_API_KEY")
    xai_api_key = os.getenv("XAI_TOKEN")

    if not api_key:
        set_recalc_status({"status": "Failed", "message": "KEEPA_API_KEY not configured."})
        return

    token_manager = TokenManager(api_key)
    business_settings = business_load_settings()
    with open(HEADERS_PATH) as f:
        headers = json.load(f)
    sanitized_headers = [sanitize_col_name(h) for h in headers]

    set_recalc_status({"status": "Running", "message": "Starting full data recalculation...", "total": 0, "processed": 0})

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
        total_deals = cursor.fetchone()[0]
        logger.info(f"Recalculation: Found {total_deals} total deals to refresh.")
        set_recalc_status({"status": "Running", "message": f"Found {total_deals} deals to refresh.", "total": total_deals, "processed": 0})

        if total_deals == 0:
            set_recalc_status({"status": "Completed", "message": "No deals to recalculate."})
            conn.close()
            return

        for offset in range(0, total_deals, BATCH_SIZE):
            logger.info(f"--- Processing batch: offset={offset}, size={BATCH_SIZE} ---")
            cursor.execute(f"SELECT ASIN FROM {TABLE_NAME} LIMIT ? OFFSET ?", (BATCH_SIZE, offset))
            asins_to_process = [row['ASIN'] for row in cursor.fetchall()]
            if not asins_to_process: break

            token_manager.request_permission_for_call(estimated_cost=len(asins_to_process) * 2)
            product_data, _, _, tokens_left = fetch_product_batch(api_key, asins_to_process, history=1, offers=20)
            if tokens_left is not None: token_manager.update_after_call(tokens_left)
            if not product_data or 'products' not in product_data: continue

            products_map = {p['asin']: p for p in product_data['products']}
            unique_seller_ids = {offer['sellerId'] for p in products_map.values() for offer in p.get('offers', []) if isinstance(offer, dict) and offer.get('sellerId')}

            seller_data_cache = {}
            if unique_seller_ids:
                seller_id_list = list(unique_seller_ids)
                token_manager.request_permission_for_call(estimated_cost=len(seller_id_list))
                seller_response, _, _, tokens_left = fetch_seller_data(api_key, seller_id_list)
                if tokens_left is not None: token_manager.update_after_call(tokens_left)
                if seller_response and 'sellers' in seller_response:
                    seller_data_cache.update(seller_response['sellers'])

            for asin, product in products_map.items():
                processed_row = _process_single_deal_for_recalc(product, seller_data_cache, xai_api_key, business_settings, headers, logger)
                if not processed_row: continue

                update_cols = [f'"{sanitize_col_name(h)}" = ?' for h in headers if h != 'ASIN' and h in processed_row]
                update_vals = [processed_row.get(h) for h in headers if h != 'ASIN' and h in processed_row]
                if not update_cols: continue
                update_vals.append(asin)

                update_sql = f"UPDATE {TABLE_NAME} SET {', '.join(update_cols)} WHERE ASIN = ?"
                try: cursor.execute(update_sql, tuple(update_vals))
                except Exception as e: logger.error(f"Failed to update DB for ASIN {asin}: {e}")

            conn.commit()
            processed_count = offset + len(asins_to_process)
            set_recalc_status({"status": "Running", "message": f"Processing...", "total": total_deals, "processed": processed_count})

        set_recalc_status({"status": "Completed", "message": "Full recalculation complete.", "total": total_deals, "processed": total_deals})
    except Exception as e:
        logger.error(f"Recalculation unexpected error: {e}", exc_info=True)
        set_recalc_status({"status": "Failed", "message": f"An unexpected error occurred: {e}"})
    finally:
        if 'conn' in locals(): conn.close()

# Note: run_keepa_script is removed as it's not part of the core recalculation logic and its functionality
# is now better handled by the dedicated `update_recent_deals` task in tasks.py.
# The `save_to_database` function is also removed as the new `recalculate_deals` handles its own DB updates.