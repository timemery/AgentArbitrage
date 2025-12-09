# keepa_deals/recalculator.py
import json
import logging
import time
import os
import re
from dotenv import load_dotenv
from celery_app import celery_app
import sqlite3
from .business_calculations import (
    load_settings as business_load_settings,
    calculate_all_in_cost,
    calculate_profit_and_margin,
    calculate_min_listing_price,
)
from .seasonality_classifier import classify_seasonality, get_sells_period
from .processing import clean_numeric_values
from .db_utils import sanitize_col_name

logger = logging.getLogger(__name__)

def set_recalc_status(status_data):
    """Helper to write to the recalculation status file."""
    RECALC_STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'recalc_status.json')
    try:
        with open(RECALC_STATUS_FILE, 'w') as f:
            json.dump(status_data, f, indent=4)
    except IOError as e:
        logger.error(f"Error writing recalc status file: {e}")

@celery_app.task(name='keepa_deals.recalculator.recalculate_deals')
def recalculate_deals():
    """
    Celery task to perform a database-only data refresh for all deals.
    This version is API-free and only recalculates business logic and seasonality.
    """
    load_dotenv()
    XAI_API_KEY = os.getenv("XAI_TOKEN")
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'deals.db')

    set_recalc_status({"status": "Running", "message": "Starting database-only recalculation..."})
    task_start_time = time.time()

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        required_columns_map = {
            "ASIN": "ASIN",
            "List at": "List_at",
            "Best Price": "Best_Price",
            "FBA Pick&Pack Fee": "FBA_PickPack_Fee",
            "Referral Fee %": "Referral_Fee_Percent",
            "Shipping Included": "Shipping_Included",
            "Title": "Title",
            "Categories - Sub": "Categories_Sub",
            "Manufacturer": "Manufacturer"
        }

        cursor.execute("PRAGMA table_info(deals)")
        existing_columns = [row['name'] for row in cursor.fetchall()]

        select_clauses = []
        for original_name, alias in required_columns_map.items():
            sanitized_original = sanitize_col_name(original_name)
            if sanitized_original in existing_columns:
                select_clauses.append(f'"{sanitized_original}" AS {alias}')

        if not any('ASIN' in s for s in select_clauses):
            raise ValueError("ASIN column not found in deals table, cannot proceed.")

        query = f"SELECT {', '.join(select_clauses)} FROM deals"
        cursor.execute(query)
        deals_to_refresh = [dict(row) for row in cursor.fetchall()]
        conn.close()

        if not deals_to_refresh:
            set_recalc_status({"status": "Completed", "message": "No deals to recalculate."})
            return

        total_deals = len(deals_to_refresh)
        set_recalc_status({
            "status": "Running", "message": f"Found {total_deals} deals. Applying latest business logic...",
            "total_deals": total_deals, "processed_deals": 0
        })

        business_settings = business_load_settings()
        all_rows_to_update = []
        for i, deal_data in enumerate(deals_to_refresh):
            row_updates = {'ASIN': deal_data['ASIN']}

            try:
                list_at_price = float(str(deal_data.get('List_at', '0')).replace('$', '').replace(',', ''))
                now_price = float(str(deal_data.get('Now', '0')).replace('$', '').replace(',', ''))

                if list_at_price > 0 and now_price > 0:
                    fba_fee = float(str(deal_data.get('FBA_PickPack_Fee', '0')).replace(',', ''))
                    ref_fee = float(str(deal_data.get('Referral_Fee_Percent', '0')).replace('%', ''))

                    shipping_included = str(deal_data.get('Shipping_Included', 'no')).lower() == 'yes'
                    all_cost = calculate_all_in_cost(now_price, list_at_price, fba_fee, ref_fee, business_settings, shipping_included)
                    profit_margin = calculate_profit_and_margin(list_at_price, all_cost)

                    row_updates.update({
                        'All_in_Cost': all_cost,
                        'Profit': profit_margin['profit'], 'Margin': profit_margin['margin'],
                        'Min_Listing_Price': calculate_min_listing_price(all_cost, business_settings)
                    })
            except (ValueError, TypeError, KeyError) as e:
                 logger.error(f"Recalc (Biz Calcs): Error for ASIN {deal_data['ASIN']}. Error: {e}", exc_info=True)

            try:
                detailed_season = classify_seasonality(deal_data.get('Title', ''), deal_data.get('Categories_Sub', ''), deal_data.get('Manufacturer', ''), xai_api_key=XAI_API_KEY)
                sells_period = get_sells_period(detailed_season)
                row_updates['Detailed_Seasonality'] = detailed_season # Keep "Year-round" instead of "None"
                row_updates['Sells'] = sells_period
            except Exception as e:
                logger.error(f"Recalc (Seasonality): Error for ASIN {deal_data['ASIN']}. Error: {e}", exc_info=True)

            all_rows_to_update.append(clean_numeric_values(row_updates))

            if (i + 1) % 50 == 0:
                 set_recalc_status({
                    "status": "Running", "message": f"Processing logic for {i+1}/{total_deals} deals.",
                    "total_deals": total_deals, "processed_deals": i + 1
                })

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        update_count = 0
        for row in all_rows_to_update:
            try:
                update_dict = {k: v for k, v in row.items() if v is not None and k != 'ASIN'}
                if not update_dict: continue

                sanitized_update_dict = {sanitize_col_name(k): v for k, v in update_dict.items()}
                set_clauses = ', '.join([f'"{col}" = :{col}' for col in sanitized_update_dict.keys()])

                # The primary key for the WHERE clause also needs to be in the dictionary
                sanitized_update_dict['ASIN_WHERE'] = row['ASIN']
                logger.debug(f"Updating ASIN {row['ASIN']} with: {sanitized_update_dict}")

                cursor.execute(f'UPDATE deals SET {set_clauses} WHERE ASIN = :ASIN_WHERE', sanitized_update_dict)
                update_count += 1
            except sqlite3.Error as e:
                logger.error(f"Recalculation: Failed to update DB for ASIN {row.get('ASIN', 'UNKNOWN')}. Error: {e}", exc_info=True)

        conn.commit()
        conn.close()

        task_duration = time.time() - task_start_time
        logger.info(f"Recalculation finished in {task_duration:.2f}s. Updated {update_count} rows.")
        set_recalc_status({"status": "Completed", "message": f"Database-only recalculation complete. Updated {update_count} of {total_deals} deals."})

    except Exception as e:
        logger.error(f"Recalculation task failed catastrophically: {e}", exc_info=True)
        set_recalc_status({"status": "Failed", "message": f"An unexpected error occurred: {e}"})
