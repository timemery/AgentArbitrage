import os
import sys
import json
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals.keepa_api import fetch_deals_for_deals

def convert_keepa(minutes):
    if not minutes: return "N/A"
    years = minutes / (60*24*365.25)
    return f"Year {2000 + years:.2f}"

def test_sort(sort_type, name):
    print(f"\n--- Testing Sort Type: {sort_type} ({name}) ---")
    load_dotenv()
    api_key = os.getenv("KEEPA_API_KEY")

    # We use the function which loads keepa_query.json automatically
    response, consumed, left = fetch_deals_for_deals(0, api_key, sort_type=sort_type)

    if not response or 'deals' not in response:
        print("No response or error.")
        return

    deals = response['deals'].get('dr', [])
    print(f"Deals Found: {len(deals)}")

    if deals:
        first = deals[0].get('lastUpdate')
        last = deals[-1].get('lastUpdate')

        print(f"First Deal: {convert_keepa(first)} ({first})")
        print(f"Last Deal:  {convert_keepa(last)} ({last})")

        if first > 13000000 or last > 13000000:
             print(">>> SUCCESS: Found 2026 Data!")
        else:
             print(">>> OLD DATA DETECTED")

def main():
    print("Investigating Keepa Sort Order (using keepa_api.py)...")

    test_sort(4, "Last Update - Default")
    test_sort(3, "Creation Date")
    # Try other sort types just in case
    # Keepa docs: 1 could be descending?
    test_sort(1, "Type 1")
    test_sort(2, "Type 2")

if __name__ == "__main__":
    main()
