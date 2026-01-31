
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from keepa_deals import ava_advisor

class TestAvaPrompt(unittest.TestCase):
    @patch('keepa_deals.ava_advisor.query_xai_api')
    def test_generate_ava_advice_prompt(self, mock_query):
        # Mock response
        mock_query.return_value = {
            'choices': [{'message': {'content': 'Mock advice'}}]
        }

        deal_data = {
            'Title': 'Test Book',
            'Price_Now': 20.0,
            '1yr_Avg': 30.0,
            'Sales_Rank_Current': 100000,
            'Sales_Rank_365_days_avg': 150000,
            'Detailed_Seasonality': 'No Seasonality',
            'Profit': 10.0,
            'Margin': 50.0,
            'Percent_Down': 33.3,
            'Trend': 'Flat',
            'Sales_Rank_Drops_last_365_days': 10
        }

        # Call the function
        ava_advisor.generate_ava_advice(deal_data, mentor_type='olyvia')

        # Get the call args
        args, kwargs = mock_query.call_args
        payload = args[0]
        user_message = payload['messages'][1]['content']

        # Check for constraints
        print("\n--- PROMPT SENT TO API ---\n")
        print(user_message)
        print("\n--------------------------\n")

        # Verify Intro is NOT present (this relies on knowing the intro text)
        intro_text = ava_advisor.MENTOR_PERSONAS['olyvia']['intro']
        if intro_text in user_message:
            print("FAILURE: Intro text found in prompt.")
        else:
            print("SUCCESS: Intro text NOT found in prompt.")

        # Verify Markdown constraint
        if "Do NOT use markdown formatting" in user_message:
            print("SUCCESS: Markdown constraint found.")
        else:
            print("FAILURE: Markdown constraint NOT found.")

        # Verify Intro constraint
        if "Do NOT start with an introduction" in user_message:
             print("SUCCESS: Intro constraint found.")
        else:
             print("FAILURE: Intro constraint NOT found.")

if __name__ == '__main__':
    unittest.main()
