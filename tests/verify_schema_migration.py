import os
import sys
import sqlite3
import unittest
import logging
from unittest.mock import patch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set environment variable for DB BEFORE importing db_utils
TEST_DB_PATH = 'test_schema_migration.db'
os.environ['DATABASE_URL'] = TEST_DB_PATH

# Add repo root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals import db_utils

class TestSchemaMigration(unittest.TestCase):

    def setUp(self):
        # clean up any existing test db
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)

    def tearDown(self):
        # clean up
        if os.path.exists(TEST_DB_PATH):
            os.remove(TEST_DB_PATH)

    def test_migration_adds_missing_columns(self):
        # 1. Create a dummy DB with an "Old Schema" (just ASIN and Price)
        conn = sqlite3.connect(TEST_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE deals (id INTEGER PRIMARY KEY AUTOINCREMENT, ASIN TEXT UNIQUE, Price REAL)")
        conn.commit()
        conn.close()

        logger.info("Created test DB with old schema (ASIN, Price).")

        # Verify 'Detailed_Seasonality' is missing
        conn = sqlite3.connect(TEST_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(deals)")
        columns = [row[1] for row in cursor.fetchall()]
        conn.close()
        self.assertIn('ASIN', columns)
        self.assertNotIn('Detailed_Seasonality', columns)

        # 2. Run the migration function
        # We need to make sure db_utils uses our TEST_DB_PATH.
        # Since we set env var before import, db_utils.DB_PATH should be correct.
        logger.info(f"db_utils.DB_PATH is: {db_utils.DB_PATH}")
        self.assertEqual(db_utils.DB_PATH, TEST_DB_PATH)

        db_utils.create_deals_table_if_not_exists()

        # 3. Verify 'Detailed_Seasonality' was added
        conn = sqlite3.connect(TEST_DB_PATH)
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(deals)")
        new_columns = [row[1] for row in cursor.fetchall()]
        conn.close()

        logger.info(f"Columns after migration: {new_columns}")

        self.assertIn('Detailed_Seasonality', new_columns)
        self.assertIn('Seasonality_Type', new_columns) # Correct sanitized name
        self.assertIn('last_seen_utc', new_columns) # Should be added as mandatory system col

        # 4. Verify we can insert into it
        conn = sqlite3.connect(TEST_DB_PATH)
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO deals (ASIN, Detailed_Seasonality) VALUES (?, ?)", ('B00TEST', 'High Winter'))
            conn.commit()
            logger.info("Successfully inserted data into new column.")
        except Exception as e:
            self.fail(f"Insert failed: {e}")
        finally:
            conn.close()

if __name__ == '__main__':
    unittest.main()
