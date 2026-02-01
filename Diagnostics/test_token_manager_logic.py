#!/usr/bin/env python3
import sys
import os
import unittest
import math
from unittest.mock import MagicMock, patch

# Ensure root directory is in path so we can import keepa_deals
sys.path.append(os.getcwd())

# Simple .env parser to avoid dependency issues
def load_env_file():
    env_path = os.path.join(os.getcwd(), '.env')
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    os.environ[key] = value

load_env_file()

from keepa_deals.token_manager import TokenManager

class TestTokenManagerLogic(unittest.TestCase):

    def setUp(self):
        # Use real API key if available to avoid 400 errors, otherwise fallback to dummy (which will fail integration tests but pass logic tests)
        self.api_key = os.getenv("KEEPA_API_KEY", "dummy_key")
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

        # Mock the sync_tokens method to prevent actual API calls during logic test
        with patch.object(self.tm, 'sync_tokens') as mock_sync:
            self.tm.request_permission_for_call(estimated_cost)

            # Verify: NO sleep called for token recovery (maybe sleep for rate limit, but setup says long ago)
            # Actually rate limit check is:
            # time_since_last_call = 1000 - 0 = 1000 > 60. No rate limit sleep.
            # Token check: 60 > 50. Proceed.

            # Check sleep calls
            # NOTE: TokenManager *might* call sleep(0) or similar if logic dictates,
            # but for aggressive consumption it should NOT sleep for recovery.
            # However, if rate limit logic triggers, it might sleep.
            # In this test setup, last call was 0, now is 1000. 1000 > 60. No rate limit sleep.

            # Correction: assert_not_called() is strict. If the code sleeps for 0.0s it might fail.
            # But let's assume standard behavior.
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

        # Mock the sync_tokens method
        with patch.object(self.tm, 'sync_tokens') as mock_sync:
            # We must mock sleep to ADVANCE time or loop will be infinite if TokenManager loops
            # TokenManager implementation uses a while loop with time.sleep
            # and re-checks tokens.
            # If we mock sleep, we must also ensure tokens 'refill' or the loop condition breaks.

            # Wait! The current TokenManager implementation has a while loop:
            # while remaining_wait > 0:
            #    sleep...
            #    sync_tokens...

            # If we mock sync_tokens to do nothing, self.tokens won't change unless _refill_tokens updates it.
            # _refill_tokens relies on time.time() changing.
            # Since time.time() is mocked to return constant 1000, _refill_tokens will add 0 tokens.
            # Infinite Loop Hazard!

            # FIX: We should rely on the calculation logic, not the loop execution for this unit test.
            # Or we can test that it ENTERS the wait logic.
            # Given the complexity of testing the loop with mocks, let's just trust the logic
            # that calculates 'wait_time_seconds'.

            # But wait, TokenManager calls sleep inside.
            # Let's side_effect the sleep to raise an exception to break the loop,
            # OR we can just check if it calls sleep AT ALL.

            mock_sleep.side_effect = StopIteration("Break Loop")

            try:
                self.tm.request_permission_for_call(estimated_cost)
            except StopIteration:
                pass

            # Verify sleep called
            # It should be called with some value.
            # The exact value might differ due to rounding or loop chunks (30s).
            # But it MUST be called.
            self.assertTrue(mock_sleep.called)
            print(f"Test Smart Recovery: PASSED (Sleep called)")

    @patch('time.sleep')
    @patch('time.time')
    def test_hard_stop(self, mock_time, mock_sleep):
        # Setup: We have -10 tokens.
        # Logic should WAIT until 10.

        mock_time.return_value = 1000
        self.tm.last_api_call_timestamp = 0
        self.tm.last_refill_timestamp = 1000
        self.tm.tokens = -10

        estimated_cost = 200

        # Mock sync_tokens
        with patch.object(self.tm, 'sync_tokens') as mock_sync:
             mock_sleep.side_effect = StopIteration("Break Loop")
             try:
                self.tm.request_permission_for_call(estimated_cost)
             except StopIteration:
                pass

             self.assertTrue(mock_sleep.called)
             print(f"Test Hard Stop: PASSED (Sleep called)")

    def test_connectivity_check(self):
        """
        Integration test: Does the TokenManager actually connect to Keepa without error?
        This test is NOT mocked and uses the real API key.
        """
        if self.api_key == "dummy_key":
            print("Skipping connectivity check: No API Key found.")
            return

        print("\nRunning Connectivity Check (REAL API CALL)...")
        try:
            self.tm.sync_tokens()
            print(f"Connectivity Check: PASSED. Tokens Left: {self.tm.tokens}, Rate: {self.tm.REFILL_RATE_PER_MINUTE}")
        except Exception as e:
            self.fail(f"Connectivity Check: FAILED with error: {e}")

if __name__ == '__main__':
    unittest.main()
