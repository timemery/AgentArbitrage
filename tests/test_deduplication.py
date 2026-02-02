import sys
import os
import json
import unittest
from unittest.mock import patch, MagicMock

# Add repo root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# We need to import the functions to test.
# Note: Since wsgi_handler imports STRATEGIES_FILE etc at module level, patching them in the module might be tricky if we don't do it right.
# But we can patch them where they are used.
import wsgi_handler

class TestDeduplication(unittest.TestCase):
    def setUp(self):
        # Create temp files for testing
        self.test_strategies = 'test_strategies.json'
        self.test_intelligence = 'test_intelligence.json'

        # Patch the file paths in wsgi_handler
        self.strategies_patcher = patch('wsgi_handler.STRATEGIES_FILE', self.test_strategies)
        self.intelligence_patcher = patch('wsgi_handler.INTELLIGENCE_FILE', self.test_intelligence)
        self.strategies_patcher.start()
        self.intelligence_patcher.start()

    def tearDown(self):
        self.strategies_patcher.stop()
        self.intelligence_patcher.stop()
        if os.path.exists(self.test_strategies):
            os.remove(self.test_strategies)
        if os.path.exists(self.test_intelligence):
            os.remove(self.test_intelligence)

    def test_deduplicate_strategies(self):
        # Create strategies with duplicates
        strategies = [
            {"category": "Buying", "trigger": "Rank < 100k", "advice": "Buy!"},
            {"category": "Buying", "trigger": "Rank < 100k", "advice": "Buy!"}, # Duplicate
            {"category": "Selling", "trigger": "Profit > 10", "advice": "Sell!"},
            "Legacy Strategy",
            "Legacy Strategy" # Duplicate
        ]

        with open(self.test_strategies, 'w') as f:
            json.dump(strategies, f)

        removed = wsgi_handler._deduplicate_strategies()
        self.assertEqual(removed, 2)

        with open(self.test_strategies, 'r') as f:
            unique = json.load(f)
            self.assertEqual(len(unique), 3)

    def test_deduplicate_intelligence(self):
        # Create intelligence with duplicates
        intelligence = [
            "Concept A",
            "Concept B",
            "Concept A", # Duplicate
            "Concept C"
        ]

        with open(self.test_intelligence, 'w') as f:
            json.dump(intelligence, f)

        removed = wsgi_handler._deduplicate_intelligence()
        self.assertEqual(removed, 1)

        with open(self.test_intelligence, 'r') as f:
            unique = json.load(f)
            self.assertEqual(len(unique), 3)

if __name__ == '__main__':
    unittest.main()
