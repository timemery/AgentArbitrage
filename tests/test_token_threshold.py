import unittest
from unittest.mock import MagicMock, patch
import math
import sys
import os

# Ensure the app can be imported
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals.token_manager import TokenManager

class TestTokenThreshold(unittest.TestCase):
    def setUp(self):
        # Patch Redis to avoid real connection
        self.redis_patcher = patch('redis.Redis.from_url')
        self.mock_redis = self.redis_patcher.start()
        self.mock_client = MagicMock()
        self.mock_redis.return_value = self.mock_client

        # Setup mock redis behaviors
        self.mock_client.ping.return_value = True
        self.mock_client.get.return_value = "100" # Default tokens
        self.mock_client.incrbyfloat.side_effect = self._mock_incrbyfloat

        self.current_tokens = 100.0

    def tearDown(self):
        self.redis_patcher.stop()

    def _mock_incrbyfloat(self, key, amount):
        if key == "keepa_tokens_left":
            self.current_tokens += amount
            return self.current_tokens
        return 0

    def test_threshold_20_allowed(self):
        """Test that with 20 threshold, 20 tokens is enough to start (Cost 10)."""
        tm = TokenManager("dummy_key")
        tm.MIN_TOKEN_THRESHOLD = 20
        self.current_tokens = 20.0
        tm.tokens = 20.0
        tm.redis_client = self.mock_client

        # We need to mock _wait_for_tokens to avoid actual sleep if it fails
        with patch.object(tm, '_wait_for_tokens') as mock_wait:
            # If successful, wait is NOT called.
            # Cost 10.
            # 20 - 10 = 10. Old Balance = 20. 20 >= 20. Allowed.
            tm.request_permission_for_call(10)
            mock_wait.assert_not_called()
            self.assertEqual(self.current_tokens, 10.0)

    def test_threshold_20_denied_large_cost(self):
        """Test that with 20 threshold, 19 tokens is NOT enough for Large Cost (Non-Priority)."""
        tm = TokenManager("dummy_key")
        tm.MIN_TOKEN_THRESHOLD = 20
        self.current_tokens = 19.0
        tm.tokens = 19.0
        tm.redis_client = self.mock_client

        # Cost 20 (Greater than 10, so Priority Pass ignored).
        # 19 - 20 = -1.
        # Old Balance = 19. 19 < 20. Denied.

        with patch.object(tm, '_wait_for_tokens', side_effect=StopIteration("Wait called")):
            try:
                tm.request_permission_for_call(20)
            except StopIteration:
                pass # Expected

            # Should have reverted
            self.assertEqual(self.current_tokens, 19.0)

    def test_controlled_deficit(self):
        """Test allowing negative tokens if starting balance was sufficient."""
        tm = TokenManager("dummy_key")
        tm.MIN_TOKEN_THRESHOLD = 20
        self.current_tokens = 25.0 # Start with 25
        tm.tokens = 25.0
        tm.redis_client = self.mock_client

        # Cost 40.
        # 25 - 40 = -15.
        # Old Balance = 25.
        # 25 >= 20. Allowed.

        with patch.object(tm, '_wait_for_tokens') as mock_wait:
            tm.request_permission_for_call(40)
            mock_wait.assert_not_called()
            self.assertEqual(self.current_tokens, -15.0)

if __name__ == '__main__':
    unittest.main()
