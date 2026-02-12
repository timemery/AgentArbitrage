
import unittest
from unittest.mock import MagicMock, patch
from keepa_deals.token_manager import TokenManager
import logging

logging.basicConfig(level=logging.INFO)

class TestDeficitStrategy(unittest.TestCase):
    @patch('redis.Redis.from_url')
    @patch('time.sleep') # Suppress sleep
    def test_deficit_allowed_low_threshold(self, mock_sleep, mock_redis_from_url):
        # Setup
        mock_redis = MagicMock()
        mock_redis_from_url.return_value = mock_redis
        mock_redis.get.return_value = "1.0" # Initial state (Very low but positive)

        # Scenario: Threshold 1. Start 1. Cost 100. Result -99.
        # Logic: 1 >= 1 -> Allowed.
        mock_redis.incrbyfloat.return_value = -99.0

        tm = TokenManager("fake")
        tm.MIN_TOKEN_THRESHOLD = 1 # Simulating the change or assuming default will be changed

        print("Testing Deficit Allowance (1 start, 100 cost, 1 thresh)...")
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
    def test_deficit_denied_below_threshold(self, mock_sleep, mock_redis_from_url):
        # Setup
        mock_redis = MagicMock()
        mock_redis_from_url.return_value = mock_redis
        mock_redis.get.return_value = "0.5" # Initial state

        # Scenario: Threshold 1. Start 0.5. Cost 100. Result -99.5.
        # Logic: 0.5 < 1 -> Denied.
        mock_redis.incrbyfloat.side_effect = [-99.5, 0.5] # Decrement, then Revert

        tm = TokenManager("fake")
        tm.MIN_TOKEN_THRESHOLD = 1

        # We expect it to loop/wait. We'll raise exception in sleep to break loop
        mock_sleep.side_effect = InterruptedError("Break Loop")

        print("Testing Deficit Denial (0.5 start, 100 cost, 1 thresh)...")
        try:
            tm.request_permission_for_call(100)
        except InterruptedError:
            pass

        # Verify Revert called
        self.assertEqual(mock_redis.incrbyfloat.call_count, 2)
        print("PASS: Deficit denied.")

    @patch('redis.Redis.from_url')
    def test_burst_threshold_adjustment(self, mock_redis_from_url):
        mock_redis = MagicMock()
        mock_redis_from_url.return_value = mock_redis

        tm = TokenManager("fake")

        # Test Low Rate -> High Burst (New Logic)
        tm.REFILL_RATE_PER_MINUTE = 5
        tm._adjust_burst_threshold()
        # Proposed logic: if rate < 10, burst = 40 (was 150/80)
        self.assertEqual(tm.BURST_THRESHOLD, 40)
        print("PASS: Low Rate Burst Adjustment.")

        # Test High Rate -> High Burst
        tm.REFILL_RATE_PER_MINUTE = 20
        tm._adjust_burst_threshold()
        self.assertEqual(tm.BURST_THRESHOLD, 280)
        print("PASS: High Rate Burst Adjustment.")

if __name__ == '__main__':
    unittest.main()
