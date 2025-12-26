import unittest
from unittest.mock import MagicMock, patch
import math

from keepa_deals.token_manager import TokenManager

class TestTokenManagerLogic(unittest.TestCase):

    def setUp(self):
        self.api_key = "dummy_key"
        self.tm = TokenManager(self.api_key)
        self.tm.REFILL_RATE_PER_MINUTE = 5
        self.tm.max_tokens = 300
        self.tm.MIN_TOKEN_THRESHOLD = 50

    @patch('time.sleep')
    @patch('time.time')
    def test_aggressive_consumption(self, mock_time, mock_sleep):
        # Setup: We have 60 tokens (Above threshold 50)
        # Cost is 200.
        # Logic should ALLOW call without waiting for refill.

        mock_time.return_value = 1000
        self.tm.last_api_call_timestamp = 0 # Long ago
        self.tm.last_refill_timestamp = 1000
        self.tm.tokens = 60

        estimated_cost = 200

        self.tm.request_permission_for_call(estimated_cost)

        # Verify: NO sleep called for token recovery (maybe sleep for rate limit, but setup says long ago)
        # Actually rate limit check is:
        # time_since_last_call = 1000 - 0 = 1000 > 60. No rate limit sleep.
        # Token check: 60 > 50. Proceed.

        # Check sleep calls
        mock_sleep.assert_not_called()
        print("Test Aggressive Consumption: PASSED (No sleep triggered)")

    @patch('time.sleep')
    @patch('time.time')
    def test_smart_recovery(self, mock_time, mock_sleep):
        # Setup: We have 40 tokens (Below threshold 50)
        # Logic should WAIT until 55 (Threshold + 5).
        # Need 15 tokens.
        # Rate 5/min. Time = 3 mins = 180s.

        mock_time.return_value = 1000
        self.tm.last_api_call_timestamp = 0
        self.tm.last_refill_timestamp = 1000
        self.tm.tokens = 40

        estimated_cost = 200

        self.tm.request_permission_for_call(estimated_cost)

        # Verify sleep called
        expected_wait = math.ceil(((55 - 40) / 5) * 60) # 15/5 * 60 = 180
        mock_sleep.assert_called_with(expected_wait)
        print(f"Test Smart Recovery: PASSED (Sleep called with {expected_wait}s)")

    @patch('time.sleep')
    @patch('time.time')
    def test_hard_stop(self, mock_time, mock_sleep):
        # Setup: We have -10 tokens.
        # Logic should WAIT until 10.
        # Need 20 tokens.
        # Rate 5/min. Time = 4 mins = 240s.

        mock_time.return_value = 1000
        self.tm.last_api_call_timestamp = 0
        self.tm.last_refill_timestamp = 1000
        self.tm.tokens = -10

        estimated_cost = 200

        self.tm.request_permission_for_call(estimated_cost)

        # Verify sleep called
        expected_wait = math.ceil(((10 - (-10)) / 5) * 60) # 20/5 * 60 = 240
        mock_sleep.assert_called_with(expected_wait)
        print(f"Test Hard Stop: PASSED (Sleep called with {expected_wait}s)")

if __name__ == '__main__':
    unittest.main()
