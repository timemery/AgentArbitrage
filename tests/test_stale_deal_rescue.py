
import os
import sys
import sqlite3
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set DB path before importing module
TEST_DB = 'test_diminishing.db'
os.environ['DATABASE_URL'] = TEST_DB
os.environ['KEEPA_API_KEY'] = 'dummy'

# Mock Redis before importing smart_ingestor
sys.modules['redis'] = MagicMock()

# Import after setting env and mocks
from keepa_deals import smart_ingestor
from keepa_deals import db_utils
from keepa_deals import janitor

class TestDiminishingDeals(unittest.TestCase):
    def setUp(self):
        # Setup clean DB
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)
        db_utils.create_deals_table_if_not_exists()

        # Insert a "Stale" deal (70 hours old)
        # We use a known ASIN so we can query it
        self.stale_asin = 'B00STALE00'
        # 70 hours ago
        self.stale_time = (datetime.now(timezone.utc) - timedelta(hours=70)).isoformat()

        with sqlite3.connect(TEST_DB) as conn:
            cursor = conn.cursor()
            # Insert minimal valid deal
            # Column names must match sanitized versions from headers.json + utils
            # Price Now -> Price_Now
            # List at -> List_at
            # 1yr. Avg. -> 1yr_Avg
            cursor.execute(f"""
                INSERT INTO deals (ASIN, Title, "Price_Now", "List_at", "1yr_Avg", Profit, last_seen_utc)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (self.stale_asin, "Stale Book", 10.0, 20.0, 15.0, 5.0, self.stale_time))
            conn.commit()

    def tearDown(self):
        if os.path.exists(TEST_DB):
            os.remove(TEST_DB)

    @patch('keepa_deals.smart_ingestor.fetch_deals_for_deals')
    @patch('keepa_deals.smart_ingestor.TokenManager')
    @patch('keepa_deals.smart_ingestor.requeue_stuck_restrictions') # Mock this to avoid error
    def test_smart_ingestor_ignores_stale_deals(self, mock_requeue, MockTokenManager, mock_fetch):
        """
        Verify that smart_ingestor does NOT update a deal if Keepa doesn't return it in the delta fetch.
        """
        # Mock TokenManager to allow execution
        tm_instance = MockTokenManager.return_value
        tm_instance.should_skip_sync.return_value = False
        tm_instance.REFILL_RATE_PER_MINUTE = 20
        tm_instance.request_permission_for_call = MagicMock()
        tm_instance.sync_tokens = MagicMock()
        tm_instance.emit_heartbeat = MagicMock()

        # Mock fetch_deals_for_deals to return NO new deals (empty list)
        # Returns: (response_dict, headers, tokens_left)
        mock_fetch.return_value = ({'deals': {'dr': []}}, {}, 100)

        # Run Smart Ingestor
        smart_ingestor.run()

        # Check if last_seen_utc updated
        with sqlite3.connect(TEST_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT last_seen_utc FROM deals WHERE ASIN = ?", (self.stale_asin,))
            row = cursor.fetchone()
            last_seen = row[0]

        print(f"Original Time: {self.stale_time}")
        print(f"Current Time:  {last_seen}")

        # It should be UNCHANGED because smart_ingestor didn't see it
        self.assertEqual(last_seen, self.stale_time, "Smart Ingestor mistakenly updated a deal it didn't fetch!")

    @patch('keepa_deals.smart_ingestor.fetch_deals_for_deals')
    @patch('keepa_deals.smart_ingestor.fetch_current_stats_batch')
    @patch('keepa_deals.smart_ingestor.TokenManager')
    @patch('keepa_deals.smart_ingestor.requeue_stuck_restrictions')
    def test_smart_ingestor_rescues_stale_deals(self, mock_requeue, MockTokenManager, mock_stats, mock_fetch):
        """
        Verify that smart_ingestor finds and updates deals > 48h old, even if Keepa delta fetch returns nothing.
        """
        # Mock TokenManager
        tm_instance = MockTokenManager.return_value
        tm_instance.should_skip_sync.return_value = False
        tm_instance.REFILL_RATE_PER_MINUTE = 20 # High enough to trigger rescue
        tm_instance.request_permission_for_call = MagicMock()
        tm_instance.sync_tokens = MagicMock()
        tm_instance.emit_heartbeat = MagicMock()

        # Mock fetch_deals_for_deals to return NO new deals (Keepa is silent)
        mock_fetch.return_value = ({'deals': {'dr': []}}, {}, 100)

        # Mock fetch_current_stats_batch to return product data for the stale ASIN
        # This simulates that the product still exists and we fetched its stats
        mock_stats.return_value = ({'products': [{
            'asin': self.stale_asin,
            'stats': {'current': [2000, 2000, 1000]}, # Valid stats
            'lastUpdate': 123456
        }]}, {}, {}, 99)

        # Run Smart Ingestor
        smart_ingestor.run()

        # Check if last_seen_utc updated
        with sqlite3.connect(TEST_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT last_seen_utc, source FROM deals WHERE ASIN = ?", (self.stale_asin,))
            row = cursor.fetchone()
            last_seen = row[0]
            source = row[1]

        print(f"Original Time: {self.stale_time}")
        print(f"New Time:      {last_seen}")
        print(f"Source:        {source}")

        # It SHOULD be updated now
        self.assertNotEqual(last_seen, self.stale_time, "Smart Ingestor failed to rescue stale deal!")
        self.assertGreater(last_seen, self.stale_time)
        self.assertEqual(source, 'stale_rescue')

    def test_janitor_deletes_stale_deal(self):
        """
        Verify that Janitor deletes the deal if it gets too old.
        """
        # Manually age the deal to > 72h
        aged_time = (datetime.now(timezone.utc) - timedelta(hours=73)).isoformat()
        with sqlite3.connect(TEST_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE deals SET last_seen_utc = ? WHERE ASIN = ?", (aged_time, self.stale_asin))
            conn.commit()

        # Run Janitor
        janitor._clean_stale_deals_logic(grace_period_hours=72)

        # Check if deleted
        with sqlite3.connect(TEST_DB) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM deals WHERE ASIN = ?", (self.stale_asin,))
            count = cursor.fetchone()[0]

        self.assertEqual(count, 0, "Janitor failed to delete stale deal")

if __name__ == '__main__':
    unittest.main()
