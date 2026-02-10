# Restore Dashboard Functionality
import sqlite3
import json
import os
import re
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Use DATABASE_URL if set, otherwise default to deals.db in parent directory
DB_PATH = os.getenv('DATABASE_URL', os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'deals.db'))
TABLE_NAME = 'deals'
HEADERS_PATH = os.path.join(os.path.dirname(__file__), 'headers.json')
WATERMARK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'watermark.json')

def sanitize_col_name(name):
    """Sanitizes a string to be a valid SQLite column name."""
    name = name.replace('%', 'Percent').replace('&', 'and').replace('.', '_')
    name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    name = re.sub(r'__+', '_', name)
    name = name.strip('_')
    return name

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

def create_system_state_table_if_not_exists():
    """
    Ensures the 'system_state' table exists.
    Schema: key (TEXT PRIMARY KEY), value (TEXT), updated_at (TIMESTAMP)
    """
    logger.info(f"Database check: Ensuring table 'system_state' at '{DB_PATH}' exists.")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS system_state (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP
                )
            """)
            conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error creating system_state table: {e}", exc_info=True)
        raise

def get_system_state(key: str, default=None):
    """Retrieves a value from the system_state table."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM system_state WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                return row[0]
            return default
    except sqlite3.Error as e:
        logger.error(f"Error retrieving system state for key '{key}': {e}", exc_info=True)
        return default

def set_system_state(key: str, value: str):
    """Sets a value in the system_state table."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            updated_at = datetime.now(timezone.utc).isoformat()
            cursor.execute("""
                INSERT OR REPLACE INTO system_state (key, value, updated_at)
                VALUES (?, ?, ?)
            """, (key, str(value), updated_at))
            conn.commit()
            logger.info(f"System state updated: {key}={value}")
    except sqlite3.Error as e:
        logger.error(f"Error setting system state for key '{key}': {e}", exc_info=True)

def create_deals_table_if_not_exists():
    """
    Ensures the 'deals' table exists and has the correct schema.
    Also ensures 'system_state' table exists.
    """
    # Ensure system state table exists
    create_system_state_table_if_not_exists()

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

            # --- Dynamic Schema Migration (2026-02-12) ---
            # Automatically add any columns defined in headers.json but missing from the DB.
            with open(HEADERS_PATH) as f:
                headers = json.load(f)

            explicit_real_types = [
                "Price", "Cost", "Fee", "Profit", "Margin", "List at"
            ]

            for header in headers:
                sanitized_header = sanitize_col_name(header)
                if sanitized_header not in existing_columns:
                    # Determine type (Logic mirrored from recreate_deals_table)
                    col_type = 'TEXT' # Default
                    if any(keyword in header for keyword in explicit_real_types):
                        col_type = 'REAL'
                    elif "Rank" in header or "Count" in header or "Drops" in header:
                        col_type = 'INTEGER'

                    logger.info(f"Schema Migration: Adding missing column '{sanitized_header}' ({col_type}).")
                    try:
                        cursor.execute(f'ALTER TABLE {TABLE_NAME} ADD COLUMN "{sanitized_header}" {col_type}')
                        existing_columns.append(sanitized_header) # Update local list to prevent re-adding
                    except sqlite3.OperationalError as e:
                        logger.error(f"Failed to add column '{sanitized_header}': {e}")

            # Add system columns (idempotent)
            if 'last_seen_utc' not in existing_columns:
                logger.info("Adding 'last_seen_utc' column.")
                cursor.execute(f'ALTER TABLE {TABLE_NAME} ADD COLUMN last_seen_utc TIMESTAMP')

            if 'source' not in existing_columns:
                logger.info("Adding 'source' column.")
                cursor.execute(f'ALTER TABLE {TABLE_NAME} ADD COLUMN source TEXT')

            # Add new dashboard columns if missing (Added 2025-06-25) - Now handled by dynamic loop mostly, but kept for safety if not in headers.json
            if 'Drops' not in existing_columns:
                logger.info("Adding 'Drops' column.")
                cursor.execute(f'ALTER TABLE {TABLE_NAME} ADD COLUMN Drops INTEGER')

            if 'Offers' not in existing_columns:
                logger.info("Adding 'Offers' column.")
                cursor.execute(f'ALTER TABLE {TABLE_NAME} ADD COLUMN Offers TEXT')

            if 'AMZ' not in existing_columns:
                logger.info("Adding 'AMZ' column.")
                cursor.execute(f'ALTER TABLE {TABLE_NAME} ADD COLUMN AMZ TEXT')

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

def save_watermark(timestamp: str):
    """Saves the given ISO 8601 timestamp to the system_state table."""
    logger.info(f"Saving new watermark timestamp: {timestamp}")
    set_system_state('watermark_iso', timestamp)

def load_watermark() -> str | None:
    """
    Loads the watermark timestamp from the system_state table.
    Migrates from 'watermark.json' if the DB entry is missing.
    """
    # Try loading from DB first
    val = get_system_state('watermark_iso')
    if val:
        return val

    # Fallback: Check for legacy file
    if os.path.exists(WATERMARK_PATH):
        logger.info("Watermark missing in DB. Checking legacy file...")
        try:
            with open(WATERMARK_PATH, 'r') as f:
                data = json.load(f)
                timestamp = data.get('lastUpdate')
                if timestamp:
                    logger.info(f"Found legacy watermark: {timestamp}. Migrating to DB.")
                    save_watermark(timestamp)
                    return timestamp
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Error loading watermark from {WATERMARK_PATH}: {e}", exc_info=True)

    logger.warning("Watermark not found in DB or file. Assuming this is the first run.")
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

def recreate_user_restrictions_table():
    """
    Destroys and recreates the 'user_restrictions' table.
    Used during a full system reset.
    """
    table_name = 'user_restrictions'
    logger.info(f"Recreating '{table_name}' table at '{DB_PATH}'. This will delete all existing restriction data.")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
            conn.commit()
            logger.info(f"Dropped existing '{table_name}' table.")

        # Now recreate it
        create_user_restrictions_table_if_not_exists()
        logger.info(f"Successfully recreated '{table_name}' table.")

    except sqlite3.Error as e:
        logger.error(f"Error recreating '{table_name}': {e}", exc_info=True)
        raise

def create_user_credentials_table_if_not_exists():
    """
    Ensures the 'user_credentials' table exists to persist SP-API tokens.
    Required for background tasks that cannot access Flask session.
    """
    table_name = 'user_credentials'
    logger.info(f"Database check: Ensuring table '{table_name}' at '{DB_PATH}' exists.")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}'")
            if not cursor.fetchone():
                logger.info(f"Table '{table_name}' not found. Creating it now.")
                cursor.execute(f"""
                    CREATE TABLE {table_name} (
                        user_id TEXT PRIMARY KEY,
                        refresh_token TEXT NOT NULL,
                        updated_at TIMESTAMP
                    )
                """)
                conn.commit()
                logger.info(f"Successfully created table '{table_name}'.")
    except sqlite3.Error as e:
        logger.error(f"Error creating '{table_name}' table: {e}", exc_info=True)
        raise

def save_user_credentials(user_id: str, refresh_token: str):
    """Saves or updates user SP-API credentials."""
    # Let exceptions propagate to the caller for proper UI feedback
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        updated_at = datetime.now(timezone.utc).isoformat()
        cursor.execute("""
            INSERT OR REPLACE INTO user_credentials (user_id, refresh_token, updated_at)
            VALUES (?, ?, ?)
        """, (user_id, refresh_token, updated_at))
        conn.commit()
        logger.info(f"Saved credentials for user_id: {user_id}")

def get_all_user_credentials():
    """Retrieves all user credentials for background processing."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, refresh_token FROM user_credentials")
            return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logger.error(f"Error retrieving user credentials: {e}", exc_info=True)
        return []

