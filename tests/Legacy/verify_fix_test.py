import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import logging

# Configure logging to stdout
logging.basicConfig(stream=sys.stdout, level=logging.INFO)

# Ensure we can import the module
sys.path.append(os.getcwd())

# Mock 'worker' module BEFORE importing simple_task
mock_worker = MagicMock()
mock_celery_app = MagicMock()

# Define a pass-through decorator for @celery.task
def mock_task_decorator(name=None):
    def decorator(func):
        return func
    return decorator

mock_celery_app.task.side_effect = mock_task_decorator
mock_worker.celery_app = mock_celery_app

sys.modules['worker'] = mock_worker
# Also mock celery.conf.broker_url
mock_celery_app.conf.broker_url = 'redis://localhost:6379/0'


# Mock redis
sys.modules['redis'] = MagicMock()

# Set ENV var
os.environ["KEEPA_API_KEY"] = "TEST_KEY"
os.environ["XAI_TOKEN"] = "TEST_XAI"

from keepa_deals import simple_task

class TestFix(unittest.TestCase):
    @patch('keepa_deals.simple_task.fetch_deals_for_deals')
    @patch('keepa_deals.simple_task.TokenManager')
    @patch('keepa_deals.simple_task.load_watermark')
    @patch('keepa_deals.simple_task._convert_iso_to_keepa_time')
    @patch('keepa_deals.simple_task.create_deals_table_if_not_exists')
    @patch('keepa_deals.simple_task.business_load_settings')
    @patch('keepa_deals.simple_task.redis.Redis')
    def test_sort_type_is_4(self, mock_redis_cls, mock_settings, mock_create_table, mock_convert_time, mock_load_watermark, mock_token_manager_cls, mock_fetch):
        # Setup Mocks
        mock_redis_instance = mock_redis_cls.from_url.return_value
        mock_lock = mock_redis_instance.lock.return_value
        mock_lock.acquire.return_value = True

        mock_token_manager = mock_token_manager_cls.return_value
        mock_token_manager.has_enough_tokens.return_value = True
        mock_token_manager.tokens = 100
        mock_token_manager.sync_tokens.return_value = None

        mock_load_watermark.return_value = "2025-01-01T00:00:00+00:00"
        mock_convert_time.return_value = 1000000

        # Mock fetch to return empty deals so the loop exits after page 0
        mock_fetch.return_value = ({'deals': {'dr': []}}, 0, 100)

        # Run the function
        print("Running update_recent_deals...")
        simple_task.update_recent_deals()
        print("Finished update_recent_deals.")

        self.assertTrue(mock_fetch.called, "fetch_deals_for_deals should be called")

        args, kwargs = mock_fetch.call_args
        self.assertEqual(kwargs.get('sort_type'), 4, f"Expected sort_type=4, got {kwargs.get('sort_type')}")

        print("SUCCESS: fetch_deals_for_deals was called with sort_type=4")

if __name__ == '__main__':
    unittest.main()
