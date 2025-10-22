# Restore Dashboard Functionality
import sqlite3
import json
import os
import re
import logging

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'deals.db')
TABLE_NAME = 'deals'
HEADERS_PATH = os.path.join(os.path.dirname(__file__), 'headers.json')

def sanitize_col_name(name):
    """Sanitizes a string to be a valid SQLite column name."""
    name = name.replace(' ', '_').replace('.', '').replace('-', '_').replace('%', 'Percent').replace('&', 'and')
    return re.sub(r'[^a-zA-Z0-9_]', '', name)

def recreate_deals_table():
    """
    Destroys and recreates the 'deals' table to ensure a fresh schema.
    This is the authoritative function for creating the table and should be
    used by the backfiller.
    """
    logger.info(f"Recreating '{TABLE_NAME}' table at '{DB_PATH}'. This will delete all existing data in the table.")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Drop the old table to ensure a completely fresh start
            cursor.execute(f"DROP TABLE IF EXISTS {TABLE_NAME}")
            logger.info(f"Dropped existing '{TABLE_NAME}' table.")

            with open(HEADERS_PATH) as f:
                headers = json.load(f)

            # --- Define explicit REAL types for financial columns ---
            # This is critical for correct sorting and display in the UI.
            explicit_real_types = [
                "Price", "Cost", "Fee", "Profit", "Margin", "List at"
            ]

            cols_sql = []
            for header in headers:
                sanitized_header = sanitize_col_name(header)

                # Determine data type with more robust rules
                col_type = 'TEXT' # Default
                if any(keyword in header for keyword in explicit_real_types):
                    col_type = 'REAL'
                elif "Rank" in header or "Count" in header or "Drops" in header:
                    col_type = 'INTEGER'

                if sanitized_header == 'ASIN':
                    cols_sql.append(f'"{sanitized_header}" TEXT NOT NULL UNIQUE')
                else:
                    cols_sql.append(f'"{sanitized_header}" {col_type}')

            create_table_sql = f"CREATE TABLE {TABLE_NAME} (id INTEGER PRIMARY KEY AUTOINCREMENT, {', '.join(cols_sql)})"
            cursor.execute(create_table_sql)
            logger.info(f"Successfully recreated '{TABLE_NAME}' table with up-to-date schema.")

            # Create the unique index on ASIN immediately after table creation.
            cursor.execute(f"CREATE UNIQUE INDEX idx_asin_unique ON {TABLE_NAME}(ASIN)")
            logger.info("Created unique index on ASIN.")

            conn.commit()
            logger.info("Database schema recreation complete.")

    except (sqlite3.Error, IOError, json.JSONDecodeError) as e:
        logger.error(f"A critical error occurred during table recreation: {e}", exc_info=True)
        raise

WATERMARK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'watermark.json')

def save_watermark(timestamp: str):
    """Saves the given ISO 8601 timestamp to the watermark file."""
    logger.info(f"Saving new watermark timestamp: {timestamp}")
    try:
        with open(WATERMARK_PATH, 'w') as f:
            json.dump({'lastUpdate': timestamp}, f)
        logger.info("Watermark saved successfully.")
    except IOError as e:
        logger.error(f"Error saving watermark to {WATERMARK_PATH}: {e}", exc_info=True)

def load_watermark() -> str | None:
    """
    Loads the watermark timestamp from the file.
    Returns the ISO 8601 timestamp string or None if the file doesn't exist.
    """
    if not os.path.exists(WATERMARK_PATH):
        logger.warning("Watermark file not found. Assuming this is the first run.")
        return None
    try:
        with open(WATERMARK_PATH, 'r') as f:
            data = json.load(f)
            timestamp = data.get('lastUpdate')
            logger.info(f"Loaded watermark: {timestamp}")
            return timestamp
    except (IOError, json.JSONDecodeError) as e:
        logger.error(f"Error loading watermark from {WATERMARK_PATH}: {e}", exc_info=True)
        return None
