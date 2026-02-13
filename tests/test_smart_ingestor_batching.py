import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add repo root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from keepa_deals import smart_ingestor

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

        print("Test passed!")

if __name__ == '__main__':
    unittest.main()
