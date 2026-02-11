
import sys
import os
import json
import logging
from keepa_deals.new_analytics import get_1yr_avg_sale_price

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_1yr_avg_fallback():
    print("\n--- Testing 1yr Avg Fallback Logic ---")

    # Mock Product Data simulating the problematic ASIN 1454919108
    # Missing CSV (or empty inferred sales) but valid Stats
    mock_product = {
        'asin': '1454919108',
        'csv': [], # simulate missing/empty CSV
        'stats': {
            'avg365': [
                -1, -1,
                23088, # Index 2: Used ($230.88)
                -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1, -1,
                -1,
                21000, # Index 19: Used - Like New ($210.00)
                -1,
                22500  # Index 21: Used - Good ($225.00)
            ]
        }
    }

    print(f"Input Stats (avg365[2]): {mock_product['stats']['avg365'][2]}")

    try:
        result = get_1yr_avg_sale_price(mock_product, logger)
        print(f"\nResult: {result}")

        if result and result.get('1yr. Avg.') == 230.88:
            print("✅ SUCCESS: Correctly fell back to avg365[2] ($230.88)")
        elif result and result.get('1yr. Avg.') == 230.88 and result.get('price_source') == 'Keepa Stats Fallback':
             print("✅ SUCCESS: Correctly fell back with source flag.")
        else:
            print("❌ FAILURE: Did not return expected $230.88")

    except Exception as e:
        print(f"❌ EXCEPTION: {e}")

if __name__ == "__main__":
    test_1yr_avg_fallback()
