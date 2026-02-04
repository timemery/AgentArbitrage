import unittest
import sqlite3
import os
import tempfile
import shutil
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

# Import the logic function (assuming path is set up correctly)
try:
    from keepa_deals.janitor import _clean_stale_deals_logic
except ImportError:
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    from keepa_deals.janitor import _clean_stale_deals_logic

class TestJanitor(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, "test_deals.db")
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE deals (id INTEGER PRIMARY KEY, ASIN TEXT, last_seen_utc TIMESTAMP)")
        conn.commit()
        conn.close()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_janitor_cleans_old_deals(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Insert deals
        now = datetime.now(timezone.utc)
        # Old deal: 25 hours old
        old_time = (now - timedelta(hours=25)).isoformat()
        # New deal: 1 hour old
        new_time = (now - timedelta(hours=1)).isoformat()

        cursor.execute("INSERT INTO deals (ASIN, last_seen_utc) VALUES ('OLD_DEAL', ?)", (old_time,))
        cursor.execute("INSERT INTO deals (ASIN, last_seen_utc) VALUES ('NEW_DEAL', ?)", (new_time,))
        conn.commit()
        conn.close()

        # Patch DB_PATH in janitor to point to our temp db
        with patch('keepa_deals.janitor.DB_PATH', self.db_path):
            # Run cleanup with 24h grace period
            deleted = _clean_stale_deals_logic(grace_period_hours=24)

        self.assertEqual(deleted, 1)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT ASIN FROM deals")
        rows = cursor.fetchall()
        conn.close()

        asins = [r[0] for r in rows]
        self.assertIn('NEW_DEAL', asins)
        self.assertNotIn('OLD_DEAL', asins)

if __name__ == '__main__':
    unittest.main()
