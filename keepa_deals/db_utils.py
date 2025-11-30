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
    # Special case for "1yr. Avg." which can cause an "unrecognized token" error
    # during table creation. We give it a unique, safe name.
    if name == "1yr. Avg.":
        return "yr_1_Avg"

    # For all other columns, we use the original logic to ensure generated names
    # match the schema of the user's existing database (e.g., "Avg. Price 90" -> "Avg_Price_90").
    name = name.replace(' ', '_').replace('.', '').replace('-', '_').replace('%', 'Percent').replace('&', 'and')
    return re.sub(r'[^a-zA-Z0-9_]', '', name)

def get_table_columns(cursor, table_name):
    """Fetches the column names for a given table."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]

def has_unique_index_on_asin(cursor, table_name):
    """Checks if a unique index exists on the ASIN column."""
    try:
        cursor.execute(f"PRAGMA index_list('{table_name}')")
        indexes = [row for row in cursor.fetchall() if row[2] == 1] # unique indexes
        for index in indexes:
            index_name = index[1]
            cursor.execute(f"PRAGMA index_info('{index_name}')")
            columns = cursor.fetchall()
            if len(columns) == 1 and columns[0][2] == 'ASIN':
                logger.info(f"Found existing unique index '{index_name}' on ASIN.")
                return True
        return False
    except sqlite3.Error as e:
        logger.error(f"Error checking for unique index: {e}")
        return False

def create_deals_table_if_not_exists():
    """
    Ensures the 'deals' table exists and has the correct schema.
    This is a non-destructive function safe for frequent checks.
    """
    logger.info(f"Database check: Ensuring table '{TABLE_NAME}' at '{DB_PATH}' is correctly configured.")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{TABLE_NAME}'")
            if not cursor.fetchone():
                # If the table doesn't exist at all, we can safely call the full recreation.
                logger.warning(f"Table '{TABLE_NAME}' not found. Calling recreate_deals_table() to build it.")
                # The connection is implicitly handled by the 'with' statement.
                # We must not close it manually here. The recreation function will open its own connection.
                recreate_deals_table()
                return  # The table is now created, so we're done.

            # If the table exists, just perform safe checks.
            logger.info(f"Table '{TABLE_NAME}' exists. Verifying schema and indexes.")
            existing_columns = get_table_columns(cursor, TABLE_NAME)

            # Add missing columns (idempotent)
            if 'last_seen_utc' not in existing_columns:
                logger.info("Adding 'last_seen_utc' column.")
                cursor.execute(f'ALTER TABLE {TABLE_NAME} ADD COLUMN last_seen_utc TIMESTAMP')

            if 'source' not in existing_columns:
                logger.info("Adding 'source' column.")
                cursor.execute(f'ALTER TABLE {TABLE_NAME} ADD COLUMN source TEXT')

            if not has_unique_index_on_asin(cursor, TABLE_NAME):
                logger.warning("No unique index found on ASIN column. This should have been created with the table.")

            conn.commit()
            logger.info("Database schema check complete.")

    except (sqlite3.Error, Exception) as e:
        logger.error(f"An unexpected error occurred during schema check: {e}", exc_info=True)
        raise

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

def create_user_restrictions_table_if_not_exists():
    """
    Ensures the 'user_restrictions' table exists with the correct schema.
    This is a non-destructive function safe for frequent checks.
    """
    table_name = 'user_restrictions'
    logger.info(f"Database check: Ensuring table '{table_name}' at '{DB_PATH}' is correctly configured.")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
            if cursor.fetchone():
                logger.info(f"Table '{table_name}' already exists.")
                # You could add schema verification/migration logic here if needed
                return

            logger.info(f"Table '{table_name}' not found. Creating it now.")
            create_table_sql = f"""
            CREATE TABLE {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                asin TEXT NOT NULL,
                is_restricted INTEGER,
                approval_url TEXT,
                last_checked_timestamp TIMESTAMP,
                UNIQUE(user_id, asin)
            )
            """
            cursor.execute(create_table_sql)
            logger.info(f"Successfully created table '{table_name}'.")
            conn.commit()

    except (sqlite3.Error, Exception) as e:
        logger.error(f"An unexpected error occurred during '{table_name}' table creation: {e}", exc_info=True)
        raise
