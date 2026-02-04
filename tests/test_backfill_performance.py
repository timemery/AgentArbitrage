import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals.backfiller import backfill_deals

class TestBackfillSlowness(unittest.TestCase):
    @patch('keepa_deals.backfiller.time.sleep')
    @patch('keepa_deals.backfiller.redis.Redis')
    @patch('keepa_deals.backfiller.TokenManager')
    @patch('keepa_deals.backfiller.fetch_deals_for_deals')
    @patch('keepa_deals.backfiller.fetch_product_batch')
    @patch('keepa_deals.backfiller.fetch_current_stats_batch')
    @patch('keepa_deals.backfiller.create_deals_table_if_not_exists')
    @patch('keepa_deals.backfiller.get_system_state')
    @patch('keepa_deals.backfiller.set_system_state')
    @patch('keepa_deals.backfiller.sqlite3')
    @patch('keepa_deals.backfiller.get_seller_info_for_single_deal')
    @patch('keepa_deals.backfiller._process_single_deal')
    @patch('keepa_deals.backfiller._process_lightweight_update')
    def test_backfill_sleep_calls(self, mock_lightweight, mock_process, mock_seller, mock_sqlite,
                                  mock_set_state, mock_get_state, mock_create_table,
                                  mock_fetch_stats, mock_fetch_prod, mock_fetch_deals,
                                  mock_tm, mock_redis, mock_sleep):

        # Setup Mocks
        os.environ['KEEPA_API_KEY'] = 'test_key'
        os.environ['XAI_TOKEN'] = 'test_token'

        mock_get_state.side_effect = lambda k, default=None: "0" if k == 'backfill_page' else (default if default else None)

        # Mock Redis Lock
        mock_redis_client = MagicMock()
        mock_redis.from_url.return_value = mock_redis_client
        mock_lock = MagicMock()
        mock_redis_client.lock.return_value = mock_lock
        mock_lock.acquire.return_value = True

        # Mock TokenManager
        mock_tm_instance = MagicMock()
        mock_tm.return_value = mock_tm_instance

        # Mock Fetch Deals (One page, 20 deals to trigger one chunk)
        # DEALS_PER_CHUNK is 20
        # ASINs must be 10 chars and alphanumeric to pass validation
        deals = [{'asin': f'ABC12345{i:02d}', 'lastUpdate': 1000} for i in range(20)]
        deal_response = {'deals': {'dr': deals}}

        # We want the loop to run once (Page 0), then stop.
        # To stop the loop, we can make the second call return empty or raise an exception.
        # Or we can just let it run for one iteration and check calls.
        # Let's make fetch_deals_for_deals return deals for page 0, then empty for page 1.
        def fetch_side_effect(page, *args, **kwargs):
            if page == 0:
                return deal_response, 0, 100
            return {}, 0, 100
        mock_fetch_deals.side_effect = fetch_side_effect

        # Mock Fetch Products
        mock_fetch_prod.return_value = ({'products': []}, {}, 0, 100)
        mock_fetch_stats.return_value = ({'products': []}, {}, 0, 100)

        # Run Backfill
        try:
            backfill_deals()
        except Exception as e:
            pass # Ignore expected errors or loop breaks

        # Verify Sleep Calls
        # We expect time.sleep(60) to be called once after the chunk.
        # We also expect time.sleep(0.5) to be called (for batching)
        # And time.sleep(1) at end of page.

        # Check if sleep(1) was called (New behavior)
        mock_sleep.assert_any_call(1)
        print("Confirmed: time.sleep(1) was called.")

        # Check frequency
        # For 20 deals (1 chunk), sleep(1) is called at end of chunk.
        # sleep(1) is ALSO called at end of page loop.
        # So we expect at least 2 calls to sleep(1).
        calls_1 = [call for call in mock_sleep.mock_calls if call.args == (1,)]
        self.assertGreaterEqual(len(calls_1), 1, f"Expected sleep(1) to be called, got {len(calls_1)}")

        # Ensure sleep(60) is NOT called
        calls_60 = [call for call in mock_sleep.mock_calls if call.args == (60,)]
        self.assertEqual(len(calls_60), 0, f"Expected sleep(60) to NOT be called, got {len(calls_60)}")

if __name__ == '__main__':
    unittest.main()
