import unittest
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from keepa_deals.stable_calculations import analyze_sales_performance
from keepa_deals.new_analytics import get_1yr_avg_sale_price

class TestFallbackLogic(unittest.TestCase):
    def test_analyze_sales_performance_fallback(self):
        # Scenario: No sale events, no Used stats. Only New/Amazon stats.
        product = {
            'asin': 'TEST001',
            'csv': [], # No inferred sales possible
            'stats': {
                'avg90': [1000, 2000, -1, -1], # Amazon=1000, New=2000, Used=-1
                'avg365': [1200, 2200, -1, -1],
                'current': [1000, 2000, -1, -1] # Just for context
            }
        }

        # Should now return a valid result using fallback
        result = analyze_sales_performance(product, [])

        self.assertNotEqual(result['peak_price_mode_cents'], -1)
        self.assertEqual(result['price_source'], 'Keepa Stats Fallback')

        # Max of candidates:
        # avg90[0]=1000, avg90[1]=2000
        # avg365[0]=1200, avg365[1]=2200
        # Max is 2200.
        # But wait, Amazon Ceiling Logic applies.
        # Amazon current (from stats.current[0]) is 1000. Ceiling is 1000 * 0.90 = 900.
        # So it should be capped at 900.

        expected_capped = 900.0

        self.assertEqual(result['peak_price_mode_cents'], expected_capped)

    def test_get_1yr_avg_sale_price_fallback(self):
        # Scenario: No sale events, no Used stats. Only New/Amazon stats.
        product = {
            'asin': 'TEST002',
            'csv': [],
            'stats': {
                'avg365': [1500, 2500, -1, -1] # Amazon=1500, New=2500
            }
        }

        result = get_1yr_avg_sale_price(product)

        self.assertIsNotNone(result)
        self.assertEqual(result['price_source'], 'Keepa Stats Fallback')
        # Max is 2500. Result is in dollars: 25.00
        self.assertEqual(result['1yr. Avg.'], 25.00)

if __name__ == '__main__':
    unittest.main()
