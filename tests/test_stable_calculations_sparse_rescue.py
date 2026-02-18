
import unittest
from unittest.mock import MagicMock, patch
import sys
import os
import numpy as np

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals.stable_calculations import analyze_sales_performance

class TestSparseDataFallback(unittest.TestCase):

    def test_sparse_sales_rescue(self):
        """
        Test that deals with 1-2 sales but NO Keepa stats are Rescued using sparse sales median.
        """
        # Mock product with NO stats (using -1 to simulate missing but safe data)
        product = {
            'asin': 'TEST_ASIN_001',
            'title': 'Test Book',
            'stats': {
                'avg90': [-1] * 30,
                'avg365': [-1] * 30,
                'current': [-1] * 30
            }
        }

        # Mock 2 sale events
        sale_events = [
            {'event_timestamp': '2025-01-01', 'inferred_sale_price_cents': 2000},
            {'event_timestamp': '2025-02-01', 'inferred_sale_price_cents': 3000}
        ]

        # Analyze
        result = analyze_sales_performance(product, sale_events)

        print(f"\nResult for sparse sales rescue: {result}")

        # Should use median of [2000, 3000] = 2500
        self.assertEqual(result['peak_price_mode_cents'], 2500, "Should use median of inferred sales")
        self.assertEqual(result['price_source'], 'Inferred Sales (Sparse)')

    def test_missing_stats_type_error_fix(self):
        """
        Test that missing stats (None) do not cause a TypeError.
        Previously, avg90[21] > 0 would crash if avg90[21] was None.
        """
        product = {
            'asin': 'TEST_ASIN_002',
            'title': 'Crash Test Dummy',
            'stats': {
                'avg90': [None] * 30, # All None, including index 21
                'avg365': [None] * 30,
                'current': [None] * 30
            }
        }
        sale_events = [{'event_timestamp': '2025-01-01', 'inferred_sale_price_cents': 1500}]

        # This should NOT raise TypeError and should return the rescued price
        try:
            result = analyze_sales_performance(product, sale_events)
        except TypeError as e:
            self.fail(f"analyze_sales_performance raised TypeError: {e}")

        self.assertEqual(result['peak_price_mode_cents'], 1500)
        self.assertEqual(result['price_source'], 'Inferred Sales (Sparse)')

    def test_collectible_fallback(self):
        """
        Test that Collectible conditions are picked up if Used conditions are missing.
        """
        # Mock product with ONLY Collectible stats
        # Indices 2, 19-22 (Used) are -1 or None
        # Indices 23-26 (Collectible) have data
        avg90 = [-1] * 30
        avg90[25] = 5000  # Collectible - Good

        product = {
            'asin': 'TEST_ASIN_003',
            'title': 'Collectible Book',
            'stats': {
                'avg90': avg90,
                'avg365': [-1] * 30,
                'current': [-1] * 30
            }
        }
        sale_events = [] # 0 sale events forces fallback

        result = analyze_sales_performance(product, sale_events)

        print(f"\nResult for Collectible fallback: {result}")

        self.assertEqual(result['peak_price_mode_cents'], 5000, "Should use Collectible price")
        self.assertEqual(result['price_source'], 'Keepa Stats Fallback')

if __name__ == '__main__':
    unittest.main()
