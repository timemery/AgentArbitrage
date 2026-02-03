import unittest
import sys
import os
import logging
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Add repository root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals.new_analytics import get_1yr_avg_sale_price
from keepa_deals.stable_calculations import infer_sale_events, KEEPA_EPOCH

class Test1YrAvgLogic(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL) # Silence logs during test

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def _create_mock_product(self, history_days=365, sales_count=5, sales_age_days=None):
        """
        Creates a mock product with synthetic CSV history.
        If sales_age_days is provided, sales are injected that many days ago.
        Otherwise distributed evenly.
        """
        now = datetime.now()
        timestamps = []
        ranks = []
        new_prices = []
        used_prices = []
        new_counts = []
        used_counts = []

        # Generate base timeline (hourly points)
        for i in range(history_days * 24):
            ts = now - timedelta(hours=i)
            keepa_min = int((ts - KEEPA_EPOCH).total_seconds() / 60)

            timestamps.append(keepa_min)
            ranks.append(100000) # Baseline rank
            new_prices.append(2000) # $20.00
            used_prices.append(1500) # $15.00
            new_counts.append(5)
            used_counts.append(5)

        # Reverse to be chronological (Old -> New)
        timestamps.reverse()
        ranks.reverse()
        new_prices.reverse()
        used_prices.reverse()
        new_counts.reverse()
        used_counts.reverse()

        # Helper to find index closest to a date
        def find_idx_for_date(days_ago):
            target_ts = now - timedelta(days=days_ago)
            target_min = int((target_ts - KEEPA_EPOCH).total_seconds() / 60)
            # Timestamps are sorted ascending
            for idx, ts in enumerate(timestamps):
                if ts >= target_min:
                    return idx
            return len(timestamps) - 1

        if sales_count > 0:
            if sales_age_days:
                # Inject all sales around this age
                start_idx = find_idx_for_date(sales_age_days)
                for i in range(sales_count):
                    idx = start_idx + (i * 24) # Spread out by a day
                    if idx < len(timestamps):
                        used_counts[idx] = 4
                        if idx + 1 < len(ranks):
                            ranks[idx+1] = 50000
            else:
                 # Distribute evenly
                 interval = len(timestamps) // (sales_count + 1)
                 for i in range(1, sales_count + 1):
                    idx = i * interval
                    used_counts[idx] = 4
                    if idx + 1 < len(ranks):
                        ranks[idx+1] = 50000

        def to_csv_format(times, vals):
            arr = []
            for t, v in zip(times, vals):
                arr.append(t)
                arr.append(v)
            return arr

        csv_data = [None] * 13
        csv_data[1] = to_csv_format(timestamps, new_prices) # New
        csv_data[2] = to_csv_format(timestamps, used_prices) # Used
        csv_data[3] = to_csv_format(timestamps, ranks) # Rank
        csv_data[11] = to_csv_format(timestamps, new_counts) # New Count
        csv_data[12] = to_csv_format(timestamps, used_counts) # Used Count

        return {
            'asin': 'TEST123456',
            'csv': csv_data
        }

    def test_sufficient_data(self):
        # Create product with 5 sales in last year
        product = self._create_mock_product(history_days=365, sales_count=5)

        # Verify inference works
        events, _ = infer_sale_events(product)
        self.assertGreater(len(events), 0, "Should infer sales")

        # Verify 1yr Avg
        result = get_1yr_avg_sale_price(product)
        self.assertIsNotNone(result)
        self.assertIn('1yr. Avg.', result)
        self.assertGreater(result['1yr. Avg.'], 0)

    def test_insufficient_data_no_sales(self):
        # Product with history but NO sales
        product = self._create_mock_product(history_days=365, sales_count=0)

        result = get_1yr_avg_sale_price(product)
        self.assertIsNone(result, "Should return None for 0 sales")

    def test_insufficient_data_old_sales(self):
        # Product with sales, but OLDER than 1 year (e.g. 400 days ago)
        # We need history > 400 days to contain them
        product = self._create_mock_product(history_days=500, sales_count=5, sales_age_days=400)

        # Verify inference finds them (inference window is 3 years)
        events, _ = infer_sale_events(product)
        self.assertGreater(len(events), 0, "Should infer old sales")

        # Verify 1yr Avg rejects them (because they are old)
        result = get_1yr_avg_sale_price(product)
        # Assuming the function returns None if no sales IN LAST 365 DAYS
        # Let's verify new_analytics.py logic:
        # df_last_year = df[df['event_timestamp'] >= one_year_ago]
        # if len(df_last_year) < 1: return None

        self.assertIsNone(result, "Should return None because all sales are > 365 days old")

if __name__ == '__main__':
    unittest.main()
