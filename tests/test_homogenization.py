import json
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Fix path for import
sys.path.append(os.getcwd())

# Do NOT mock the entire redis module, just the client
# sys.modules['redis'] = MagicMock()

from keepa_deals.maintenance_tasks import homogenize_intelligence_task
import keepa_deals.maintenance_tasks

class TestHomogenization(unittest.TestCase):
    def setUp(self):
        self.test_file = 'test_intelligence_homogenize.json'
        # Create a list with semantic duplicates
        self.data = [
            "Always buy low and sell high.",
            "Buy low, sell high is the key.",
            "Purchasing at a lower price and selling at a higher price is essential.",
            "Avoid restricted brands.",
            "Stay away from gated items."
        ]
        with open(self.test_file, 'w') as f:
            json.dump(self.data, f)

        # Patch the constant in the module where it is used
        self.file_patcher = patch('keepa_deals.maintenance_tasks.INTELLIGENCE_FILE', self.test_file)
        self.file_patcher.start()

    def tearDown(self):
        self.file_patcher.stop()
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    @patch('keepa_deals.maintenance_tasks.query_xai_api')
    @patch('keepa_deals.maintenance_tasks.redis.Redis')
    def test_homogenize_intelligence(self, mock_redis_cls, mock_query):
        # Mock Redis client instance
        mock_redis_client = MagicMock()
        mock_redis_cls.from_url.return_value = mock_redis_client

        # Mock the LLM response to return a merged list
        # Expected: 2 unique concepts from the 5 items
        mock_response = {
            'choices': [{
                'message': {
                    'content': '["Always buy low and sell high.", "Avoid restricted brands and gated items."]'
                }
            }]
        }
        mock_query.return_value = mock_response

        # Use .apply() to execute the task synchronously (Celery feature)
        # However, .apply() will try to use the configured backend (Redis) to store results.
        # If Redis server is not running, this might fail unless we configure Celery to use a different backend or None.

        # Alternative: Unwrap the task function.
        # The underlying function is available via .__wrapped__ if it was a simple decorator,
        # but Celery tasks are classes.

        # Best bet: Mock celery_app.conf.broker_url so redis.Redis.from_url works?
        # But we mocked redis.Redis in the module.

        # If we execute the task *directly* as a function?
        # Celery tasks are callable.
        removed_count = homogenize_intelligence_task()

        # But calling it directly might skip the decorator logic? No, calling a task calls its run method usually,
        # but in Celery < 5 it was different. In Celery 5, calling the task instance calls the body.

        # Original 5, New 2 -> Removed 3
        self.assertEqual(removed_count, 3)

        with open(self.test_file, 'r') as f:
            new_data = json.load(f)
            self.assertEqual(len(new_data), 2)
            # Handle object format
            found = False
            for item in new_data:
                content = item.get('content') if isinstance(item, dict) else item
                if content == "Always buy low and sell high.":
                    found = True
                    break
            self.assertTrue(found, "Expected concept not found in homogenized data")

if __name__ == '__main__':
    unittest.main()
