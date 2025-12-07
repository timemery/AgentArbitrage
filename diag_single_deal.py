import os
import sys
import logging
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from keepa_deals.keepa_api import fetch_product_batch
from keepa_deals.processing import _process_single_deal
from keepa_deals.db_utils import save_deals_to_db, create_deals_table_if_not_exists
from keepa_deals.seller_info import get_seller_info_for_single_deal
from keepa_deals.token_manager import TokenManager

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

def run_single_deal_diag(asin: str):
    """
    Runs the full processing pipeline for a single ASIN and saves it to the database.
    This serves as an end-to-end "pre-flight check" for the data pipeline.
    """
    logging.info(f"--- Starting Single ASIN Diagnostic for: {asin} ---")

    # 1. Setup
    keepa_api_key = os.getenv("KEEPA_API_KEY")
    xai_api_key = os.getenv("XAI_TOKEN")
    if not keepa_api_key or not xai_api_key:
        logging.error("API keys (KEEPA_API_KEY, XAI_TOKEN) not found in .env file. Aborting.")
        return

    create_deals_table_if_not_exists()
    token_manager = TokenManager(keepa_api_key)
    token_manager.sync_tokens()
    logging.info(f"Initial token count: {token_manager.tokens}")

    # 2. Fetch Product Data with Live Offers
    logging.info(f"Fetching product data for ASIN {asin} with live offers...")
    estimated_cost = 12 # ~6 for offers, 1 for product, plus stats/history
    token_manager.request_permission_for_call(estimated_cost)
    product_data, _, _, tokens_left = fetch_product_batch(keepa_api_key, [asin], days=365, history=1, offers=20)
    token_manager.update_after_call(tokens_left)

    if not product_data or not product_data.get('products'):
        logging.error(f"Failed to fetch product data for ASIN {asin}. Aborting.")
        return
    product = product_data['products'][0]
    logging.info("Successfully fetched product data.")

    # 3. Fetch Data for ONLY the Lowest-Priced Seller
    logging.info("Identifying lowest-priced seller and fetching their data...")
    seller_cache = get_seller_info_for_single_deal(product, keepa_api_key, token_manager)
    if not seller_cache:
        logging.warning(f"Could not retrieve data for the lowest-priced seller of ASIN {asin}. Proceeding without it.")

    # 4. Process the Deal
    logging.info("Processing the deal with fetched data...")
    processed_deal = _process_single_deal(product, seller_cache, xai_api_key)

    if not processed_deal:
        logging.error(f"Failed to process deal for ASIN {asin}. _process_single_deal returned None.")
        return

    logging.info("Successfully processed deal data.")
    # logging.info(f"Processed data: {processed_deal}") # Uncomment for detailed output

    # 5. Save to Database
    logging.info("Saving processed deal to the database...")
    save_deals_to_db([processed_deal])

    # 6. Verify Database
    logging.info("Verifying database content...")
    import sqlite3
    conn = sqlite3.connect('deals.db')
    cursor = conn.cursor()
    # Check for a specific column known to be problematic, e.g., 'Used_365_days_avg'
    # Note: Column name must match the sanitized version.
    col_name = "Used_365_days_avg" # This matches the NEW sanitization of "Used - 365 days avg."

    try:
        cursor.execute(f"SELECT \"{col_name}\" FROM deals WHERE ASIN = ?", (asin,))
        row = cursor.fetchone()
        if row and row[0] is not None:
             logging.info(f"Verification Check: {col_name} = {row[0]}")
             print("--- VERIFICATION SUCCESS ---")
        else:
             logging.error(f"Verification Failed: {col_name} is None or row missing.")
             print("--- VERIFICATION FAILED ---")
    except Exception as e:
        logging.error(f"Verification Error: {e}")
        print("--- VERIFICATION FAILED ---")
    finally:
        conn.close()

    logging.info(f"--- Diagnostic Complete for ASIN: {asin} ---")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python diag_single_deal.py <ASIN>")
        sys.exit(1)

    target_asin = sys.argv[1]
    run_single_deal_diag(target_asin)
