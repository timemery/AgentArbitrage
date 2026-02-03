import unittest
from unittest.mock import patch, MagicMock
import threading
import time
import redis
import os
import sys

# Add repo root to path
sys.path.append(os.getcwd())

from keepa_deals.token_manager import TokenManager
import keepa_deals.keepa_api # Ensure module is loaded for patching

class MockRedis:
    def __init__(self):
        self.data = {}
        self.lock = threading.Lock()

    def get(self, key):
        with self.lock:
            return self.data.get(key)

    def set(self, key, value):
        with self.lock:
            self.data[key] = str(value)

    def decrby(self, key, amount):
        with self.lock:
            current = float(self.data.get(key, 0))
            new_val = current - amount
            self.data[key] = str(new_val)
            return new_val

    def delete(self, key):
        with self.lock:
            if key in self.data:
                del self.data[key]

    def ping(self):
        return True

class TestTokenContention(unittest.TestCase):
    def setUp(self):
        # We use MockRedis because real Redis is not available in sandbox
        self.mock_redis = MockRedis()
        self.mock_redis.set('keepa_tokens_left', 100) # Start with 100
        self.mock_redis.set('keepa_refill_rate', 5)

        # Patch redis.Redis.from_url to return our mock
        self.redis_patcher = patch('redis.Redis.from_url', return_value=self.mock_redis)
        self.redis_patcher.start()

    def tearDown(self):
        self.redis_patcher.stop()

    @patch('keepa_deals.keepa_api.get_token_status')
    def test_concurrent_access(self, mock_get_status):
        # Mock API return to reflect current Redis state (simulating consistent server state)
        def get_status_side_effect(*args, **kwargs):
            val = float(self.mock_redis.get('keepa_tokens_left') or 0)
            return {'tokensLeft': val, 'refillRate': 5}
        mock_get_status.side_effect = get_status_side_effect

        # 1. Reset Redis to 100
        self.mock_redis.set('keepa_tokens_left', 100)

        threads = []
        def worker_func():
            tm = TokenManager("fake_key")
            try:
                # Only calling the method. The patch is applied globally below.
                tm.request_permission_for_call(20)
                return "Proceeded"
            except InterruptedError:
                return "Waited"
            except Exception as e:
                return f"Error: {e}"

        results = []
        def thread_wrapper():
            results.append(worker_func())

        # Apply patch globally during thread execution
        with patch('time.sleep', side_effect=InterruptedError("Sleeping")):
             # Spawn 15 threads, cost 20 each. Total 300. Available 100.
            for _ in range(15):
                t = threading.Thread(target=thread_wrapper)
                threads.append(t)
                t.start()

            for t in threads:
                t.join()

        # Check results
        proceeded = results.count("Proceeded")
        waited = results.count("Waited")

        final_tokens = float(self.mock_redis.get('keepa_tokens_left'))

        print(f"Threads: 15. Cost/Thread: 20. Start: 100.")
        print(f"Proceeded: {proceeded}")
        print(f"Waited: {waited}")
        print(f"Final Redis Tokens: {final_tokens}")

        # Assertions
        # 100 tokens / 20 cost = 5 should proceed.
        # Since MockRedis is perfectly atomic and threads are fast, it might be exactly 5.
        # But race conditions in TokenManager (Read -> Check -> Decr) might allow one or two extra.
        # The key is that it shouldn't be 15.

        # With threshold 50 and cost 20:
        # 100 -> 80 (OK)
        # 80 -> 60 (OK)
        # 60 -> 40 (OK)
        # 40 -> Wait (Because 40 < 50 and 20 > 10)
        # So exactly 3 should proceed if serialized.
        # If raced, maybe 4 or 5.

        self.assertLessEqual(proceeded, 6, "Too many threads proceeded! Race condition is bad.")
        self.assertGreaterEqual(proceeded, 3, "Too few threads proceeded.")

        expected_tokens = 100 - (proceeded * 20)
        self.assertAlmostEqual(final_tokens, expected_tokens, delta=1)

if __name__ == '__main__':
    unittest.main()
