import unittest
from unittest.mock import MagicMock, patch
import time
import sys
import os
import threading

# Add repo root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals.token_manager import TokenManager

class TestTokenManagerUpgrade(unittest.TestCase):

    def setUp(self):
        self.api_key = "dummy_key"
        self.tm = TokenManager(self.api_key)
        # Mock Redis
        self.tm.redis_client = MagicMock()
        self.tm.redis_client.get.side_effect = self.mock_redis_get
        self.tm.redis_client.incrbyfloat.side_effect = self.mock_redis_incrbyfloat
        self.tm.redis_client.set.side_effect = self.mock_redis_set

        self.redis_store = {
            self.tm.REDIS_KEY_TOKENS: "100.0",
            self.tm.REDIS_KEY_RATE: "20.0",
            self.tm.REDIS_KEY_RECHARGE_MODE: None,
            "keepa_worker_last_heartbeat": None,
            "keepa_recharge_start_time": None
        }

    def mock_redis_get(self, key):
        return self.redis_store.get(key)

    def mock_redis_set(self, key, value):
        self.redis_store[key] = str(value)

    def mock_redis_incrbyfloat(self, key, amount):
        current = float(self.redis_store.get(key, "0"))
        new_val = current + amount
        self.redis_store[key] = str(new_val)
        return new_val

    def mock_redis_delete(self, key):
        if key in self.redis_store:
            del self.redis_store[key]

    def test_emit_heartbeat(self):
        """Test that emit_heartbeat updates Redis."""
        self.tm.emit_heartbeat()
        self.assertIsNotNone(self.redis_store["keepa_worker_last_heartbeat"])
        # Check it's recent
        ts = float(self.redis_store["keepa_worker_last_heartbeat"])
        self.assertTrue(time.time() - ts < 1.0)

    def test_stall_check_warning(self):
        """Test that sync_tokens warns if tokens are suspiciously high."""
        with patch('keepa_deals.token_manager.logger') as mock_logger:
            # We must mock get_token_status
            with patch('keepa_deals.keepa_api.get_token_status') as mock_get_status:
                mock_get_status.return_value = {'tokensLeft': 300, 'refillRate': 20}

                # We need to set up the TM so it doesn't throttle
                self.tm.last_sync_request_timestamp = 0
                self.tm.STALL_THRESHOLD = 290

                # Execute sync_tokens
                self.tm.sync_tokens()

                # Verify warning was logged
                found = False
                for call in mock_logger.warning.call_args_list:
                    args, _ = call
                    if "POTENTIAL STALL" in args[0]:
                        found = True
                        break
                self.assertTrue(found, "Should have logged POTENTIAL STALL warning")

    def test_soft_buffer_trigger_logic(self):
        """
        Test the Soft Buffer trigger logic specifically.
        We want to ensure that if tokens < 20, we trigger Recharge Mode.
        CRITICAL: We also want to ensure the CURRENT call is NOT blocked by the mode we just set.
        """
        # 1. Setup tokens to be low (15)
        self.tm.tokens = 15.0
        self.redis_store[self.tm.REDIS_KEY_TOKENS] = "15.0"

        # 2. We verify that request_permission_for_call completes (doesn't hang)
        # and that AFTER it completes, the recharge mode is set.

        # To avoid infinite hanging if the bug exists, we run this in a thread or we mock wait?
        # A simpler way is to inspect the logic flow or mock the 'wait' to raise an exception if called.

        # Let's mock _wait_for_tokens to raise an exception so we fail fast if it tries to wait.
        self.tm._wait_for_tokens = MagicMock(side_effect=Exception("WAIT_CALLED"))

        try:
            # We request 5 tokens. 15 available. Should succeed.
            # But if it triggers recharge mode logic improperly, it might try to wait.
            self.tm.request_permission_for_call(5)

            # If we get here, it didn't wait. Good.
            # Now verify Recharge Mode IS set for the NEXT guy.
            self.assertEqual(self.redis_store.get(self.tm.REDIS_KEY_RECHARGE_MODE), "1")

        except Exception as e:
            if str(e) == "WAIT_CALLED":
                self.fail("Soft Buffer Logic Bug: The current call was forced to wait instead of being allowed to finish gracefully!")
            else:
                raise e

if __name__ == '__main__':
    unittest.main()
