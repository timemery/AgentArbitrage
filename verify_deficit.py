
import unittest
from unittest.mock import MagicMock, patch
from keepa_deals.token_manager import TokenManager
import logging

logging.basicConfig(level=logging.INFO)

class TestDeficitStrategy(unittest.TestCase):
    @patch('redis.Redis.from_url')
    @patch('time.sleep') # Suppress sleep
    def test_deficit_allowed(self, mock_sleep, mock_redis_from_url):
        # Setup
        mock_redis = MagicMock()
        mock_redis_from_url.return_value = mock_redis
        mock_redis.get.return_value = "90.0" # Initial state

        # Scenario: Threshold 80. Start 90. Cost 100. Result -10.
        # Logic: 90 >= 80 -> Allowed.
        mock_redis.incrbyfloat.return_value = -10.0

        tm = TokenManager("fake")
        tm.MIN_TOKEN_THRESHOLD = 80

        print("Testing Deficit Allowance (90 start, 100 cost, 80 thresh)...")
        tm.request_permission_for_call(100)

        # Verify NO Revert called
        # request_permission_for_call calls incrbyfloat(-100)
        # If reverted, it would call incrbyfloat(100)
        # We expect only ONE call to incrbyfloat
        self.assertEqual(mock_redis.incrbyfloat.call_count, 1)
        mock_redis.incrbyfloat.assert_called_with(tm.REDIS_KEY_TOKENS, -100)
        print("PASS: Deficit allowed.")

    @patch('redis.Redis.from_url')
    @patch('time.sleep')
    def test_deficit_denied(self, mock_sleep, mock_redis_from_url):
        # Setup
        mock_redis = MagicMock()
        mock_redis_from_url.return_value = mock_redis
        mock_redis.get.return_value = "70.0" # Initial state

        # Scenario: Threshold 80. Start 70. Cost 100. Result -30.
        # Logic: 70 < 80 -> Denied.
        mock_redis.incrbyfloat.side_effect = [-30.0, 70.0] # Decrement, then Revert

        tm = TokenManager("fake")
        tm.MIN_TOKEN_THRESHOLD = 80

        # We expect it to loop/wait. We'll raise exception in sleep to break loop
        mock_sleep.side_effect = InterruptedError("Break Loop")

        print("Testing Deficit Denial (70 start, 100 cost, 80 thresh)...")
        try:
            tm.request_permission_for_call(100)
        except InterruptedError:
            pass

        # Verify Revert called
        self.assertEqual(mock_redis.incrbyfloat.call_count, 2)
        # 1. Decrement
        mock_redis.incrbyfloat.assert_any_call(tm.REDIS_KEY_TOKENS, -100)
        # 2. Revert
        mock_redis.incrbyfloat.assert_any_call(tm.REDIS_KEY_TOKENS, 100)
        print("PASS: Deficit denied.")

if __name__ == '__main__':
    unittest.main()
