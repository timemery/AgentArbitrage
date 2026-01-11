import unittest
from unittest.mock import MagicMock, patch, ANY
import sys
import os

# Add root to path
sys.path.append(os.getcwd())

from keepa_deals import simple_task

class TestRefillerUnblocked(unittest.TestCase):

    @patch('keepa_deals.simple_task.redis.Redis')
    @patch('keepa_deals.simple_task.TokenManager')
    @patch('keepa_deals.simple_task.load_watermark')
    @patch('keepa_deals.simple_task.fetch_deals_for_deals')
    @patch('keepa_deals.simple_task.create_deals_table_if_not_exists')
    def test_ignore_backfill_lock(self, mock_create, mock_fetch, mock_load_wm, mock_tm, mock_redis):
        """
        Verifies that simple_task proceeds even if 'backfill_deals_lock' is held.
        """
        # --- Setup ---

        # 1. Mock Redis locks
        mock_redis_instance = MagicMock()
        mock_lock_backfill = MagicMock()
        mock_lock_backfill.locked.return_value = True # BACKFILLER IS RUNNING

        mock_lock_simple = MagicMock()
        mock_lock_simple.acquire.return_value = True # Can acquire own lock

        # When lock() is called, return different locks based on key
        def side_effect_lock(key, timeout=None):
            if key == "backfill_deals_lock":
                return mock_lock_backfill
            return mock_lock_simple

        mock_redis_instance.lock.side_effect = side_effect_lock
        mock_redis.from_url.return_value = mock_redis_instance

        # 2. Mock Token Manager (Enough tokens)
        mock_tm_instance = MagicMock()
        mock_tm_instance.has_enough_tokens.return_value = True
        mock_tm.return_value = mock_tm_instance

        # 3. Mock Watermark
        mock_load_wm.return_value = "2024-01-01T00:00:00+00:00"

        # 4. Mock Fetch (Return empty so it finishes quickly)
        mock_fetch.return_value = ({'deals': {'dr': []}}, 0, 0)

        # --- Execute ---
        simple_task.update_recent_deals()

        # --- Assertions ---
        # If it respected the lock, it would return early and NOT call load_watermark
        mock_load_wm.assert_called()
        print("\n[TEST] Verified: Refiller proceeded despite Backfill Lock.")

if __name__ == '__main__':
    unittest.main()
