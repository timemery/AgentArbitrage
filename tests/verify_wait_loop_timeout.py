import unittest
from unittest.mock import MagicMock, patch
import time
import sys
import os

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from keepa_deals.token_manager import TokenManager

class TestWaitLoopTimeout(unittest.TestCase):
    @patch('keepa_deals.token_manager.redis.Redis.from_url')
    def test_wait_loop_exits_on_timeout(self, mock_redis_from_url):
        mock_redis = MagicMock()
        mock_redis_from_url.return_value = mock_redis

        # Setup Redis start time
        start_time = 1000.0

        # Mock Redis GET to return the start time
        def redis_get(key):
            if key == "keepa_recharge_start_time":
                return str(start_time)
            if key == "keepa_tokens_left":
                return "50"
            return None
        mock_redis.get.side_effect = redis_get

        tm = TokenManager("fake_api_key")
        tm.redis_client = mock_redis
        tm.tokens = 50
        tm.REFILL_RATE_PER_MINUTE = 5

        # Mock sync_tokens to keep tokens low (so it never naturally exits)
        tm.sync_tokens = MagicMock()
        # (sync_tokens usually updates tm.tokens, we leave it at 50)

        # Patch time.time to simulate timeout inside the loop
        with patch('time.time') as mock_time:
            # Sequence of time.time() calls:
            # 1. Initial checks (irrelevant for _wait_for_tokens direct call, but good to set base)
            # 2. Inside loop: check for timeout.

            # We set current time to be WAY past start_time + 3600
            # Start = 1000. Timeout at 4600. Current = 5000.
            mock_time.return_value = 5000.0

            # Patch sleep to avoid waiting
            with patch('time.sleep'):
                print("Entering _wait_for_tokens...")
                # Call directly
                tm._wait_for_tokens(100, 280)
                print("Exited _wait_for_tokens.")

        # Assertions
        # 1. It should have exited.
        # 2. Tokens should still be 50 (it didn't reach 280).
        self.assertEqual(tm.tokens, 50)
        print("SUCCESS: Wait loop exited due to timeout check.")

if __name__ == '__main__':
    unittest.main()
