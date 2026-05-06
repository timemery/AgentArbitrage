#!/usr/bin/env python3
import sys
import os
import json
import logging

# Ensure we can import from the parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from wsgi_handler import app, query_xai_api

# Configure logging to output to stdout for visibility
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_xai_model():
    """
    Diagnostic script to test if the specific xAI model used in Pass 2
    is responsive and returns the correct JSON format.
    """
    logger.info("=== Starting Pass 2 xAI Model Diagnostic ===")

    # Mock data to simulate Pass 1 output
    mock_candidates = [
        {"ASIN": "TEST_ASIN_1", "Title": "Mock Book 1", "Profit": 25.00, "Detailed_Seasonality": "Year-round"},
        {"ASIN": "TEST_ASIN_2", "Title": "Mock Book 2", "Profit": 5.00, "Detailed_Seasonality": "Summer"}
    ]

    mock_strategies = [
        {"name": "High Profit Margin", "rules": ["Profit should be > $20"]}
    ]

    prompt = f"""
    You are the xAI Mastermind evaluating the top 10 candidate deals.

    **Evaluation Strategy:**
    You MUST evaluate candidates holistically against ALL strategies present in the provided JSON rules.

    Strategies:
    {json.dumps(mock_strategies, indent=2)}

    **Candidates:**
    {json.dumps(mock_candidates, indent=2)}

    Select the items (ASINs) that represent solid arbitrage opportunities based on the strategies. Filter out any deals that violate key risk management rules or are obviously poor choices, but allow good standard deals to pass.
    You MUST return ONLY a JSON array of strings containing the selected ASINs. No markdown formatting, no explanations.
    Example: ["0123456789", "B01ABCD123"]
    """

    # We are testing the model currently configured in wsgi_handler for Pass 2
    # which is "grok-4-fast-reasoning" based on our recent fix
    payload = {
        "messages": [
            {"role": "system", "content": "You are a precise JSON-only output bot."},
            {"role": "user", "content": prompt}
        ],
        "model": "grok-4-fast-reasoning",
        "stream": False,
        "temperature": 0.2
    }

    logger.info(f"Sending payload to model: {payload['model']}")

    try:
        response_data = query_xai_api(payload)
    except Exception as e:
        logger.error(f"Failed to communicate with xAI API: {e}")
        return

    if not response_data or "error" in response_data:
        logger.error(f"xAI API returned an error response: {response_data.get('error', 'Unknown Error')}")
        logger.error("Pass 2 is failing because the AI call itself is failing.")
        return

    logger.info("Successfully received response from xAI API.")

    if 'choices' in response_data and response_data['choices']:
        content = response_data['choices'][0].get('message', {}).get('content', '').strip()
        logger.info(f"Raw AI Response:\n{content}")

        # Test the parsing logic used in wsgi_handler
        import re
        content_stripped = re.sub(r'^```(?:json)?\s*|\s*```$', '', content.strip(), flags=re.MULTILINE).strip()

        try:
            parsed = json.loads(content_stripped)
            logger.info("SUCCESS: The AI response successfully parsed as JSON.")

            if isinstance(parsed, list):
                logger.info(f"SUCCESS: The parsed JSON is an array. Selected ASINs: {parsed}")
            elif isinstance(parsed, dict) and "asins" in parsed:
                logger.info(f"SUCCESS: The parsed JSON is a dict with 'asins'. Selected ASINs: {parsed['asins']}")
            else:
                logger.warning(f"WARNING: The parsed JSON format is unexpected: {type(parsed)}")

        except json.JSONDecodeError:
            logger.error("FAIL: Could not parse AI response as JSON. This will trigger the fallback.")
    else:
        logger.error("FAIL: AI response did not contain 'choices'.")

    logger.info("=== Diagnostic Complete ===")

if __name__ == "__main__":
    test_xai_model()
