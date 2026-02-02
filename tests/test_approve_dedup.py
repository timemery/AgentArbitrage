import sys
import os
import json
import unittest
from unittest.mock import patch, MagicMock

# Add repo root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock Flask and dependencies before importing wsgi_handler
mock_flask = MagicMock()
sys.modules['flask'] = mock_flask
sys.modules['celery_app'] = MagicMock()
sys.modules['keepa_deals.db_utils'] = MagicMock()
sys.modules['keepa_deals.janitor'] = MagicMock()
sys.modules['keepa_deals.ava_advisor'] = MagicMock()

# Configure app.route to return the function unchanged (Pass-through decorator)
def route_side_effect(*args, **kwargs):
    def decorator(f):
        return f
    return decorator

mock_app = MagicMock()
mock_app.route.side_effect = route_side_effect
mock_flask.Flask.return_value = mock_app

# Import the module to test
import wsgi_handler

class TestApproveDedup(unittest.TestCase):
    def setUp(self):
        # Create temp files for testing
        self.test_strategies = 'test_strategies_approve.json'
        self.test_intelligence = 'test_intelligence_approve.json'

        # Patch the file paths in wsgi_handler
        self.strategies_patcher = patch('wsgi_handler.STRATEGIES_FILE', self.test_strategies)
        self.intelligence_patcher = patch('wsgi_handler.INTELLIGENCE_FILE', self.test_intelligence)
        self.strategies_patcher.start()
        self.intelligence_patcher.start()

        # Mock request and session
        self.request_patcher = patch('wsgi_handler.request')
        self.session_patcher = patch('wsgi_handler.session')
        self.mock_request = self.request_patcher.start()
        self.mock_session = self.session_patcher.start()

        # Mock flash
        self.flash_patcher = patch('wsgi_handler.flash')
        self.mock_flash = self.flash_patcher.start()

    def tearDown(self):
        self.strategies_patcher.stop()
        self.intelligence_patcher.stop()
        self.request_patcher.stop()
        self.session_patcher.stop()
        self.flash_patcher.stop()

        if os.path.exists(self.test_strategies):
            os.remove(self.test_strategies)
        if os.path.exists(self.test_intelligence):
            os.remove(self.test_intelligence)

    def test_approve_duplicate_strategies(self):
        # Initial State: 1 strategy
        initial_strategies = [
            {"id": "1", "category": "Buying", "trigger": "Rank < 100k", "advice": "Buy!"}
        ]
        with open(self.test_strategies, 'w') as f:
            json.dump(initial_strategies, f)

        # Incoming: 1 Duplicate, 1 New
        incoming_strategies_json = json.dumps([
            {"category": "Buying", "trigger": "Rank < 100k", "advice": "Buy!"}, # Duplicate (no ID)
            {"category": "Selling", "trigger": "Profit > 10", "advice": "Sell!"} # New
        ])

        # Setup Mock Request
        self.mock_session.get.return_value = True # Logged in
        self.mock_request.form = {
            'approved_strategies': incoming_strategies_json,
            'approved_ideas': ''
        }

        # Execute
        wsgi_handler.approve()

        # Verify File Content
        with open(self.test_strategies, 'r') as f:
            final_strategies = json.load(f)

        self.assertEqual(len(final_strategies), 2) # 1 initial + 1 new

        # Verify Flash Message
        # Expected: "Saved 1 new strategies. Skipped 1 duplicates."
        args, _ = self.mock_flash.call_args_list[0]
        message = args[0]
        self.assertIn("Saved 1 new strategies", message)
        self.assertIn("Skipped 1 duplicates", message)

    def test_approve_duplicate_intelligence(self):
        # Initial State
        initial_ideas = ["Idea A"]
        with open(self.test_intelligence, 'w') as f:
            json.dump(initial_ideas, f)

        # Incoming: 1 Duplicate, 1 New
        incoming_ideas_text = "Idea A\nIdea B"

        # Setup Mock Request
        self.mock_session.get.return_value = True
        self.mock_request.form = {
            'approved_strategies': '',
            'approved_ideas': incoming_ideas_text
        }

        # Execute
        wsgi_handler.approve()

        # Verify File Content
        with open(self.test_intelligence, 'r') as f:
            final_ideas = json.load(f)

        self.assertEqual(len(final_ideas), 2)
        self.assertIn("Idea A", final_ideas)
        self.assertIn("Idea B", final_ideas)

        # Verify Flash Message
        args, _ = self.mock_flash.call_args_list[0]
        message = args[0]
        self.assertIn("Saved 1 new ideas", message)
        self.assertIn("Skipped 1 duplicates", message)

if __name__ == '__main__':
    unittest.main()
