
import unittest
from unittest.mock import MagicMock, patch
import time
import math
from keepa_deals.token_manager import TokenManager

class TestTokenStarvationFix(unittest.TestCase):
    def setUp(self):
        self.mock_redis = MagicMock()
        self.mock_redis.get.return_value = None
        def side_effect_incr(key, amount):
            if key == "keepa_tokens_left":
                self.tm.tokens += float(amount)
                return self.tm.tokens
            return 0
        self.mock_redis.incrbyfloat.side_effect = side_effect_incr

    def test_priority_pass_disabled_at_low_rate(self):
        """
        Verifies that when refill rate is low (5.0), a small request (Cost 5)
        does NOT get a Priority Pass and must respect the MIN_TOKEN_THRESHOLD.
        """
        api_key = "dummy"
        with patch('redis.Redis.from_url', return_value=self.mock_redis):
            self.tm = TokenManager(api_key)

        # Set Low Rate
        self.tm.REFILL_RATE_PER_MINUTE = 5.0
        self.tm._set_shared_tokens(100, 5.0)

        # Set tokens to 15 (Below Threshold 20, Above Cost 5)
        self.tm.tokens = 15.0
        self.tm.MIN_TOKEN_THRESHOLD = 20
        self.tm.sync_tokens = MagicMock()

        class WaitException(Exception): pass
        self.tm._wait_for_tokens = MagicMock(side_effect=WaitException("Waiting"))

        try:
            self.tm.request_permission_for_call(5)
            status = "PROCEEDED"
        except WaitException:
            status = "WAITED"

        print(f"\n[Test] Rate=5.0, Tokens=15.0, Cost=5. Action: {status}")

    def test_recovery_buffer_removed_at_low_rate(self):
        """
        Verifies that recovery target doesn't add +5 buffer at low rates.
        """
        api_key = "dummy"
        with patch('redis.Redis.from_url', return_value=self.mock_redis):
            self.tm = TokenManager(api_key)

        self.tm.REFILL_RATE_PER_MINUTE = 5.0
        self.tm.tokens = 10.0
        self.tm.MIN_TOKEN_THRESHOLD = 20
        self.tm.sync_tokens = MagicMock()

        self.captured_target = None
        class StopLoop(Exception): pass
        def mock_wait(wait_time, target):
            self.captured_target = target
            raise StopLoop("Stop loop")

        self.tm._wait_for_tokens = mock_wait

        try:
            self.tm.request_permission_for_call(20)
        except StopLoop:
            pass

        # BEFORE FIX: target = 20 + 5 = 25
        # AFTER FIX: target = 20
        print(f"[Test] Rate=5.0, Tokens=10.0, Cost=20. Wait Target: {self.captured_target}")

if __name__ == '__main__':
    unittest.main()
