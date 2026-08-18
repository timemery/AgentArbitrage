import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals.processing import _process_lightweight_update

class TestSellerNameLogic(unittest.TestCase):

    @patch('keepa_deals.processing.get_used_product_info')
    @patch('keepa_deals.stable_products.sales_rank_current')
    @patch('keepa_deals.stable_products.amazon_current')
    @patch('keepa_deals.stable_products.sales_rank_drops_last_30_days')
    @patch('keepa_deals.new_analytics.get_offer_count_trend')
    @patch('keepa_deals.new_analytics.get_offer_count_trend_180')
    @patch('keepa_deals.new_analytics.get_offer_count_trend_365')
    @patch('keepa_deals.stable_deals.last_price_change')
    @patch('keepa_deals.business_calculations.calculate_all_in_cost')
    @patch('keepa_deals.business_calculations.calculate_profit_and_margin')
    @patch('keepa_deals.business_calculations.calculate_min_listing_price')
    @patch('keepa_deals.business_calculations.load_settings')
    def test_seller_name_preservation(self, mock_load_settings, mock_min_list, mock_prof, mock_cost,
                                      mock_lpc, mock_off365, mock_off180, mock_off, mock_drops,
                                      mock_amz, mock_sr, mock_get_used_info):

        # Setup common mocks
        mock_load_settings.return_value = {}
        mock_get_used_info.return_value = (1000, 'NEW_SELLER_ID', False, 2) # Price 10.00, ID, FBA, Code

        mock_sr.return_value = {}
        mock_amz.return_value = {}
        mock_drops.return_value = {}
        mock_off.return_value = {}
        mock_off180.return_value = {}
        mock_off365.return_value = {}
        mock_lpc.return_value = {}

        mock_cost.return_value = 5.00
        mock_prof.return_value = {'profit': 5.00, 'margin': 50.0}
        mock_min_list.return_value = 8.00

        product_data = {'asin': 'TESTASIN'}

        # Case 1: ID Matches -> Name Preserved
        # NOTE: keys here are the sanitized DB column names, because production always
        # passes dict(sqlite3.Row) from 'SELECT * FROM deals' (smart_ingestor.py:249
        # and :467). The previous fixture used headers.json display names ('Seller ID',
        # 'List at'), which no caller ever supplies - so this test passed while the
        # production path silently failed every lookup.
        existing_row_1 = {
            'ASIN': 'TESTASIN',
            'Seller': 'Old Seller Name',
            'Seller_ID': 'NEW_SELLER_ID', # Matches the mocked new ID
            'List_at': '$20.00',
            '1yr_Avg': '$15.00'
        }

        result_1 = _process_lightweight_update(existing_row_1, product_data)
        self.assertEqual(result_1['Seller'], 'Old Seller Name', "Seller Name should be preserved when ID matches")
        self.assertEqual(result_1['Seller_ID'], 'NEW_SELLER_ID')

        # Case 2: ID Differs -> Name Overwritten
        existing_row_2 = {
            'ASIN': 'TESTASIN',
            'Seller': 'Old Seller Name',
            'Seller_ID': 'OLD_SELLER_ID', # Differs
            'List_at': '$20.00'
        }

        result_2 = _process_lightweight_update(existing_row_2, product_data)
        self.assertEqual(result_2['Seller'], 'NEW_SELLER_ID', "Seller Name should be overwritten when ID differs")
        self.assertEqual(result_2['Seller_ID'], 'NEW_SELLER_ID')

        # Case 3: Old ID Missing -> Name Overwritten
        existing_row_3 = {
            'ASIN': 'TESTASIN',
            'Seller': 'Old Seller Name',
            # No Seller_ID
            'List_at': '$20.00'
        }

        result_3 = _process_lightweight_update(existing_row_3, product_data)
        self.assertEqual(result_3['Seller'], 'NEW_SELLER_ID', "Seller Name should be overwritten when old ID is missing")
        self.assertEqual(result_3['Seller_ID'], 'NEW_SELLER_ID')

if __name__ == '__main__':
    unittest.main()
