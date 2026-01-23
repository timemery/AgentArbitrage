import unittest
import sys
import os
from datetime import datetime, timedelta

# Add root to path
sys.path.append(os.getcwd())

from keepa_deals.stable_calculations import calculate_long_term_trend, calculate_3yr_avg

class TestStableCalculationsTrend(unittest.TestCase):
    def test_calculate_long_term_trend_up(self):
        # Create sales events trending UP
        now = datetime.now()
        sale_events = [
            {'event_timestamp': now - timedelta(days=1000), 'inferred_sale_price_cents': 1000},
            {'event_timestamp': now - timedelta(days=500), 'inferred_sale_price_cents': 1500},
            {'event_timestamp': now, 'inferred_sale_price_cents': 2000}
        ]
        trend = calculate_long_term_trend(sale_events)
        self.assertIn("UP", trend)

    def test_calculate_long_term_trend_down(self):
        # Create sales events trending DOWN
        now = datetime.now()
        sale_events = [
            {'event_timestamp': now - timedelta(days=1000), 'inferred_sale_price_cents': 2000},
            {'event_timestamp': now - timedelta(days=500), 'inferred_sale_price_cents': 1500},
            {'event_timestamp': now, 'inferred_sale_price_cents': 1000}
        ]
        trend = calculate_long_term_trend(sale_events)
        self.assertIn("DOWN", trend)

    def test_calculate_long_term_trend_flat(self):
        # Create sales events trending FLAT
        now = datetime.now()
        sale_events = [
            {'event_timestamp': now - timedelta(days=1000), 'inferred_sale_price_cents': 1000},
            {'event_timestamp': now - timedelta(days=500), 'inferred_sale_price_cents': 1010},
            {'event_timestamp': now, 'inferred_sale_price_cents': 990}
        ]
        trend = calculate_long_term_trend(sale_events)
        self.assertIn("FLAT", trend)

    def test_calculate_3yr_avg(self):
        sale_events = [
            {'inferred_sale_price_cents': 1000},
            {'inferred_sale_price_cents': 2000},
            {'inferred_sale_price_cents': 3000}
        ]
        avg = calculate_3yr_avg(sale_events)
        self.assertEqual(avg, 2000)

if __name__ == '__main__':
    unittest.main()
