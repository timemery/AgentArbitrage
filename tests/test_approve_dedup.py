import sys
import os
import json
import unittest
from unittest.mock import patch

# Add repo root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# `wsgi_handler` is imported for real, exactly as `tests/test_deduplication.py` does.
#
# This module used to install MagicMocks into sys.modules for 'flask', 'celery_app',
# 'keepa_deals.db_utils', 'keepa_deals.janitor' and 'keepa_deals.ava_advisor' at import
# time and never restore them. pytest imports every test module before running any test,
# so those mocks stayed live for the whole session and `sys.modules['wsgi_handler']` was
# left holding a Flask app that was really a MagicMock. That was the single cause of 25
# of the 26 pre-existing full-suite failures, including the AGENTS.md 7.12 guard in
# tests/test_lightweight_upsert_preservation.py.
#
# The mocking was never needed: flask, celery and the keepa_deals modules are all real
# dependencies that install from requirements.txt, and the sibling test_deduplication.py
# has always imported wsgi_handler without them. Scoping the mocks with patch.dict would
# have contained the blast radius but still left a mock-built wsgi_handler cached, so the
# mocking is removed at the source instead.
#
# The route body is exercised inside app.test_request_context() so `request.form`,
# `session` and `url_for` are the real Flask objects rather than mock attributes.
import wsgi_handler


class TestApproveDedup(unittest.TestCase):
    def setUp(self):
        # Create temp files for testing
        self.test_strategies = 'test_strategies_approve.json'
        self.test_intelligence = 'test_intelligence_approve.json'

        # Patch the file paths in wsgi_handler
        self.strategies_patcher = patch.object(
            wsgi_handler, 'STRATEGIES_FILE', self.test_strategies)
        self.intelligence_patcher = patch.object(
            wsgi_handler, 'INTELLIGENCE_FILE', self.test_intelligence)
        self.strategies_patcher.start()
        self.intelligence_patcher.start()

        # Mock flash so the messages can be asserted on directly.
        self.flash_patcher = patch.object(wsgi_handler, 'flash')
        self.mock_flash = self.flash_patcher.start()

    def tearDown(self):
        self.strategies_patcher.stop()
        self.intelligence_patcher.stop()
        self.flash_patcher.stop()

        if os.path.exists(self.test_strategies):
            os.remove(self.test_strategies)
        if os.path.exists(self.test_intelligence):
            os.remove(self.test_intelligence)

    def _call_approve(self, form):
        """Run the /approve view body against a real, logged-in POST request."""
        with wsgi_handler.app.test_request_context(
                '/approve', method='POST', data=form):
            from flask import session
            session['logged_in'] = True
            return wsgi_handler.approve()

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

        # Execute
        self._call_approve({
            'approved_strategies': incoming_strategies_json,
            'approved_ideas': ''
        })

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

        # Execute
        self._call_approve({
            'approved_strategies': '',
            'approved_ideas': incoming_ideas_text
        })

        # Verify File Content
        with open(self.test_intelligence, 'r') as f:
            final_ideas = json.load(f)

        self.assertEqual(len(final_ideas), 2)

        # Check Idea A (Legacy String)
        self.assertIn("Idea A", final_ideas)

        # Check Idea B (New Object format)
        # It might be an object now, so we search for content
        idea_b_found = False
        for i in final_ideas:
            if isinstance(i, dict) and i.get('content') == "Idea B":
                idea_b_found = True
                break
            elif i == "Idea B":
                idea_b_found = True
                break

        self.assertTrue(idea_b_found, "Idea B not found in final ideas")

        # Verify Flash Message
        args, _ = self.mock_flash.call_args_list[0]
        message = args[0]
        self.assertIn("Saved 1 new ideas", message)
        self.assertIn("Skipped 1 duplicates", message)

    def test_unauthenticated_request_is_redirected_without_writing(self):
        """The logged_in gate still holds. Kept so the auth branch is not lost."""
        with open(self.test_strategies, 'w') as f:
            json.dump([], f)

        with wsgi_handler.app.test_request_context(
                '/approve', method='POST',
                data={'approved_strategies': json.dumps(
                    [{"category": "Buying", "trigger": "t", "advice": "a"}]),
                    'approved_ideas': ''}):
            response = wsgi_handler.approve()

        self.assertEqual(302, response.status_code)
        with open(self.test_strategies, 'r') as f:
            self.assertEqual([], json.load(f))


if __name__ == '__main__':
    unittest.main()
