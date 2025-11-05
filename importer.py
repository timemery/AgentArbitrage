import json
import sqlite3
import os
import logging
from keepa_deals.db_utils import sanitize_col_name

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Constants ---
DB_PATH = 'deals.db'
TABLE_NAME = 'deals'
JSON_PATH = 'temp_deals.json'
HEADERS_PATH = os.path.join('keepa_deals', 'headers.json')

def import_deals_from_json():
    """
    Reads processed deals from a JSON file and upserts them into the SQLite database.
    This script is run manually after the backfill_deals Celery task completes.
    """
    logging.info("--- Starting Deal Importer Script ---")

    # 1. Check for the JSON file
    if not os.path.exists(JSON_PATH):
        logging.warning(f"'{JSON_PATH}' not found. No new deals to import. Exiting.")
        return

    # 2. Load data from JSON
    try:
        with open(JSON_PATH, 'r') as f:
            rows_to_upsert = json.load(f)
        if not rows_to_upsert:
            logging.info("JSON file is empty. No deals to import.")
            os.remove(JSON_PATH)
            logging.info(f"Removed empty '{JSON_PATH}'.")
            return
        logging.info(f"Loaded {len(rows_to_upsert)} deals from '{JSON_PATH}'.")
    except (json.JSONDecodeError, IOError) as e:
        logging.error(f"Error reading or parsing '{JSON_PATH}': {e}", exc_info=True)
        return

    # 3. Load headers
    try:
        with open(HEADERS_PATH) as f:
            headers = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error reading or parsing '{HEADERS_PATH}': {e}", exc_info=True)
        return

    # 4. Connect to DB and Upsert Data
    try:
        logging.info(f"Connecting to database at '{DB_PATH}'...")
        conn = sqlite3.connect(DB_PATH, timeout=30)
        cursor = conn.cursor()
        logging.info("Database connection successful.")

        sanitized_headers = [sanitize_col_name(h) for h in headers]
        sanitized_headers.extend(['last_seen_utc', 'source'])

        cols_str = ', '.join(f'"{h}"' for h in sanitized_headers)
        vals_str = ', '.join(['?'] * len(sanitized_headers))
        update_str = ', '.join(f'"{h}"=excluded."{h}"' for h in sanitized_headers if h != 'ASIN')
        upsert_sql = f"INSERT INTO {TABLE_NAME} ({cols_str}) VALUES ({vals_str}) ON CONFLICT(ASIN) DO UPDATE SET {update_str}"

        data_tuples = [tuple(row.get(h) for h in headers) + (row.get('last_seen_utc'), row.get('source')) for row in rows_to_upsert]

        logging.info(f"Executing UPSERT for {len(data_tuples)} deals...")
        cursor.executemany(upsert_sql, data_tuples)
        conn.commit()
        logging.info(f"Successfully upserted/updated {cursor.rowcount} rows into the '{TABLE_NAME}' table.")

    except sqlite3.Error as e:
        logging.error(f"A database error occurred: {e}", exc_info=True)
        # Do not delete the JSON file if the DB write fails
        return
    except Exception as e:
        logging.error(f"An unexpected error occurred during database operation: {e}", exc_info=True)
        # Do not delete the JSON file if the DB write fails
        return
    finally:
        if 'conn' in locals() and conn:
            conn.close()
            logging.info("Database connection closed.")

    # 5. Clean up the JSON file on success
    try:
        os.remove(JSON_PATH)
        logging.info(f"Successfully imported deals and removed '{JSON_PATH}'.")
    except OSError as e:
        logging.error(f"Error removing '{JSON_PATH}': {e}", exc_info=True)

    logging.info("--- Deal Importer Script Finished ---")

if __name__ == "__main__":
    import_deals_from_json()
