import json
import logging
import math
import os
import sqlite3
from datetime import datetime, timezone
from dotenv import load_dotenv

from celery_config import celery
from .keepa_api import fetch_product_batch, fetch_seller_data
from .token_manager import TokenManager
from .business_calculations import load_settings as business_load_settings
from .processing import _process_single_deal, clean_and_prepare_row_for_db
from .db_utils import sanitize_col_name
from .seller_info import seller_data_cache

logger = logging.getLogger(__name__)

def set_recalc_status(status_data):
    """Helper to write to the recalculation status file."""
    RECALC_STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'recalc_status.json')
    try:
        with open(RECALC_STATUS_FILE, 'w') as f:
            json.dump(status_data, f, indent=4)
    except IOError as e:
        print(f"Error writing recalc status file: {e}")

@celery.task
def recalculate_deals():
    """
    Celery task to perform a full data refresh for all deals in the database.
    It fetches fresh data from Keepa and re-runs the entire enrichment pipeline
    in a token-aware and rate-limited manner.
    """
    load_dotenv()
    DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'deals.db')
    HEADERS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'keepa_deals', 'headers.json')
    MAX_ASINS_PER_BATCH = 50
    ESTIMATED_COST_PER_ASIN = 2

    set_recalc_status({"status": "Running", "message": "Starting full data refresh..."})
    conn = None
    processed_count = 0
    try:
        # --- Setup ---
        api_key = os.getenv("KEEPA_API_KEY")
        xai_api_key = os.getenv("XAI_API_KEY")
        if not api_key:
            raise ValueError("KEEPA_API_KEY not set.")

        token_manager = TokenManager(api_key)
        business_settings = business_load_settings()
        with open(HEADERS_PATH) as f:
            headers = json.load(f)
        sanitized_headers = [sanitize_col_name(h) for h in headers]

        # --- Database Connection and ASIN Fetch ---
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT ASIN FROM deals")
        all_asins = [row[0] for row in cursor.fetchall() if row[0]]

        if not all_asins:
            logger.info("Recalculation: No deals found. Nothing to do.")
            set_recalc_status({"status": "Completed", "message": "No deals to recalculate."})
            return

        total_asins = len(all_asins)
        logger.info(f"Recalculation: Found {total_asins} total ASINs to refresh.")

        cursor.execute(f"PRAGMA table_info(deals)")
        schema_info = {row[1]: row[2] for row in cursor.fetchall()}

        all_products_to_process = {}

        # --- Step 1: Fetch all product data in batches ---
        logger.info("--- Step 1: Fetching all product data ---")
        for i in range(0, total_asins, MAX_ASINS_PER_BATCH):
            batch_asins = all_asins[i:i + MAX_ASINS_PER_BATCH]
            estimated_cost = len(batch_asins) * ESTIMATED_COST_PER_ASIN
            token_manager.request_permission_for_call(estimated_cost)

            product_response, _, _, tokens_left = fetch_product_batch(api_key, batch_asins, history=1, offers=20)
            if tokens_left is not None: token_manager.update_after_call(tokens_left)

            if product_response and 'products' in product_response:
                for p in product_response['products']:
                    all_products_to_process[p['asin']] = p
        logger.info(f"--- Step 1 Complete: Fetched data for {len(all_products_to_process)} products ---")

        # --- Step 2: Pre-fetch all seller data ---
        logger.info("--- Step 2: Pre-fetching all required seller data ---")
        unique_seller_ids = {offer['sellerId'] for p in all_products_to_process.values() for offer in p.get('offers', []) if offer.get('sellerId')}
        seller_ids_to_fetch = list(unique_seller_ids - set(seller_data_cache.keys()))

        if seller_ids_to_fetch:
            logger.info(f"Found {len(seller_ids_to_fetch)} new sellers to fetch.")
            estimated_cost = len(seller_ids_to_fetch)
            token_manager.request_permission_for_call(estimated_cost)

            seller_data_response, _, _, tokens_left = fetch_seller_data(api_key, seller_ids_to_fetch)
            if tokens_left is not None: token_manager.update_after_call(tokens_left)

            if seller_data_response and seller_data_response.get('sellers'):
                for seller_id, data in seller_data_response['sellers'].items():
                    seller_data_cache[seller_id] = data
        else:
            logger.info("All required seller data is already in cache.")
        logger.info("--- Step 2 Complete: Seller data pre-fetched and cached. ---")

        # --- Step 3: Process and update deals in database ---
        logger.info("--- Step 3: Processing and updating deals ---")
        for asin, product_data in all_products_to_process.items():
            processed_row = _process_single_deal(
                product_data, api_key, xai_api_key, business_settings, headers
            )
            if not processed_row:
                logger.warning(f"Failed to re-process ASIN {asin}. Skipping update.")
                continue

            processed_row['last_seen_utc'] = datetime.now(timezone.utc).isoformat()
            processed_row['source'] = 'recalc'

            cleaned_tuple = clean_and_prepare_row_for_db(processed_row, headers, schema_info)

            update_dict = dict(zip(sanitized_headers, cleaned_tuple))
            update_asin = update_dict.pop('ASIN', None)

            if not update_asin: continue

            set_clause = ", ".join([f'"{key}" = ?' for key in update_dict.keys()])
            params = list(update_dict.values())
            params.append(update_asin)

            update_sql = f"UPDATE deals SET {set_clause} WHERE ASIN = ?"

            cursor.execute(update_sql, tuple(params))
            processed_count += 1

        conn.commit()
        logger.info(f"--- Step 3 Complete: Database updates committed. {processed_count} deals refreshed. ---")

    except Exception as e:
        logger.error(f"Recalculation failed with an unexpected error: {e}", exc_info=True)
        set_recalc_status({"status": "Failed", "message": f"An unexpected error occurred: {e}"})
        if conn: conn.rollback()
    finally:
        if conn: conn.close()
        set_recalc_status({"status": "Completed", "message": f"Full data refresh complete. {processed_count} deals updated."})