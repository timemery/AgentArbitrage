import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add repo root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from keepa_deals import smart_ingestor
from keepa_deals.token_manager import TokenRechargeError

class TestSmartIngestorBatching(unittest.TestCase):
    @patch('keepa_deals.smart_ingestor.redis.Redis')
    @patch('keepa_deals.smart_ingestor.sqlite3')
    @patch('keepa_deals.smart_ingestor.TokenManager')
    @patch('keepa_deals.smart_ingestor.fetch_deals_for_deals')
    @patch('keepa_deals.smart_ingestor.fetch_current_stats_batch')
    @patch('keepa_deals.smart_ingestor.fetch_product_batch')
    @patch('keepa_deals.smart_ingestor.check_peek_viability')
    @patch('keepa_deals.smart_ingestor.load_watermark')
    @patch('keepa_deals.smart_ingestor.save_watermark')
    @patch('keepa_deals.smart_ingestor.create_deals_table_if_not_exists')
    @patch('keepa_deals.smart_ingestor.requeue_stuck_restrictions')
    @patch('keepa_deals.smart_ingestor.get_seller_info_for_single_deal')
    @patch('keepa_deals.smart_ingestor._process_single_deal')
    @patch('keepa_deals.smart_ingestor.celery') # Mock celery
    def test_batching_logic(self, mock_celery, mock_process_single, mock_get_seller, mock_requeue, mock_create_table, mock_save_wm, mock_load_wm,
                            mock_check_peek, mock_fetch_product, mock_fetch_stats, mock_fetch_deals,
                            mock_token_manager_cls, mock_sqlite, mock_redis):

        # Setup Mocks
        mock_load_wm.return_value = "2023-01-01T00:00:00+00:00"
        watermark_mins = smart_ingestor._convert_iso_to_keepa_time("2023-01-01T00:00:00+00:00")

        deals = [{'asin': f'ASIN{i:06d}', 'lastUpdate': watermark_mins + 100 + i} for i in range(100)]

        def side_effect_fetch_deals(page, *args, **kwargs):
            if page == 0:
                return {'deals': {'dr': deals}}, 0, 100
            else:
                return {'deals': {'dr': []}}, 0, 100
        mock_fetch_deals.side_effect = side_effect_fetch_deals

        mock_tm = mock_token_manager_cls.return_value
        mock_tm.REFILL_RATE_PER_MINUTE = 20
        # Ensure should_skip_sync is False for standard test
        mock_tm.should_skip_sync.return_value = False

        mock_conn = mock_sqlite.connect.return_value
        mock_cursor = mock_conn.cursor.return_value
        mock_cursor.fetchall.return_value = []

        mock_check_peek.return_value = True

        def side_effect_peek(api_key, asins, days, offers):
            return {'products': [{'asin': a, 'stats': {}} for a in asins]}, None, 0, 100
        mock_fetch_stats.side_effect = side_effect_peek

        def side_effect_commit(api_key, asins, days=365, offers=20, rating=1, history=0):
             return {'products': [{'asin': a} for a in asins]}, None, 0, 100
        mock_fetch_product.side_effect = side_effect_commit

        # Mock processing to succeed
        mock_process_single.return_value = {'ASIN': 'TEST', 'Title': 'Mock Title'}
        mock_get_seller.return_value = {}

        # Run
        smart_ingestor.run()

        # Assertions

        # 1. Verify Peek Batch Size (Should be 50)
        self.assertEqual(mock_fetch_stats.call_count, 2)

        call_args_list_stats = mock_fetch_stats.call_args_list
        args1, kwargs1 = call_args_list_stats[0]
        self.assertEqual(len(args1[1]), 50, "Peek batch 1 should have 50 ASINs")
        self.assertEqual(kwargs1.get('offers'), 20, "Peek offers should be 20")

        # 2. Verify Commit Batch Size (Should be 5)
        self.assertEqual(mock_fetch_product.call_count, 20)

        call_args_list_product = mock_fetch_product.call_args_list
        args_prod1, _ = call_args_list_product[0]
        self.assertEqual(len(args_prod1[1]), 5, "Commit batch should have 5 ASINs")

        # 3. Verify Upsert Count
        self.assertEqual(mock_process_single.call_count, 100)

        print("Batching Test passed!")

    @patch('keepa_deals.smart_ingestor.redis.Redis')
    @patch('keepa_deals.smart_ingestor.TokenManager')
    def test_recharge_exception_handling(self, mock_token_manager_cls, mock_redis):
        # Mock TokenManager to raise exception immediately
        mock_tm = mock_token_manager_cls.return_value
        mock_tm.request_permission_for_call.side_effect = TokenRechargeError("Test Recharge")
        # Ensure should_skip_sync is False so we proceed to request_permission
        mock_tm.should_skip_sync.return_value = False

        # Mock Redis lock
        mock_lock = MagicMock()
        mock_redis.from_url.return_value.lock.return_value = mock_lock
        mock_lock.acquire.return_value = True
        mock_lock.locked.return_value = True # Ensure release is called

        # Run
        smart_ingestor.run()

        # Verify lock released
        mock_lock.release.assert_called_once()
        print("Recharge Exception Test passed!")

    @patch('keepa_deals.smart_ingestor.redis.Redis')
    @patch('keepa_deals.smart_ingestor.TokenManager')
    def test_skip_sync_logic(self, mock_token_manager_cls, mock_redis):
        # Mock TokenManager to indicate we should skip sync
        mock_tm = mock_token_manager_cls.return_value
        mock_tm.should_skip_sync.return_value = True
        # Also ensure request_permission eventually raises the error (since we are recharging)
        mock_tm.request_permission_for_call.side_effect = TokenRechargeError("Recharge needed")

        # Mock Redis lock
        mock_lock = MagicMock()
        mock_redis.from_url.return_value.lock.return_value = mock_lock
        mock_lock.acquire.return_value = True
        mock_lock.locked.return_value = True

        # Run
        smart_ingestor.run()

        # Assert sync_tokens was NOT called
        mock_tm.sync_tokens.assert_not_called()

        # Assert lock released
        mock_lock.release.assert_called_once()

        print("Skip Sync Test passed!")

if __name__ == '__main__':
    unittest.main()
