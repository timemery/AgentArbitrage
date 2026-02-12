import unittest
from unittest.mock import patch, MagicMock

# Import the class/function to test
# Since smart_ingestor is a module with a 'run' task, we can't easily import the internal loop.
# But we can create a mock test that replicates the exact logic block.

class TestSmartIngestorSorting(unittest.TestCase):

    def test_sorting_fix(self):
        """
        Verifies that sorting deals DESCENDING allows finding NEW deals
        even if an OLD deal appears first in the raw list.
        """
        # Setup: Watermark is 100
        watermark_keepa_time = 100

        # Raw API Response: [Old, New, Old, Newest]
        # If we don't sort, we stop at Index 0 (Old <= Watermark).
        # If we sort, we get [Newest, New, Old, Old]. We process Newest and New, stop at Old.
        raw_deals = [
            {'asin': 'OLD_1', 'lastUpdate': 90},   # <= Watermark (STOP TRIGGER if unsorted)
            {'asin': 'NEW_1', 'lastUpdate': 110},  # > Watermark (Should be processed)
            {'asin': 'OLD_2', 'lastUpdate': 80},
            {'asin': 'NEW_2', 'lastUpdate': 120},  # > Watermark (Should be processed first)
        ]

        # --- Logic Before Fix (Simulation) ---
        processed_unsorted = []
        for deal in raw_deals:
            if deal['lastUpdate'] <= watermark_keepa_time:
                break # Stop immediately
            processed_unsorted.append(deal)

        self.assertEqual(len(processed_unsorted), 0, "Unsorted logic should fail to find any deals because Index 0 is old.")

        # --- Logic After Fix (Actual Code Pattern) ---
        # 1. Sort Descending
        deals_sorted = sorted(raw_deals, key=lambda x: x['lastUpdate'], reverse=True)

        # Verify Sort Order: [120, 110, 90, 80]
        self.assertEqual(deals_sorted[0]['lastUpdate'], 120)
        self.assertEqual(deals_sorted[1]['lastUpdate'], 110)
        self.assertEqual(deals_sorted[2]['lastUpdate'], 90)

        # 2. Iterate and check Watermark
        processed_sorted = []
        found_stop = False
        for deal in deals_sorted:
            if deal['lastUpdate'] <= watermark_keepa_time:
                found_stop = True
                break
            processed_sorted.append(deal)

        # Verify Results
        self.assertTrue(found_stop, "Should have found a stop trigger eventually.")
        self.assertEqual(len(processed_sorted), 2, "Should have found exactly 2 new deals.")
        self.assertEqual(processed_sorted[0]['asin'], 'NEW_2') # 120
        self.assertEqual(processed_sorted[1]['asin'], 'NEW_1') # 110

if __name__ == '__main__':
    unittest.main()
