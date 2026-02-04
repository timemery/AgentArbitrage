import unittest
import sys
import os
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

# Add directories to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Diagnostics')))

# Now import the script
import diagnose_dwindling_deals

class TestDiagnoseScript(unittest.TestCase):
    def setUp(self):
        self.test_db_path = "test_diagnose_deals.db"
        # Setup DB
        conn = sqlite3.connect(self.test_db_path)
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE deals (ASIN TEXT PRIMARY KEY, last_seen_utc TEXT)")
        cursor.execute("CREATE TABLE system_state (key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP)")

        # Insert test data
        now = datetime.now(timezone.utc)

        # 1. Fresh deal (< 1h)
        cursor.execute("INSERT INTO deals VALUES (?, ?)", ("ASIN1", now.isoformat()))

        # 2. Aging deal (40h)
        cursor.execute("INSERT INTO deals VALUES (?, ?)", ("ASIN2", (now - timedelta(hours=40)).isoformat()))

        # 3. Danger zone deal (71h)
        cursor.execute("INSERT INTO deals VALUES (?, ?)", ("ASIN3", (now - timedelta(hours=71)).isoformat()))

        # 4. Expired deal (75h)
        cursor.execute("INSERT INTO deals VALUES (?, ?)", ("ASIN4", (now - timedelta(hours=75)).isoformat()))

        # System state
        cursor.execute("INSERT INTO system_state VALUES (?, ?, ?)", ("backfill_page", "5", now.isoformat()))
        cursor.execute("INSERT INTO system_state VALUES (?, ?, ?)", ("watermark_iso", "2026-01-01T00:00:00+00:00", now.isoformat()))

        conn.commit()
        conn.close()

    def tearDown(self):
        if os.path.exists(self.test_db_path):
            os.remove(self.test_db_path)

    @patch('diagnose_dwindling_deals.get_redis_client')
    @patch('diagnose_dwindling_deals.DB_PATH', new_callable=lambda: "test_diagnose_deals.db") # This might not work if DB_PATH is imported directly
    def test_run_script_locked(self, mock_db_path, mock_get_redis):
        # Mock Redis
        mock_redis = MagicMock()
        mock_redis.ping.return_value = True

        # Backfill lock held (ttl > 0)
        # Upserter lock free (ttl -2)
        mock_redis.ttl.side_effect = lambda k: 100 if "backfill" in k else -2

        mock_get_redis.return_value = mock_redis

        # Patch DB_PATH in the module
        diagnose_dwindling_deals.DB_PATH = self.test_db_path

        print("\n--- TEST OUTPUT START ---")
        diagnose_dwindling_deals.main()
        print("--- TEST OUTPUT END ---\n")

        # Verify interactions if needed, but mainly we want to see it run without error
        mock_redis.ping.assert_called()

if __name__ == '__main__':
    unittest.main()
