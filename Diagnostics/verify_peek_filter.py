
import os
import sys
import logging
import unittest

# Add repo root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals.backfiller import check_peek_viability

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestPeekFilter(unittest.TestCase):

    def test_good_deal(self):
        # Sell: $264, Buy: $42 (Like our test ASIN)
        stats = {
            'current': [-1, -1, 4250],
            'avg90': [-1, -1, 26466]
        }
        self.assertTrue(check_peek_viability(stats), "Should ACCEPT high ROI deal")

    def test_bad_spread(self):
        # Sell: $20, Buy: $25
        stats = {
            'current': [-1, -1, 2500],
            'avg90': [-1, -1, 2000]
        }
        self.assertFalse(check_peek_viability(stats), "Should REJECT negative spread")

    def test_cheap_deal(self):
        # Sell: $10, Buy: $5 (ROI looks good, but absolute profit is killed by fees)
        stats = {
            'current': [-1, -1, 500],
            'avg90': [-1, -1, 1000]
        }
        self.assertFalse(check_peek_viability(stats), "Should REJECT cheap deal (<$12)")

    def test_low_roi(self):
        # Sell: $100, Buy: $90 (ROI = 11%)
        stats = {
            'current': [-1, -1, 9000],
            'avg90': [-1, -1, 10000]
        }
        self.assertFalse(check_peek_viability(stats), "Should REJECT low ROI (<20%)")

    def test_missing_buy_price(self):
        stats = {
            'current': [-1, -1, -1],
            'avg90': [-1, -1, 10000]
        }
        self.assertFalse(check_peek_viability(stats), "Should REJECT missing buy price")

    def test_missing_sell_history(self):
        stats = {
            'current': [-1, -1, 5000],
            'avg90': [-1, -1, -1]
        }
        self.assertFalse(check_peek_viability(stats), "Should REJECT missing sell history")

if __name__ == '__main__':
    unittest.main()
