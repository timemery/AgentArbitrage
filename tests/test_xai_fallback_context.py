import unittest
from unittest.mock import patch
import sys
import os

# Ensure local imports work
sys.path.append(os.getcwd())

from keepa_deals.stable_calculations import analyze_sales_performance

class TestXAIFallbackContext(unittest.TestCase):
    def test_fallback_success_without_xai(self):
        """
        Verifies that analyze_sales_performance correctly uses the fallback price (avg365)
        when inferred sales are missing, but valid stats are present.
        """
        product = {
            'asin': 'TESTFALLBACK',
            'title': 'Test Fallback Book',
            'categoryTree': [{'name': 'Books'}],
            'stats': {
                'current': [5000, 5000, 5000, 5000],
                'avg90': [None, None, 4000, 100000], # Used=4000 ($40)
                'avg365': [None, None, 3500, 150000], # Used=3500 ($35)
            }
        }
        sale_events = []

        # We mock XAI to verify that it is SKIPPED for fallback cases
        with patch('keepa_deals.stable_calculations._query_xai_for_reasonableness', return_value=True) as mock_xai:
            result = analyze_sales_performance(product, sale_events)

            # Check Result
            self.assertEqual(result.get('peak_price_mode_cents'), 4000) # Max of avg90 ($40) and avg365 ($35)
            self.assertEqual(result.get('price_source'), 'Keepa Stats Fallback')

            # Check Context Passed to XAI - SHOULD BE NONE
            mock_xai.assert_not_called()

if __name__ == '__main__':
    unittest.main()
