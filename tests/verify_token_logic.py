
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add parent directory to path to import keepa_deals
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from keepa_deals.token_manager import TokenManager

class TestTokenManagerLeak(unittest.TestCase):
    def setUp(self):
        # Patch redis
        self.redis_patcher = patch('redis.Redis.from_url')
        self.mock_redis = self.redis_patcher.start()
        self.mock_client = MagicMock()
        self.mock_redis.return_value = self.mock_client

        # Patch time to control flow if needed
        self.time_patcher = patch('time.time')
        self.mock_time = self.time_patcher.start()
        self.mock_time.return_value = 1000.0

        # Create manager
        self.tm = TokenManager("dummy_key")

        # Mock Redis behavior
        self.redis_store = {}

        def mock_get(key):
            return self.redis_store.get(key)

        def mock_set(key, val):
            self.redis_store[key] = str(val)

        def mock_incrbyfloat(key, amount):
            curr = float(self.redis_store.get(key, 100.0))
            new_val = curr + amount
            self.redis_store[key] = str(new_val)
            return new_val

        def mock_delete(key):
            if key in self.redis_store:
                del self.redis_store[key]

        self.mock_client.get.side_effect = mock_get
        self.mock_client.set.side_effect = mock_set
        self.mock_client.incrbyfloat.side_effect = mock_incrbyfloat
        self.mock_client.delete.side_effect = mock_delete

        # Mock sync_tokens to avoid API calls
        self.tm.sync_tokens = MagicMock()

        # Mock wait loop to raise exception instead of sleeping
        self.tm._wait_for_tokens = MagicMock(side_effect=Exception("Entered Wait Loop"))

    def tearDown(self):
        self.redis_patcher.stop()
        self.time_patcher.stop()

    def test_recharge_mode_bypass_leak(self):
        """
        Scenario:
        1. Rate starts low (5). Tokens drop below threshold (20).
        2. System enters Recharge Mode.
        3. Rate spikes to high (12).
        4. Request should STILL be blocked (Wait Loop) because we haven't reached BURST (80).
        5. Currently (The Bug), it bypasses the check because rate > 10.
        """

        # 1. Setup: Low Rate, Low Tokens
        self.tm.REFILL_RATE_PER_MINUTE = 5.0
        self.redis_store[self.tm.REDIS_KEY_TOKENS] = "19.0"
        self.redis_store[self.tm.REDIS_KEY_RATE] = "5.0"
        self.tm.tokens = 19.0

        # 2. Trigger Recharge Mode
        # Attempt to consume 5 tokens.
        # Old balance = 19 + 5? No, logic uses incrbyfloat(-5). New=14. Old=19.
        # 19 < 20 -> Trigger Recharge Mode.
        print("\n--- Step 1: Triggering Recharge Mode (Rate=5, Tokens=19) ---")
        try:
            self.tm.request_permission_for_call(5)
        except Exception as e:
            if str(e) == "Entered Wait Loop":
                print("Step 1 Success: Entered Wait Loop correctly.")
            else:
                self.fail(f"Unexpected exception: {e}")
        else:
            # It might just set the flag and loop, calling _wait_for_tokens.
            # If request_permission catches the exception internally? No it doesn't.
            # The loop calls continue. Wait, _wait_for_tokens is called.
            # So exception should be raised.
            pass

        # Verify Recharge Mode is Active in Redis
        is_recharging = self.redis_store.get(self.tm.REDIS_KEY_RECHARGE_MODE)
        self.assertEqual(is_recharging, "1", "Recharge Mode should be active in Redis.")

        # 3. Simulate Rate Spike
        print("\n--- Step 2: Simulating Rate Spike to 12.0 ---")
        self.tm.REFILL_RATE_PER_MINUTE = 12.0
        # Redis rate updated too (though local variable matters most for the check)
        self.redis_store[self.tm.REDIS_KEY_RATE] = "12.0"

        # Tokens still low (19 or 14 depending on revert logic)
        # Revert logic in code: self.redis_client.incrbyfloat(..., cost_int)
        # So tokens should be back to ~19.
        self.tm.tokens = 19.0
        self.redis_store[self.tm.REDIS_KEY_TOKENS] = "19.0"

        # 4. Attempt Request Again
        # EXPECTED BEHAVIOR (FIXED): Should see Recharge Mode "1", verify tokens < BURST (80), and Wait.
        # CURRENT BUGGY BEHAVIOR: Checks `if rate < 10`. 12 < 10 is False. Skips check. Allows request.
        print("\n--- Step 3: Attempting Request with High Rate (12.0) ---")

        entered_wait = False
        try:
            self.tm.request_permission_for_call(5)
        except Exception as e:
            if str(e) == "Entered Wait Loop":
                entered_wait = True

        if entered_wait:
            print("RESULT: BLOCKED (Correct Behavior)")
        else:
            print("RESULT: ALLOWED (Leak Detected!)")
            # In the bug state, we expect this to print.
            # Assert failure if we want to enforce "Test fails on bug"
            # But here we want to verify the fix later.
            # So for now, asserting True is fine, just log it.
            # Or assert False to confirm bug.

            # The test should FAIL if the bug exists, so we know we reproduced it.
            self.fail("Leak Detected! Request was allowed despite Recharge Mode active.")

if __name__ == '__main__':
    unittest.main()
