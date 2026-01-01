import unittest
import json
import os
from keepa_deals.ava_advisor import load_strategies

class TestAvaAdvisor(unittest.TestCase):
    def setUp(self):
        self.test_file = 'strategies.json'
        # Create a mock strategies file
        self.mock_strategies = [
            "Legacy Strategy 1",
            {
                "id": "1",
                "category": "Seasonality",
                "trigger": "Textbook Season",
                "advice": "Buy early."
            },
            {
                "id": "2",
                "category": "Risk",
                "trigger": "High Rank",
                "advice": "Avoid."
            },
            {
                "id": "3",
                "category": "General",
                "trigger": "Always",
                "advice": "Be nice."
            }
        ]

        # Backup original if it exists
        self.original_content = None
        if os.path.exists(self.test_file):
            with open(self.test_file, 'r') as f:
                self.original_content = f.read()

        with open(self.test_file, 'w') as f:
            json.dump(self.mock_strategies, f)

    def tearDown(self):
        # Restore original
        if self.original_content:
            with open(self.test_file, 'w') as f:
                f.write(self.original_content)

    def test_load_strategies_no_context(self):
        # Should return all strategies including legacy
        text = load_strategies()
        self.assertIn("Legacy Strategy 1", text)
        self.assertIn("Category: Seasonality", text)
        self.assertIn("Category: Risk", text)
        self.assertIn("Category: General", text)

    def test_load_strategies_with_textbook_context(self):
        context = {'Title': 'Calculus', 'Detailed_Seasonality': 'Textbook'}
        text = load_strategies(context)
        self.assertIn("Legacy Strategy 1", text)
        self.assertIn("Category: Seasonality", text) # Should be included
        self.assertIn("Category: Risk", text) # Default included
        self.assertIn("Category: General", text) # Default included

    # Note: Currently my implementation includes "Risk" by default.
    # If I had a category NOT in defaults (e.g., "Niche"), I could test its exclusion.

    def test_load_strategies_with_irrelevant_context(self):
        # Create a strategy with a weird category
        custom_strategies = self.mock_strategies + [{
            "id": "4",
            "category": "WeirdCategory",
            "trigger": "Never",
            "advice": "Don't show."
        }]
        with open(self.test_file, 'w') as f:
            json.dump(custom_strategies, f)

        context = {'Title': 'Novel', 'Detailed_Seasonality': 'None'}
        text = load_strategies(context)

        self.assertIn("Legacy Strategy 1", text)
        self.assertNotIn("Category: WeirdCategory", text) # Should be excluded
        self.assertIn("Category: General", text)

if __name__ == '__main__':
    unittest.main()
