import sys
import os
import logging
from unittest.mock import patch

# Ensure local imports work
sys.path.append(os.getcwd())

from keepa_deals.stable_calculations import analyze_sales_performance

# Configure logging
logging.basicConfig(level=logging.INFO)

def main():
    print("Verifying Fallback Logic...")

    # Mock product with stats but no sales
    product = {
        'asin': 'VERIFYFIX',
        'title': 'Verification Product',
        'categoryTree': [{'name': 'Books'}],
        'stats': {
            'current': [50000, 50000, 50000, 50000],
            'avg90': [None, None, 40000, 100000], # Used=40000
            'avg365': [None, None, 35000, 150000], # Used=35000
        }
    }
    sale_events = []

    # Mock XAI to avoid API calls (though my fix should skip it anyway)
    # But to be safe and test the logic flow, we rely on the skip.
    # Actually, let's NOT mock XAI to verify the skip works in integration?
    # No, we need an API key for that. Let's rely on the log message "Skipping AI Reasonableness Check".

    # We will use patch just to be safe against errors, but check the result.
    with patch('keepa_deals.stable_calculations._query_xai_for_reasonableness', return_value=False) as mock_xai:
        # We return False. If the skip logic works, the result should still be valid.
        # If skip fails, XAI (False) will reject it -> -1.

        result = analyze_sales_performance(product, sale_events)

        print(f"Result: {result}")

        if result['peak_price_mode_cents'] == 40000:
            print("SUCCESS: Fallback logic calculated 40000 and XAI check was skipped (or ignored).")
            if result['price_source'] == 'Keepa Stats Fallback':
                print("SUCCESS: Price Source identified correctly.")
            else:
                print(f"FAILURE: Price Source mismatch: {result['price_source']}")
        else:
            print(f"FAILURE: Expected 40000, got {result['peak_price_mode_cents']}")

if __name__ == "__main__":
    main()
