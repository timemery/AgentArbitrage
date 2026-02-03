import unittest
from unittest.mock import MagicMock, patch
from keepa_deals.token_manager import TokenManager

class TestTokenManagerRedis(unittest.TestCase):
    @patch('redis.Redis.from_url')
    def test_request_permission_uses_incrbyfloat(self, mock_redis_from_url):
        # Setup mock redis
        mock_redis = MagicMock()
        mock_redis_from_url.return_value = mock_redis

        # Mock initial state load
        mock_redis.get.return_value = "100.0"

        # Mock decr behavior (simulating incrbyfloat)
        # First call (decrement): returns 95.0
        mock_redis.incrbyfloat.side_effect = [95.0]

        tm = TokenManager("dummy_key")

        # Action
        tm.request_permission_for_call(5)

        # Verify
        # Check that incrbyfloat was called with negative cost
        mock_redis.incrbyfloat.assert_called_with(tm.REDIS_KEY_TOKENS, -5)

    @patch('redis.Redis.from_url')
    def test_revert_uses_incrbyfloat(self, mock_redis_from_url):
        # Setup mock redis to fail the check (low tokens)
        mock_redis = MagicMock()
        mock_redis_from_url.return_value = mock_redis

        mock_redis.get.return_value = "10.0" # Start low

        # 1. Decrement 5 -> -5.0 (Too low, fail priority pass because negative)
        # 2. Revert 5 -> 0.0
        mock_redis.incrbyfloat.side_effect = [-5.0, 0.0]

        tm = TokenManager("dummy_key")

        # Action
        with patch('time.sleep', side_effect=InterruptedError("Break Loop")):
            try:
                tm.request_permission_for_call(5)
            except InterruptedError:
                pass

        # Verify calls
        # 1. Decrement
        mock_redis.incrbyfloat.assert_any_call(tm.REDIS_KEY_TOKENS, -5)
        # 2. Revert (Increment)
        mock_redis.incrbyfloat.assert_any_call(tm.REDIS_KEY_TOKENS, 5)

if __name__ == '__main__':
    unittest.main()
