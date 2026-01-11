import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add root to path
sys.path.append(os.getcwd())

from keepa_deals import janitor

class TestJanitorPause(unittest.TestCase):

    @patch('keepa_deals.janitor.get_system_state')
    @patch('keepa_deals.janitor.get_deal_count')
    @patch('keepa_deals.janitor.sqlite3.connect')
    def test_janitor_skips_when_limit_reached(self, mock_sqlite, mock_get_count, mock_get_state):
        """
        Verifies Janitor skips deletion when Artificial Limit is active and reached.
        """
        # --- Setup ---
        # 1. State: Limit Enabled (1000), Current Count (1500) -> Over Limit
        def get_state_side_effect(key, default=None):
            if key == 'backfill_limit_enabled': return 'true'
            if key == 'backfill_limit_count': return '1000'
            return default

        mock_get_state.side_effect = get_state_side_effect
        mock_get_count.return_value = 1500

        # 2. Mock DB (Should NOT be called if logic works)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_sqlite.return_value = mock_conn

        # --- Execute ---
        result = janitor.clean_stale_deals()

        # --- Assertions ---
        # Should return 0 (deleted count)
        self.assertEqual(result, 0)

        # Should NOT have executed DELETE query
        delete_calls = [args[0] for args, _ in mock_cursor.execute.call_args_list if "DELETE" in args[0]]
        self.assertEqual(len(delete_calls), 0, "Janitor attempted deletion despite limit being reached!")

        print("\n[TEST] Verified: Janitor skipped deletion because limit (1000) <= count (1500).")

    @patch('keepa_deals.janitor.get_system_state')
    @patch('keepa_deals.janitor.get_deal_count')
    @patch('keepa_deals.janitor.sqlite3.connect')
    def test_janitor_runs_normal(self, mock_sqlite, mock_get_count, mock_get_state):
        """
        Verifies Janitor runs normally when limit is disabled.
        """
        # --- Setup ---
        mock_get_state.return_value = 'false' # Disabled

        # Mock Context Manager for sqlite3.connect
        # When you call sqlite3.connect(), it returns a connection.
        # When you enter the 'with' block, it calls __enter__, which returns the connection.
        mock_conn = MagicMock()
        mock_cursor = MagicMock()

        # IMPORTANT: The cursor must return a tuple when fetchone() is called
        mock_cursor.fetchone.return_value = (50,) # 50 items to delete

        mock_conn.cursor.return_value = mock_cursor
        mock_sqlite.return_value.__enter__.return_value = mock_conn # Fix for context manager

        # --- Execute ---
        result = janitor.clean_stale_deals()

        # --- Assertions ---
        # Should have executed SQL queries
        self.assertTrue(mock_cursor.execute.called)

        # Should have attempted delete
        delete_calls = [args[0] for args, _ in mock_cursor.execute.call_args_list if "DELETE" in args[0]]
        self.assertTrue(len(delete_calls) > 0, "Janitor did NOT attempt deletion when limit was disabled!")

        # Should return 50
        self.assertEqual(result, 50)

        print("[TEST] Verified: Janitor ran normally when limit disabled.")

if __name__ == '__main__':
    unittest.main()
