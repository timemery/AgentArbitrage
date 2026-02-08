import unittest
from unittest.mock import MagicMock, patch
import time
import sys
import os
import logging

# Configure logging to stdout
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

# Ensure project root is in sys.path for direct execution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals.token_manager import TokenManager

class TestTokenManagerThreshold(unittest.TestCase):

    @patch('keepa_deals.token_manager.redis.Redis.from_url')
    def test_dynamic_burst_threshold(self, mock_redis_from_url):
        # Setup Mock Redis
        mock_redis = MagicMock()
        mock_redis_from_url.return_value = mock_redis

        # Initialize TokenManager
        tm = TokenManager("fake_api_key")

        # Default (High Rate)
        tm.REFILL_RATE_PER_MINUTE = 20.0
        tm._adjust_burst_threshold()
        self.assertEqual(tm.BURST_THRESHOLD, 280, "Should use 280 for high rates")
        print("High Rate (20.0) -> Threshold 280 [OK]")

        # Low Rate
        tm.REFILL_RATE_PER_MINUTE = 5.0
        tm._adjust_burst_threshold()
        self.assertEqual(tm.BURST_THRESHOLD, 80, "Should use 80 for low rates")
        print("Low Rate (5.0) -> Threshold 80 [OK]")

        # Borderline (9.9)
        tm.REFILL_RATE_PER_MINUTE = 9.9
        tm._adjust_burst_threshold()
        self.assertEqual(tm.BURST_THRESHOLD, 80, "Should use 80 for rate < 10")

        # Borderline (10.0)
        tm.REFILL_RATE_PER_MINUTE = 10.0
        tm._adjust_burst_threshold()
        self.assertEqual(tm.BURST_THRESHOLD, 280, "Should use 280 for rate >= 10")

        print("SUCCESS")

if __name__ == '__main__':
    unittest.main()
