import unittest
from unittest.mock import patch, MagicMock
import sys
import os

sys.path.append(os.getcwd())

from keepa_deals.stable_calculations import deal_trust

class TestDealTrust(unittest.TestCase):
    def test_deal_trust_no_drops(self):
        # Mock infer_sale_events to return 0 drops
        with patch('keepa_deals.stable_calculations.infer_sale_events', return_value=([], 0)):
            result = deal_trust({})
            self.assertEqual(result, {'Deal Trust': '-'})

    def test_deal_trust_calculation(self):
        # Mock infer_sale_events to return 5 sales and 10 drops
        sales = [1, 2, 3, 4, 5]
        drops = 10
        with patch('keepa_deals.stable_calculations.infer_sale_events', return_value=(sales, drops)):
            result = deal_trust({})
            self.assertEqual(result, {'Deal Trust': '50%'})

if __name__ == '__main__':
    unittest.main()
