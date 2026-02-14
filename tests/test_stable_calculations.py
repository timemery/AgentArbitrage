import unittest
from unittest.mock import patch, MagicMock
import sys
import os
from datetime import datetime

# Ensure local imports work
sys.path.append(os.getcwd())

from keepa_deals.stable_calculations import analyze_sales_performance

class TestStableCalculations(unittest.TestCase):
    def test_zombie_fallback_works(self):
        """
        Test that analyze_sales_performance correctly uses the Silver Standard Fallback (avg365)
        when inferred sales are missing, provided Keepa stats are available.
        """
        # Mock product data with valid stats but no sales
        product = {
            'asin': 'TESTFALLBACK',
            'monthlySold': 0, # Low/Unknown
            'stats': {
                'current': [50000, 50000, 50000, 50000], # Amazon, New, Used, Rank (Index 3)
                'avg90': [None, None, 40000, 100000], # Used price index 2 = 40000 ($400)
                'avg365': [None, None, 35000, 150000], # Used price index 2 = 35000 ($350)
            },
            'title': 'Test Fallback Product',
            'categoryTree': [{'name': 'Books'}],
            'binding': 'Paperback',
            'numberOfPages': 200,
            'imagesCSV': 'test.jpg'
        }

        sale_events = [] # No inferred sales

        # Patch _query_xai_for_reasonableness to confirm it is called (for now) and returns True
        with patch('keepa_deals.stable_calculations._query_xai_for_reasonableness', return_value=True):
            result = analyze_sales_performance(product, sale_events)

        # Assert that the price is the fallback price (Max of avg90/avg365 = 40000)
        self.assertEqual(result.get('peak_price_mode_cents'), 40000,
                         "Should return fallback price ($400) when stats are present.")
        self.assertEqual(result.get('price_source'), 'Keepa Stats Fallback')
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
            {'event_timestamp': datetime(2025, 5, 1), 'inferred_sale_price_cents': 2000},
            {'event_timestamp': datetime(2025, 5, 2), 'inferred_sale_price_cents': 2000},
            {'event_timestamp': datetime(2025, 5, 3), 'inferred_sale_price_cents': 2000},
        ]

        with patch('keepa_deals.stable_calculations._query_xai_for_reasonableness', return_value=True):
            result = analyze_sales_performance(product, sale_events)

        self.assertEqual(result.get('peak_price_mode_cents'), 2000)
        self.assertEqual(result.get('peak_season'), 'May')

if __name__ == '__main__':
    unittest.main()
