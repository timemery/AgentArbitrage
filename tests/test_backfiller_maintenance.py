import unittest
from unittest.mock import MagicMock, patch, ANY
import sys
import os

# Add root to path
sys.path.append(os.getcwd())

from keepa_deals import backfiller

class TestBackfillLimitV2(unittest.TestCase):

    @patch('keepa_deals.backfiller.get_system_state')
    @patch('keepa_deals.backfiller.get_deal_count')
    @patch('keepa_deals.backfiller.fetch_deals_for_deals')
    @patch('keepa_deals.backfiller.fetch_product_batch')
    @patch('keepa_deals.backfiller.TokenManager')
    @patch('keepa_deals.backfiller.redis.Redis')
    @patch('keepa_deals.backfiller.create_deals_table_if_not_exists')
    @patch('keepa_deals.backfiller.filter_existing_asins')  # Mocking the new utility
    def test_maintenance_mode(self, mock_filter_existing, mock_create_table, mock_redis, mock_tm, mock_fetch_products, mock_fetch_deals, mock_get_count, mock_get_state):
        """
        Verifies that when limit is reached, it switches to Maintenance Mode:
        - Cycles through pages
        - Checks DB for existing ASINs using filter_existing_asins
        - ONLY processes existing ASINs
        - Skips New ASINs
        """
        # --- Setup ---

        # 1. State: Limit Enabled (100), Current Count (150) -> Over Limit
        mock_get_state.side_effect = lambda key, default=None: 'true' if key == 'backfill_limit_enabled' else ('100' if key == 'backfill_limit_count' else default)
        mock_get_count.return_value = 150

        # 2. Redis Lock Mock
        mock_redis_instance = MagicMock()
        mock_lock = MagicMock()
        mock_lock.acquire.return_value = True
        mock_redis_instance.lock.return_value = mock_lock
        mock_redis.from_url.return_value = mock_redis_instance

        # 3. Mock Fetch Deals (Return 1 Page with 3 deals)
        # We must use VALID ASINs (10 char alphanumeric) because Keepa API validates them now
        deals_payload = {'dr': [
            {'asin': 'EXISTING01', 'lastUpdate': 1000},
            {'asin': 'NEWDEAL002', 'lastUpdate': 1000},
            {'asin': 'EXISTING03', 'lastUpdate': 1000}
        ]}
        mock_fetch_deals.side_effect = [
            ({'deals': deals_payload}, 0, 0), # Page 0
            (None, 0, 0)                      # Page 1 (End)
        ]

        # 4. Mock DB "Existing Check"
        # Return only EXISTING01 and EXISTING03
        mock_filter_existing.return_value = {'EXISTING01', 'EXISTING03'}

        # 5. Mock Product Batch (Should only be called with Filtered list)
        mock_fetch_products.return_value = ({'products': []}, {}, 0, 0)

        # --- Execute ---
        backfiller.backfill_deals()

        # --- Assertions ---

        # 1. Verify DB Check was performed
        mock_filter_existing.assert_called()
        print("\n[TEST] Verified: filter_existing_asins called.")

        # 2. Verify fetch_product_batch called with ONLY existing ASINs
        # Expecting ['EXISTING01', 'EXISTING03']
        mock_fetch_products.assert_called_once()
        called_asins = mock_fetch_products.call_args[0][1]

        self.assertIn('EXISTING01', called_asins)
        self.assertIn('EXISTING03', called_asins)
        self.assertNotIn('NEWDEAL002', called_asins)

        print(f"[TEST] fetch_product_batch called with: {called_asins}")
        print("[TEST] Verified: NEWDEAL002 was filtered out in Maintenance Mode.")

if __name__ == '__main__':
    unittest.main()