def get_deal_count():
    """Returns the total number of rows in the deals table."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
            row = cursor.fetchone()
            if row:
                return row[0]
            return 0
    except sqlite3.Error as e:
        logger.error(f"Error counting deals: {e}", exc_info=True)
        return 0

def save_deals_to_db(deals_data):
    """Saves a list of deal dictionaries to the deals.db SQLite database."""
    if not deals_data:
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get the columns from the deals table to ensure we only insert what's expected
    cursor.execute("PRAGMA table_info(deals)")
    table_columns = {row[1] for row in cursor.fetchall()}

    for deal in deals_data:
        # Create a new dictionary with sanitized keys
        sanitized_deal = {}
        for k, v in deal.items():
            sanitized_key = sanitize_col_name(k)
            if sanitized_key in table_columns:
                 sanitized_deal[sanitized_key] = v

        if not sanitized_deal:
             logger.warning(f"Skipping deal for ASIN {deal.get('ASIN')} because no valid columns were found.")
             continue


        columns = ', '.join([f'"{k}"' for k in sanitized_deal.keys()])
        placeholders = ', '.join(['?'] * len(sanitized_deal))
        values = list(sanitized_deal.values())

        # Use INSERT OR REPLACE to handle both new deals and updates gracefully
        sql = f"INSERT OR REPLACE INTO deals ({columns}) VALUES ({placeholders})"

        cursor.execute(sql, values)


    conn.commit()
    conn.close()
    logging.info(f"Successfully saved/updated {len(deals_data)} deals to the database.")

def clear_deals_table():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM deals")
    conn.commit()
    conn.close()
    logging.info("Deals table cleared.")
# Refreshed
# Refreshed
