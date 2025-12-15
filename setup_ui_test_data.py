
import sqlite3
import os
import logging
from keepa_deals.db_utils import DB_PATH, recreate_deals_table, create_user_restrictions_table_if_not_exists

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def setup_test_data():
    logger.info("Initializing database schema for UI verification...")

    # Initialize tables
    # create_deals_table_if_not_exists() # Assume it exists or we use existing deals.
    # But for clean test, we might want to insert specific rows.
    # To be safe, I will just insert rows into existing tables or ensure they exist.

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        # Ensure deals table has at least 3 rows to show different states
        # 1. Restricted (Error)
        # 2. Restricted (Success with link)
        # 3. Not Restricted

        # Check if deals exist, if not insert dummy deals
        cursor.execute("SELECT COUNT(*) FROM deals")
        count = cursor.fetchone()[0]

        if count < 3:
            logger.info("Inserting dummy deals...")
            cursor.execute("INSERT OR IGNORE INTO deals (ASIN, Title, Condition) VALUES ('TEST_ERR', 'Error Item', 'Used - Good')")
            cursor.execute("INSERT OR IGNORE INTO deals (ASIN, Title, Condition) VALUES ('TEST_LINK', 'Link Item', 'Used - Good')")
            cursor.execute("INSERT OR IGNORE INTO deals (ASIN, Title, Condition) VALUES ('TEST_OPEN', 'Open Item', 'Used - Good')")
            cursor.execute("INSERT OR IGNORE INTO deals (ASIN, Title, Condition) VALUES ('TEST_REST_NOLINK', 'Restricted No Link', 'Used - Good')")
            conn.commit()

        # Insert user restrictions
        # Assume user_id 'TEST_USER' is what the UI uses?
        # The UI filters/joins based on the user in session?
        # Wait, the UI uses `current_user.id`. I need to know what that is.
        # But for Playwright, I can't easily log in unless I go through the login flow.
        # The user provided login: `tester` / `OnceUponaBurgerTree-12monkeys`.
        # I will need to log in first in the playwright script.
        # And I need to know the user_id for 'tester'.
        # I can check the `users` table if it exists? Or `user_credentials`?

        # Let's blindly insert for 'tester' (if that's the ID) or try to find it.
        # Usually user_id is the email or username.

        user_id = 'tester'

        # Insert states into user_restrictions
        # Error State
        cursor.execute("""
            INSERT OR REPLACE INTO user_restrictions (user_id, asin, is_restricted, approval_url)
            VALUES (?, ?, ?, ?)
        """, (user_id, 'TEST_ERR', -1, 'ERROR'))

        # Success with Link
        cursor.execute("""
            INSERT OR REPLACE INTO user_restrictions (user_id, asin, is_restricted, approval_url)
            VALUES (?, ?, ?, ?)
        """, (user_id, 'TEST_LINK', 1, 'https://sellercentral.amazon.com/approval'))

        # Open
        cursor.execute("""
            INSERT OR REPLACE INTO user_restrictions (user_id, asin, is_restricted, approval_url)
            VALUES (?, ?, ?, ?)
        """, (user_id, 'TEST_OPEN', 0, None))

        # Restricted No Link
        cursor.execute("""
            INSERT OR REPLACE INTO user_restrictions (user_id, asin, is_restricted, approval_url)
            VALUES (?, ?, ?, ?)
        """, (user_id, 'TEST_REST_NOLINK', 1, None))

        conn.commit()
        logger.info("Test data inserted.")

if __name__ == "__main__":
    setup_test_data()
