import unittest
from keepa_deals.processing import clean_numeric_values

class TestProcessingLogic(unittest.TestCase):
    def test_clean_numeric_values_avg(self):
        # Test 1yr. Avg. cleaning (added "Avg" to keyword list)
        row_data = {
            "1yr. Avg.": "$30.00",
            "Price Now": "$25.00",
            "Profit": "$5.00",
            "Other Field": "Some Text"
        }
        cleaned = clean_numeric_values(row_data)

        self.assertIsInstance(cleaned["1yr. Avg."], float)
        self.assertEqual(cleaned["1yr. Avg."], 30.0)
        self.assertEqual(cleaned["Price Now"], 25.0)
        self.assertEqual(cleaned["Profit"], 5.0)
        self.assertEqual(cleaned["Other Field"], "Some Text")

    def test_clean_numeric_values_avg_with_comma(self):
        row_data = {
            "1yr. Avg.": "$1,200.50"
        }
        cleaned = clean_numeric_values(row_data)
        self.assertEqual(cleaned["1yr. Avg."], 1200.50)

    def test_clean_numeric_values_avg_invalid(self):
        row_data = {
            "1yr. Avg.": "N/A"
        }
        cleaned = clean_numeric_values(row_data)
        self.assertIsNone(cleaned["1yr. Avg."])

if __name__ == '__main__':
    unittest.main()
