import logging
import os
import sqlite3
from dotenv import load_dotenv

from celery_config import celery
from .keepa_api import fetch_deals_for_deals, validate_asin
from .db_utils import create_deals_table_if_not_exists

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# --- Constants ---
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'deals.db')
TABLE_NAME = 'deals'

@celery.task(name='keepa_deals.simple_task.get_recent_deals_asins')
def get_recent_deals_asins():
    """
    Fetches recent deals from Keepa, logs the ASINs, and inserts them into the database.
    """
    logger.info("--- Task: get_recent_deals_asins started ---")
    
    # Ensure the deals table exists before doing anything else.
    create_deals_table_if_not_exists()
    
    api_key = os.getenv("KEEPA_API_KEY")
    if not api_key:
        logger.error("KEEPA_API_KEY not set. Aborting.")
        return

    # Using date_range_days=1 to get deals from the last 24 hours.
    deal_response, tokens_left = fetch_deals_for_deals(1, api_key, use_deal_settings=True)

    if not deal_response or 'deals' not in deal_response:
        logger.error("Failed to fetch deals or no deals in response.")
        return

    recent_deals = [d for d in deal_response.get('deals', {}).get('dr', []) if d.get('asin') and validate_asin(d.get('asin'))]

    if not recent_deals:
        logger.info("No new valid deals found.")
        return

    asins = [d['asin'] for d in recent_deals]
    logger.info(f"Found {len(asins)} ASINs: {', '.join(asins)}")

    # --- Database Insertion ---
    logger.info(f"Attempting to insert {len(asins)} ASINs into the database...")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Prepare data for executemany, which expects a list of tuples
            data_to_insert = [(asin,) for asin in asins]
            
            # Use INSERT OR IGNORE to avoid errors on duplicate ASINs.
            # This is a simple upsert for just the ASIN column.
            insert_sql = f"INSERT OR IGNORE INTO {TABLE_NAME} (ASIN) VALUES (?)"
            
            cursor.executemany(insert_sql, data_to_insert)
            conn.commit()
            
            # cursor.rowcount will show how many rows were actually inserted (not ignored).
            logger.info(f"Successfully inserted {cursor.rowcount} new ASINs into the database.")

    except sqlite3.Error as e:
        logger.error(f"Database error during ASIN insertion: {e}", exc_info=True)
    except Exception as e:
        logger.error(f"An unexpected error occurred during database insertion: {e}", exc_info=True)
        
    logger.info("--- Task: get_recent_deals_asins finished ---")
