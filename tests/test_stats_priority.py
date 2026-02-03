import unittest
import sys
import os
from datetime import datetime, timedelta

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals.seller_info import get_used_product_info

class TestStatsPriority(unittest.TestCase):

    def test_stats_match_offer(self):
        # Case 1: Stats has price, Offer matches -> Full Info
        # Stats Price: 2500
        # Offer Price: 2500 (Item) + 0 (Ship)
        epoch = datetime(2011, 1, 1)
        now_minutes = int((datetime.now() - epoch).total_seconds() / 60)

        offer_match = {
            "condition": 4, # Used Good
            "sellerId": "SELLER_MATCH",
            "isFBA": True,
            "offerCSV": [now_minutes, 2500, -1] # Price matches stats
        }

        product = {
            "asin": "TEST1",
            "offers": [offer_match],
            "stats": {
                "current": [-1, -1, 2500, -1] # Index 2 = Used
            }
        }

        price, seller, is_fba, condition = get_used_product_info(product)

        # Expect: Price 2500 + 0 (FBA ship) = 2500
        self.assertEqual(price, 2500)
        self.assertEqual(seller, "SELLER_MATCH")
        self.assertTrue(is_fba)

    def test_stats_no_match_fallback(self):
        # Case 2: Stats has price, No Offer match -> Price + Unknown Seller + Def Ship
        # Stats Price: 3000
        # Offer Price: 5000 (No match)

        offer_mismatch = {
            "condition": 4,
            "sellerId": "SELLER_WRONG",
            "offerCSV": [0, 5000, 0]
        }

        product = {
            "asin": "TEST2",
            "offers": [offer_mismatch],
            "stats": {
                "current": [-1, -1, 3000, -1]
            }
        }

        # Mock default shipping as 200 cents (from default settings if file missing/mocked)
        # Note: In the test env, we expect it to load the file or default.
        # Let's assume default is 200 cents ($2.00) based on previous reads.

        price, seller, is_fba, condition = get_used_product_info(product)

        # Expect: 3000 (Item) + 200 (Def Ship) = 3200
        # NOTE: The implementation adds default shipping if no match found.
        # We need to verify if settings.json is loaded. In this sandbox, it exists.

        self.assertGreater(price, 3000) # Should include shipping
        self.assertEqual(seller, "Unknown")
        self.assertEqual(condition, 4)

    def test_stats_missing_returns_none(self):
        # Case 3: Stats missing, Offers exist -> Return None (Unavailable)
        # Even if offer exists, if stats says -1, we trust stats (it's gone).

        offer_zombie = {
            "condition": 4,
            "offerCSV": [0, 1000, 0]
        }

        product = {
            "asin": "TEST3",
            "offers": [offer_zombie],
            "stats": {
                "current": [-1, -1, -1, -1] # All missing
            }
        }

        price, seller, is_fba, condition = get_used_product_info(product)

        self.assertIsNone(price)

    def test_new_price_fallback(self):
        # Case 4: Used Missing, New Available -> Use New Stats Price
        product = {
            "asin": "TEST4",
            "offers": [],
            "stats": {
                "current": [-1, 4000, -1, -1] # New = 4000
            }
        }

        price, seller, is_fba, condition = get_used_product_info(product)

        # Expect: 4000 + Def Ship (since no offer match)
        self.assertGreater(price, 4000)
        self.assertEqual(seller, "Unknown")
        self.assertEqual(condition, 0) # New

if __name__ == '__main__':
    unittest.main()
