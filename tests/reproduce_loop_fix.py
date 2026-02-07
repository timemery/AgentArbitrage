
import logging
import sys
import os

# Add the project root to the python path
sys.path.append(os.getcwd())

from keepa_deals.processing import _process_single_deal

# Mock logger
logging.basicConfig(level=logging.INFO)

def test_missing_data_ingestion_rejection():
    print("--- Testing Ingestion Rejection for Missing Data (Loop Prevention) ---")

    # Mock product that calculates PROFIT ok, but missing 1yr Avg
    # This simulates a "Heavy Re-fetch" result that still lacks key info.
    mock_product_zombie = {
        'asin': 'TESTLOOP001',
        'title': 'Zombie Loop Book',
        'csv': [None]*13,
        'offers': [{'offerCSV': [1000, 0], 'condition': 2}], # Used - Good, $10.00
        'stats': {
            'current': [2000, 2000, 1000, 500000],
            'avg365': [] # Empty -> Missing 1yr Avg
        },
        'categoryTree': [{'name': 'Books'}],
        'manufacturer': 'Test Press'
    }

    print("\nTesting _process_single_deal with Profit > 0 but Missing Data:")
    try:
        res = _process_single_deal(mock_product_zombie, {}, None)

        if res is None:
            print("PASS: Deal was rejected.")
        else:
            print(f"FAIL: Deal was NOT rejected. Keys: {res.keys()}")
            print(f"List at: {res.get('List at')}")
            print(f"1yr Avg: {res.get('1yr. Avg.')}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_missing_data_ingestion_rejection()
