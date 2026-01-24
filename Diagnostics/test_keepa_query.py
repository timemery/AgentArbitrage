import os
import sys
import json
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals.keepa_api import fetch_deals_for_deals

def main():
    print("--- Testing Keepa Query (Page 0) ---")
    load_dotenv()
    api_key = os.getenv("KEEPA_API_KEY")
    if not api_key:
        print("ERROR: KEEPA_API_KEY not set.")
        return

    print(f"Using API Key: {api_key[:5]}...")

    # Run fetch
    # Note: sort_type=4 is 'Last Update' (Newest)
    response, consumed, left = fetch_deals_for_deals(0, api_key, sort_type=4)

    if not response:
        print("ERROR: No response from Keepa API.")
        return

    deals = response.get('deals', {}).get('dr', [])
    print(f"\nResults:")
    print(f"Deals Found: {len(deals)}")
    print(f"Tokens Consumed: {consumed}")
    print(f"Tokens Left: {left}")

    if deals:
        first_deal = deals[0]
        print(f"\nNewest Deal Timestamp (minutes): {first_deal.get('lastUpdate')}")
        print(f"ASIN: {first_deal.get('asin')}")
        print(f"Title: {first_deal.get('title')}")
    else:
        print("\nWARNING: Query returned 0 deals. Check keepa_query.json parameters.")

if __name__ == "__main__":
    main()
