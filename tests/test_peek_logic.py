import unittest
import sys
import os

# Add repo root to path
sys.path.append(os.getcwd())

from keepa_deals.smart_ingestor import check_peek_viability

class TestPeekViability(unittest.TestCase):
    def setUp(self):
        # Base stats with good price history (to pass other checks)
        # Sell Price = 2000 (Used Avg), Buy Price = 1000 (New Fallback or Used Current)
        # Fees ~ 500, ROI > 20%
        # current: [Amazon, New, Used]
        self.base_stats = {
            'current': [-1, 1000, 1000], # New=1000, Used=1000. Buy = 1000.
            'avg90': [-1, -1, 2000],   # Used Avg = 2000. Sell = 2000.
            'avg365': [-1, -1, 2000],
            'salesRankDrops365': 4     # Default passes
        }

    def test_peek_drops_4_passes(self):
        stats = self.base_stats.copy()
        stats['salesRankDrops365'] = 4
        self.assertTrue(check_peek_viability(stats), "Should pass with 4 drops")

    def test_peek_drops_3_should_pass_target(self):
        stats = self.base_stats.copy()
        stats['salesRankDrops365'] = 3
        # Currently fails (drops < 4). After fix, should pass.
        self.assertTrue(check_peek_viability(stats), "Should pass with 3 drops (Target behavior)")

    def test_peek_drops_1_should_pass_target(self):
        stats = self.base_stats.copy()
        stats['salesRankDrops365'] = 1
        self.assertTrue(check_peek_viability(stats), "Should pass with 1 drop (Target behavior)")

    def test_peek_drops_0_should_fail(self):
        stats = self.base_stats.copy()
        stats['salesRankDrops365'] = 0
        self.assertFalse(check_peek_viability(stats), "Should fail with 0 drops (Dead Inventory)")

    def test_peek_drops_unknown_passes(self):
        stats = self.base_stats.copy()
        stats['salesRankDrops365'] = -1
        self.assertTrue(check_peek_viability(stats), "Should pass with unknown drops (-1)")

if __name__ == '__main__':
    unittest.main()
