import unittest
from unittest.mock import MagicMock, patch
import time
import sys
import logging

# Configure logging to stdout
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

from keepa_deals.token_manager import TokenManager

class TestTokenManagerTimeout(unittest.TestCase):

    @patch('keepa_deals.token_manager.redis.Redis.from_url')
    def test_recharge_timeout_triggers(self, mock_redis_from_url):
        # Setup Mock Redis
        mock_redis = MagicMock()
        mock_redis_from_url.return_value = mock_redis

        # Setup Redis GET responses
        current_time = time.time()
        start_time = current_time - 3700

        def redis_get_side_effect(key):
            if key == "keepa_tokens_left":
                return "50"
            elif key == "keepa_refill_rate":
                return "5.0"
            elif key == "keepa_recharge_mode_active":
                return "1"
            elif key == "keepa_recharge_start_time":
                return str(start_time)
            return None

        mock_redis.get.side_effect = redis_get_side_effect

        # Mock incrbyfloat to return a valid float (simulating decrement)
        mock_redis.incrbyfloat.return_value = 49.0

        # Initialize TokenManager
        tm = TokenManager("fake_api_key")

        # Mock sync_tokens
        tm.sync_tokens = MagicMock()
        # Ensure internal state is consistent with mock redis
        tm.tokens = 50.0

        print(f"DEBUG: Start Time in Redis: {start_time}")
        print(f"DEBUG: Current Time: {current_time}")
        print(f"DEBUG: Expected Elapsed: {current_time - start_time}")

        print("Testing request_permission_for_call...")
        start_exec = time.time()

        # This calls the method under test
        tm.request_permission_for_call(1)

        end_exec = time.time()
        print(f"Execution time: {end_exec - start_exec:.4f}s")

        # Assertions
        mock_redis.delete.assert_any_call("keepa_recharge_mode_active")
        mock_redis.delete.assert_any_call("keepa_recharge_start_time")

        # Verify that atomic reservation was attempted (proof that we broke out of the recharge loop)
        mock_redis.incrbyfloat.assert_called()

        print("SUCCESS")

if __name__ == '__main__':
    unittest.main()
