import json
import sqlite3
import os
from logging import getLogger
from worker import celery_app as celery
from .db_utils import sanitize_col_name

logger = getLogger(__name__)

# --- Constants ---
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'deals.db')
TABLE_NAME = 'deals'
JSON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'temp_deals.json')
HEADERS_PATH = os.path.join(os.path.dirname(__file__), 'headers.json')

@celery.task(name='keepa_deals.importer_task.import_deals')
def import_deals():
    """
    Reads processed deals from a JSON file and upserts them into the SQLite database.
    This task is intended to be run automatically after the backfill_deals task completes.
    """
    logger.info("--- Starting Deal Importer Task ---")

    # 1. Check for the JSON file
    if not os.path.exists(JSON_PATH):
        logger.warning(f"'{JSON_PATH}' not found. No new deals to import. Exiting.")
        return

    # 2. Load data from JSON
    try:
        with open(JSON_PATH, 'r') as f:
            rows_to_upsert = json.load(f)
        if not rows_to_upsert:
            logger.info("JSON file is empty. No deals to import.")
            os.remove(JSON_PATH)
            logger.info(f"Removed empty '{JSON_PATH}'.")
            return
        logger.info(f"Loaded {len(rows_to_upsert)} deals from '{JSON_PATH}'.")
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error reading or parsing '{JSON_PATH}': {e}", exc_info=True)
        # Re-raise the exception to mark the Celery task as failed
        raise

    # 3. Load headers
    try:
        with open(HEADERS_PATH) as f:
            headers = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Error reading or parsing '{HEADERS_PATH}': {e}", exc_info=True)
        raise

    # 4. Connect to DB and Upsert Data
    try:
        logger.info(f"Connecting to database at '{DB_PATH}'...")
        conn = sqlite3.connect(DB_PATH, timeout=30)
        cursor = conn.cursor()
        logger.info("Database connection successful.")

        sanitized_headers = [sanitize_col_name(h) for h in headers]
        sanitized_headers.extend(['last_seen_utc', 'source'])

        cols_str = ', '.join(f'"{h}"' for h in sanitized_headers)
        vals_str = ', '.join(['?'] * len(sanitized_headers))
        update_str = ', '.join(f'"{h}"=excluded."{h}"' for h in sanitized_headers if h != 'ASIN')
        upsert_sql = f"INSERT INTO {TABLE_NAME} ({cols_str}) VALUES ({vals_str}) ON CONFLICT(ASIN) DO UPDATE SET {update_str}"

        data_tuples = [tuple(row.get(h) for h in headers) + (row.get('last_seen_utc'), row.get('source')) for row in rows_to_upsert]

        logger.info(f"Executing UPSERT for {len(data_tuples)} deals...")
        cursor.executemany(upsert_sql, data_tuples)
        conn.commit()
        logger.info(f"Successfully upserted/updated {cursor.rowcount} rows into the '{TABLE_NAME}' table.")

    except sqlite3.Error as e:
        logger.error(f"A database error occurred: {e}", exc_info=True)
        # Do not delete the JSON file if the DB write fails
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred during database operation: {e}", exc_info=True)
        # Do not delete the JSON file if the DB write fails
        raise
    finally:
        if 'conn' in locals() and conn:
            conn.close()
            logger.info("Database connection closed.")

    # 5. Clean up the JSON file on success
    try:
        os.remove(JSON_PATH)
        logger.info(f"Successfully imported deals and removed '{JSON_PATH}'.")
    except OSError as e:
        logger.error(f"Error removing '{JSON_PATH}': {e}", exc_info=True)

    logger.info("--- Deal Importer Task Finished ---")
