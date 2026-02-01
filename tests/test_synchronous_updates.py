
import unittest
from datetime import datetime, timedelta
from keepa_deals.stable_calculations import infer_sale_events, KEEPA_EPOCH

class TestSynchronousUpdates(unittest.TestCase):
    def test_synchronous_offer_and_rank_drop(self):
        """
        Tests that a sale is inferred when the Offer Count drop and Sales Rank drop
        occur at the EXACT same timestamp (synchronous update from a crawl).
        """
        # Define a base time relative to KEEPA_EPOCH
        # Keepa epoch is 2011-01-01
        # Let's pick a time in 2024.
        # 2024 is approx 13 years * 525600 min = ~6.8M minutes.
        base_time = 7000000

        # Scenario:
        # T=0 (relative to base): Initial state. Rank 500k, Offer Count 10.
        # T=1440 (1 day later): Sale happens! Rank 100k, Offer Count 9.
        # Both updates recorded at exactly T=1440.

        t0 = base_time
        t1 = base_time + 1440

        rank_history = [t0, 500000, t1, 100000] # Drop: 500k -> 100k
        used_offer_history = [t0, 10, t1, 9]    # Drop: 10 -> 9

        # We also need price history for the function to work
        used_price_history = [t0, 2000, t1, 2000] # Price $20.00

        product = {
            'asin': 'TESTSYNC',
            'csv': [
                None, # 0
                None, # 1: New Price
                used_price_history, # 2: Used Price
                rank_history, # 3: Sales Rank
                None, None, None, None, None, None, None,
                None, # 11: New Offers
                used_offer_history, # 12: Used Offers
                # Ensure length > 12
                None, None, None
            ]
        }

        sales, drop_count = infer_sale_events(product)

        # Expectation:
        # 1 Offer Drop (at t1)
        # 1 Confirmed Sale (because Rank dropped at t1, which matches >= t1)

        self.assertEqual(drop_count, 1, "Should detect 1 offer drop")
        self.assertEqual(len(sales), 1, "Should detect 1 confirmed sale event")

        if sales:
            sale = sales[0]
            # Verify timestamp matches t1
            expected_dt = KEEPA_EPOCH + timedelta(minutes=t1)
            self.assertEqual(sale['event_timestamp'], expected_dt)
            self.assertEqual(sale['inferred_sale_price_cents'], 2000)

    def test_asynchronous_offer_and_rank_drop(self):
        """
        Tests that a sale is inferred when the Rank drop occurs AFTER the Offer Count drop.
        (Standard behavior, should still work with >= change).
        """
        base_time = 7000000

        t0 = base_time
        t1 = base_time + 1440 # Offer Drop
        t2 = base_time + 2000 # Rank Drop (Later)

        rank_history = [t0, 500000, t2, 100000] # Drop at t2
        used_offer_history = [t0, 10, t1, 9]    # Drop at t1
        used_price_history = [t0, 2000, t1, 2000]

        product = {
            'asin': 'TESTASYNC',
            'csv': [
                None, None, used_price_history, rank_history,
                None, None, None, None, None, None, None,
                None, used_offer_history, None
            ]
        }

        sales, drop_count = infer_sale_events(product)

        self.assertEqual(drop_count, 1, "Should detect 1 offer drop")
        self.assertEqual(len(sales), 1, "Should detect 1 confirmed sale event")

        if sales:
            sale = sales[0]
            # Event timestamp is the OFFER DROP time (t1)
            expected_dt = KEEPA_EPOCH + timedelta(minutes=t1)
            self.assertEqual(sale['event_timestamp'], expected_dt)

if __name__ == '__main__':
    unittest.main()
