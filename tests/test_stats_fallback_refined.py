import unittest
from datetime import datetime, timedelta
from keepa_deals.seller_info import get_used_product_info

class TestStatsFallbackRefined(unittest.TestCase):

    def test_stats_fallback_used_priority(self):
        # Product with no offers but valid stats for BOTH Used and New
        product = {
            "asin": "TEST1",
            "offers": [],
            "stats": {
                # [Amazon, New, Used]
                "current": [-1, 5000, 2500, -1]
            }
        }

        price, seller, is_fba, condition = get_used_product_info(product)

        # Should pick Used (2500) over New (5000)
        self.assertEqual(price, 2500)
        self.assertEqual(condition, 4) # Used - Good

    def test_stats_fallback_new_when_used_missing(self):
        # Product with no offers, Used is missing (-1), but New exists
        product = {
            "asin": "TEST2",
            "offers": [],
            "stats": {
                # [Amazon, New, Used]
                "current": [-1, 4000, -1, -1]
            }
        }

        price, seller, is_fba, condition = get_used_product_info(product)

        # Should pick New (4000) because Used is missing
        self.assertEqual(price, 4000)
        self.assertEqual(condition, 0) # New, unopened

    def test_stats_fallback_new_when_used_zero(self):
        # Edge case: Used is 0 (invalid), New exists
        product = {
            "asin": "TEST3",
            "offers": [],
            "stats": {
                "current": [-1, 4500, 0, -1]
            }
        }

        price, seller, is_fba, condition = get_used_product_info(product)

        self.assertEqual(price, 4500)
        self.assertEqual(condition, 0)

    def test_offers_still_priority(self):
        # Fresh offer exists
        epoch = datetime(2011, 1, 1)
        now_minutes = int((datetime.now() - epoch).total_seconds() / 60)

        fresh_offer = {
            "condition": 4,
            "sellerId": "SELLER_A",
            "isFBA": True,
            "offerCSV": [now_minutes, 1500, 0] # $15.00
        }

        product = {
            "asin": "TEST4",
            "offers": [fresh_offer],
            "stats": {
                "current": [-1, 2000, 3000, -1] # Stats say higher prices
            }
        }

        price, seller, is_fba, condition = get_used_product_info(product)

        # Should respect the fresh offer
        self.assertEqual(price, 1500)
        self.assertEqual(seller, "SELLER_A")

if __name__ == '__main__':
    unittest.main()
