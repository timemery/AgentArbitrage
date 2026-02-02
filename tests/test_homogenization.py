import json
import os
import unittest
from unittest.mock import patch, MagicMock
import wsgi_handler

class TestHomogenization(unittest.TestCase):
    def setUp(self):
        self.test_file = 'test_intelligence_homogenize.json'
        # Create a list with semantic duplicates
        self.data = [
            "Always buy low and sell high.",
            "Buy low, sell high is the key.",
            "Purchasing at a lower price and selling at a higher price is essential.",
            "Avoid restricted brands.",
            "Stay away from gated items."
        ]
        with open(self.test_file, 'w') as f:
            json.dump(self.data, f)

        self.file_patcher = patch('wsgi_handler.INTELLIGENCE_FILE', self.test_file)
        self.file_patcher.start()

    def tearDown(self):
        self.file_patcher.stop()
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    @patch('wsgi_handler.query_xai_api')
    def test_homogenize_intelligence(self, mock_query):
        # Mock the LLM response to return a merged list
        # Expected: 2 unique concepts from the 5 items
        mock_response = {
            'choices': [{
                'message': {
                    'content': '["Always buy low and sell high.", "Avoid restricted brands and gated items."]'
                }
            }]
        }
        mock_query.return_value = mock_response

        removed_count = wsgi_handler._homogenize_intelligence()

        # Original 5, New 2 -> Removed 3
        self.assertEqual(removed_count, 3)

        with open(self.test_file, 'r') as f:
            new_data = json.load(f)
            self.assertEqual(len(new_data), 2)
            self.assertIn("Always buy low and sell high.", new_data)

if __name__ == '__main__':
    unittest.main()
