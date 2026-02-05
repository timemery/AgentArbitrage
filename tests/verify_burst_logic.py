
import unittest
from unittest.mock import MagicMock, patch
from keepa_deals.token_manager import TokenManager

class TestBurstLogic(unittest.TestCase):
    def setUp(self):
        self.mock_redis = MagicMock()
        self.mock_redis.get.return_value = None # Default: Key doesn't exist

        # Mock incrbyfloat
        def side_effect_incr(key, amount):
            if key == "keepa_tokens_left":
                self.tm.tokens += float(amount)
                return self.tm.tokens
            return 0
        self.mock_redis.incrbyfloat.side_effect = side_effect_incr

        # Mock set/delete for checking logic flow
        self.redis_state = {}
        def side_effect_set(key, val):
            self.redis_state[key] = val
        self.mock_redis.set.side_effect = side_effect_set

        def side_effect_get(key):
            return self.redis_state.get(key)
        self.mock_redis.get.side_effect = side_effect_get

        def side_effect_delete(key):
            if key in self.redis_state:
                del self.redis_state[key]
        self.mock_redis.delete.side_effect = side_effect_delete

    def test_enters_recharge_mode_when_low(self):
        """
        Verifies that if tokens drop below threshold at low rate, it enters Recharge Mode.
        """
        api_key = "dummy"
        with patch('redis.Redis.from_url', return_value=self.mock_redis):
            self.tm = TokenManager(api_key)

        self.tm.REFILL_RATE_PER_MINUTE = 5.0
        self.tm.tokens = 10.0 # Critically low
        self.tm.MIN_TOKEN_THRESHOLD = 20
        self.tm.BURST_THRESHOLD = 280

        self.tm.sync_tokens = MagicMock()
        self.tm._wait_for_tokens = MagicMock(side_effect=Exception("Waited"))

        try:
            self.tm.request_permission_for_call(5)
        except Exception as e:
            pass # Expected to wait

        # Verify Redis key was set
        self.assertEqual(self.redis_state.get(TokenManager.REDIS_KEY_RECHARGE_MODE), "1")
        print("\n[Test] Entered Recharge Mode successfully.")

    def test_waits_in_recharge_mode_until_full(self):
        """
        Verifies that it stays in Recharge Mode even if tokens are > 20, until they hit 280.
        """
        api_key = "dummy"
        with patch('redis.Redis.from_url', return_value=self.mock_redis):
            self.tm = TokenManager(api_key)

        self.tm.REFILL_RATE_PER_MINUTE = 5.0
        self.tm.tokens = 100.0 # Healthy, but below Burst
        self.tm.BURST_THRESHOLD = 280

        # Pre-set Recharge Mode
        self.redis_state[TokenManager.REDIS_KEY_RECHARGE_MODE] = "1"

        self.tm.sync_tokens = MagicMock()
        # Mock wait to simulate refill
        def mock_wait(wait, target):
            # Simulate refill happened
            self.tm.tokens = 280.0
        self.tm._wait_for_tokens = MagicMock(side_effect=mock_wait)

        # Call request
        self.tm.request_permission_for_call(5)

        # Should have cleared the key
        self.assertIsNone(self.redis_state.get(TokenManager.REDIS_KEY_RECHARGE_MODE))
        print("[Test] Exited Recharge Mode after hitting 280.")

if __name__ == '__main__':
    unittest.main()
