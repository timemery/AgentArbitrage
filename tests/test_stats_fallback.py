import unittest
from datetime import datetime, timedelta
from keepa_deals.seller_info import get_used_product_info

class TestStatsFallback(unittest.TestCase):

    def test_stats_fallback_when_offers_empty(self):
        # Product with no offers but valid stats
        product = {
            "asin": "TEST1",
            "offers": [],
            "stats": {
                "current": [-1, -1, 2500, -1] # Index 2 = 2500 cents ($25.00)
            }
        }

        price, seller, is_fba, condition = get_used_product_info(product)

        self.assertEqual(price, 2500)
        self.assertEqual(seller, "Unknown")
        self.assertFalse(is_fba)
        self.assertEqual(condition, 4) # Used - Good

    def test_stats_fallback_when_offers_stale(self):
        # Product with stale offer (older than 365 days)
        # Keepa epoch is 2011-01-01
        # 1 year ago from now is approx (Now - 2011) - 1 year in minutes
        # Let's just use a very small timestamp (e.g., 0)

        stale_offer = {
            "condition": 4,
            "offerCSV": [0, 1000, 0] # Timestamp 0, Price 1000, Ship 0
        }

        product = {
            "asin": "TEST2",
            "offers": [stale_offer],
            "stats": {
                "current": [-1, -1, 3000, -1] # Index 2 = 3000 cents ($30.00)
            }
        }

        price, seller, is_fba, condition = get_used_product_info(product)

        # Should skip offer (stale) and use stats
        self.assertEqual(price, 3000)
        self.assertEqual(seller, "Unknown")

    def test_offers_priority_over_stats(self):
        # Product with valid fresh offer AND valid stats
        # Create a fresh timestamp: Now in keepa minutes
        epoch = datetime(2011, 1, 1)
        now_minutes = int((datetime.now() - epoch).total_seconds() / 60)

        fresh_offer = {
            "condition": 4,
            "sellerId": "SELLER_X",
            "isFBA": True,
            "offerCSV": [now_minutes, 1500, 0] # $15.00
        }

        product = {
            "asin": "TEST3",
            "offers": [fresh_offer],
            "stats": {
                "current": [-1, -1, 2000, -1] # $20.00 (Higher/Lower doesn't matter, offer takes priority)
            }
        }

        price, seller, is_fba, condition = get_used_product_info(product)

        # Should use offer
        self.assertEqual(price, 1500)
        self.assertEqual(seller, "SELLER_X")
        self.assertTrue(is_fba)

    def test_no_stats_no_offers(self):
        product = {
            "asin": "TEST4",
            "offers": [],
            "stats": {
                "current": [-1, -1, -1, -1]
            }
        }

        price, seller, is_fba, condition = get_used_product_info(product)

        self.assertIsNone(price)

if __name__ == '__main__':
    unittest.main()
