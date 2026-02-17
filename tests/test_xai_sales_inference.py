import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Add repo root to path
sys.path.append(os.getcwd())

from keepa_deals.xai_sales_inference import format_history_for_xai, infer_sales_with_xai

# Keepa epoch is minutes from 2011-01-01
KEEPA_EPOCH = datetime(2011, 1, 1)

def datetime_to_keepa(dt):
    delta = dt - KEEPA_EPOCH
    return int(delta.total_seconds() / 60)

class TestXaiSalesInference(unittest.TestCase):
    def setUp(self):
        # Create a basic product structure
        now = datetime.now()
        start_time = now - timedelta(days=90)

        # Base arrays
        rank_hist = []
        price_hist = []
        offer_hist = []

        # Initial State
        current_time = start_time
        rank_hist.extend([datetime_to_keepa(current_time), 500000])
        price_hist.extend([datetime_to_keepa(current_time), 2500])
        offer_hist.extend([datetime_to_keepa(current_time), 5])

        # Event at day 10
        event_time = start_time + timedelta(days=10)
        offer_hist.extend([datetime_to_keepa(event_time), 4])

        rank_time = event_time + timedelta(hours=2)
        rank_hist.extend([datetime_to_keepa(rank_time), 100000])

        self.product = {
            'asin': 'TESTASIN123',
            'title': 'Test Product',
            'categoryTree': [{'name': 'Books'}],
            'csv': [
                None, None,
                price_hist, # 2
                rank_hist, # 3
                None, None, None, None, None, None, None, None,
                offer_hist # 12
            ],
            'stats': {'current': [None, None, None, 100000]} # Rank 100k
        }

    def test_format_history_for_xai(self):
        # Should return a formatted string
        text = format_history_for_xai(self.product, days=100)
        self.assertIsNotNone(text)
        self.assertIn("Time | Rank | Used Price | Offers", text)
        self.assertIn("$25.00", text)
        self.assertIn("500000", text)
        self.assertIn("100000", text) # The drop

        # Check if initial state is captured (500k, 5 offers)
        # It might be in the first row
        self.assertTrue(any("500000" in line and "5" in line for line in text.splitlines()))

    @patch('keepa_deals.xai_sales_inference.query_xai_sales_inference')
    def test_infer_sales_with_xai_success(self, mock_query):
        # Mock successful XAI response
        mock_query.return_value = {
            "sales_found": 1,
            "events": [{"date": "2025-01-01", "price": 25.00}],
            "estimated_market_price": 25.00,
            "confidence": "High",
            "reasoning": "Test reasoning"
        }

        sales = infer_sales_with_xai(self.product)
        self.assertIsNotNone(sales)
        self.assertEqual(len(sales), 1)
        self.assertEqual(sales[0]['inferred_sale_price_cents'], 2500)
        # Check datetime
        expected_dt = datetime(2025, 1, 1, 12, 0) # Noon
        self.assertEqual(sales[0]['event_timestamp'], expected_dt)

    @patch('keepa_deals.xai_sales_inference.query_xai_sales_inference')
    def test_infer_sales_with_xai_low_confidence(self, mock_query):
        # Mock low confidence
        mock_query.return_value = {
            "sales_found": 0,
            "events": [],
            "confidence": "Low",
            "reasoning": "Not sure"
        }

        sales = infer_sales_with_xai(self.product)
        self.assertIsNone(sales)

    @patch('keepa_deals.xai_sales_inference.query_xai_sales_inference')
    def test_infer_sales_with_xai_high_rank_skip(self, mock_query):
        # Set Rank to 3M
        self.product['stats']['current'][3] = 3000000

        sales = infer_sales_with_xai(self.product)
        self.assertIsNone(sales)
        mock_query.assert_not_called()

if __name__ == '__main__':
    unittest.main()
