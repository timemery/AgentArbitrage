import sqlite3
import json
import os
import re
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'deals.db')
TABLE_NAME = 'deals'
HEADERS_PATH = os.path.join(os.path.dirname(__file__), 'headers.json')

def sanitize_col_name(name):
    """Sanitizes a string to be a valid SQLite column name."""
    name = name.replace(' ', '_').replace('.', '').replace('-', '_').replace('%', 'Percent')
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
    This function is idempotent and safe to run multiple times.
    """
    logger.info(f"Database check: Ensuring table '{TABLE_NAME}' at '{DB_PATH}' is correctly configured.")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{TABLE_NAME}'")
            table_exists = cursor.fetchone()

            if not table_exists:
                logger.info(f"Table '{TABLE_NAME}' not found. Creating it.")
                with open(HEADERS_PATH) as f:
                    headers = json.load(f)

                sanitized_headers = [sanitize_col_name(h) for h in headers]

                cols_sql = []
                for header in sanitized_headers:
                    if header == 'ASIN':
                        continue # Handled separately

                    # Simple type inference to match logic in other parts of the application
                    if header == 'Percent_Down':
                        col_type = 'TEXT'
                    elif 'Price' in header or 'Fee' in header or 'Margin' in header or 'Percent' in header or 'Profit' in header or 'Cost' in header:
                        col_type = 'REAL'
                    elif 'Rank' in header or 'Count' in header or 'Drops' in header:
                        col_type = 'INTEGER'
                    else:
                        col_type = 'TEXT'

                    cols_sql.append(f'"{header}" {col_type}')

                # Add the ASIN column with its constraints at the beginning
                cols_sql.insert(0, '"ASIN" TEXT NOT NULL UNIQUE')

                create_table_sql = f"CREATE TABLE {TABLE_NAME} (id INTEGER PRIMARY KEY AUTOINCREMENT, {', '.join(cols_sql)})"
                cursor.execute(create_table_sql)
                logger.info(f"Table '{TABLE_NAME}' created with inferred data types and a UNIQUE constraint on ASIN.")

            else:
                logger.info(f"Table '{TABLE_NAME}' exists. Verifying schema and indexes.")
                existing_columns = get_table_columns(cursor, TABLE_NAME)

                # Add missing columns
                if 'last_seen_utc' not in existing_columns:
                    logger.info("Adding 'last_seen_utc' column.")
                    cursor.execute(f'ALTER TABLE {TABLE_NAME} ADD COLUMN last_seen_utc TIMESTAMP')

                if 'source' not in existing_columns:
                    logger.info("Adding 'source' column.")
                    cursor.execute(f'ALTER TABLE {TABLE_NAME} ADD COLUMN source TEXT')

                # Verify UNIQUE index on ASIN
                if not has_unique_index_on_asin(cursor, TABLE_NAME):
                    logger.warning("No unique index found on ASIN column. Attempting to create one.")
                    try:
                        # This will fail if there are duplicate ASINs, which indicates a pre-existing data integrity issue.
                        cursor.execute(f"CREATE UNIQUE INDEX idx_asin_unique ON {TABLE_NAME}(ASIN)")
                        logger.info("Successfully created a unique index on ASIN.")
                    except sqlite3.IntegrityError as e:
                        logger.error(f"FATAL: Could not create UNIQUE index on ASIN because duplicate ASINs exist in the database. Please clean the data. Error: {e}")
                        # This is a critical failure, we should not proceed.
                        raise

            conn.commit()
            logger.info("Database schema check complete.")

    except sqlite3.Error as e:
        logger.error(f"A database error occurred during schema setup: {e}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred during schema setup: {e}", exc_info=True)
        raise