import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Ensure local imports work
sys.path.append(os.getcwd())

from keepa_deals.stable_calculations import analyze_sales_performance

class TestStableCalculations(unittest.TestCase):
    def test_zombie_fallback_removed(self):
        """
        Test that analyze_sales_performance returns -1 for peak_price_mode_cents
        when there are no inferred sales, even if monthlySold is high.
        This verifies the removal of the 'Zombie Listing' fallback logic.
        """
        # Mock product data matching a "Zombie Listing"
        product = {
            'asin': 'TESTZOMBIE',
            'monthlySold': 100, # High monthly sold
            'stats': {
                'avg90': [None, None, 40000], # Used price index 2 = 40000 ($400)
            },
            'title': 'Test Zombie Product',
            'categoryTree': [{'name': 'Books'}],
            'binding': 'Paperback',
            'numberOfPages': 200,
            'imagesCSV': 'test.jpg'
        }

        sale_events = [] # No inferred sales

        # Patch _query_xai_for_reasonableness to avoid API calls
        with patch('keepa_deals.stable_calculations._query_xai_for_reasonableness', return_value=True):
            result = analyze_sales_performance(product, sale_events)

        # Assert that the price is -1 (rejected), NOT the $400 fallback
        self.assertEqual(result.get('peak_price_mode_cents'), -1,
                         "Should return -1 for missing sales, not use fallback price.")
        self.assertEqual(result.get('peak_season'), '-')

    def test_normal_calculation(self):
        """
        Test that analyze_sales_performance correctly calculates the mode
        when valid sale events are present.
        """
        product = {
            'asin': 'TESTNORMAL',
            'title': 'Test Normal Product',
            'categoryTree': [{'name': 'Books'}],
            'stats': {'current': [10000, 10000, 10000, 100]} # Amazon price for ceiling check
        }

        # 3 sales in May (Month 5) at $20.00
        sale_events = [
            {'event_timestamp': '2025-05-01', 'inferred_sale_price_cents': 2000},
            {'event_timestamp': '2025-05-02', 'inferred_sale_price_cents': 2000},
            {'event_timestamp': '2025-05-03', 'inferred_sale_price_cents': 2000},
        ]

        with patch('keepa_deals.stable_calculations._query_xai_for_reasonableness', return_value=True):
            result = analyze_sales_performance(product, sale_events)

        self.assertEqual(result.get('peak_price_mode_cents'), 2000)
        self.assertEqual(result.get('peak_season'), 'May')

if __name__ == '__main__':
    unittest.main()
