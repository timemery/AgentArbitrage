
import sys
import os
import json
import requests
import urllib.parse
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load env vars
load_dotenv()

def fetch_deals_raw(api_key, query_params):
    # Ensure page and sortType are set if not present
    if 'page' not in query_params:
        query_params['page'] = 0
    if 'sortType' not in query_params:
        query_params['sortType'] = 4

    query_json = json.dumps(query_params, separators=(',', ':'), sort_keys=True)
    encoded_selection = urllib.parse.quote(query_json)
    url = f"https://api.keepa.com/deal?key={api_key}&selection={encoded_selection}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/90.0.4430.212'}

    print(f"Querying Keepa with params (truncated): {str(query_params)[:100]}...")
    try:
        response = requests.get(url, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()

        if 'error' in data:
             print(f"API Error: {data['error']}")
             return 0, data

        deals = data.get('deals', {}).get('dr', [])
        count = len(deals)
        print(f"  -> Found {count} deals.")
        return count, data
    except Exception as e:
        print(f"  -> Exception: {e}")
        return 0, None

def main():
    api_key = os.getenv("KEEPA_API_KEY")
    if not api_key:
        print("Error: KEEPA_API_KEY not found in environment.")
        return

    # 1. More Deals (from User Table)
    more_deals_query = {
       "page": 0,
       "domainId": "1",
       "excludeCategories": [],
       "includeCategories": [283155],
       "priceTypes": [2],
       "deltaRange": [0, 10000],
       "deltaPercentRange": [10, 2147483647],
       "salesRankRange": [10000, 10000000],
       "currentRange": [0, 2147483647],
       "minRating": 10,
       "isLowest": False,
       "isLowest90": False,
       "isLowestOffer": False,
       "isOutOfStock": False,
       "titleSearch": "",
       "isRangeEnabled": True,
       "isFilterEnabled": True,
       "filterErotic": False,
       "singleVariation": True,
       "hasReviews": False,
       "isPrimeExclusive": False,
       "mustHaveAmazonOffer": False,
       "mustNotHaveAmazonOffer": False,
       "sortType": 4,
       "dateRange": 4, # User note: 4 = All combined?
       "warehouseConditions": [2, 3, 4, 5],
       "deltaLastRange": [500, 2147483647]
    }

    # 2. LESS Deals (from User Table)
    less_deals_query = {
       "page": 0,
       "domainId": "1",
       "excludeCategories": [],
       "includeCategories": [283155],
       "priceTypes": [2],
       "deltaRange": [0, 10000],
       "deltaPercentRange": [50, 90], # 50% to 90%
       "salesRankRange": [10000, 10000000],
       "currentRange": [2000, 30000], # $20 to $300
       "minRating": 10,
       "isLowest": False,
       "isLowest90": False,
       "isLowestOffer": False,
       "isOutOfStock": False,
       "titleSearch": "",
       "isRangeEnabled": True,
       "isFilterEnabled": True,
       "filterErotic": False,
       "singleVariation": True,
       "hasReviews": False,
       "isPrimeExclusive": False,
       "mustHaveAmazonOffer": False,
       "mustNotHaveAmazonOffer": False,
       "sortType": 4,
       "dateRange": 4,
       "warehouseConditions": [2, 3, 4, 5],
       "deltaLastRange": [1950, 6000]
    }

    # 3. Refiller Test (from User Table)
    refiller_test_query = {
       "page": 0,
       "domainId": "1",
       "excludeCategories": [],
       "includeCategories": [283155],
       "priceTypes": [2],
       "deltaRange": [0, 10000],
       "deltaPercentRange": [20, 2147483647],
       "salesRankRange": [100000, 5000000],
       "currentRange": [2000, 23500],
       "minRating": 50,
       "isLowest": False,
       "isLowest90": False,
       "isLowestOffer": False,
       "isOutOfStock": False,
       "titleSearch": "",
       "isRangeEnabled": True,
       "isFilterEnabled": True,
       "filterErotic": False,
       "singleVariation": True,
       "hasReviews": False,
       "isPrimeExclusive": False,
       "mustHaveAmazonOffer": False,
       "mustNotHaveAmazonOffer": False,
       "sortType": 4,
       "dateRange": 3, # 3 Months
       "warehouseConditions": [2, 3, 4, 5],
       "deltaLastRange": [0, 10000]
    }

    # 4. TONS o' Deals
    tons_deals_query = {
       "page": 0,
       "domainId": "1",
       "excludeCategories": [],
       "includeCategories": [283155],
       "priceTypes": [2],
       "deltaRange": [0, 10000],
       "deltaPercentRange": [10, 2147483647],
       "salesRankRange": [10000, 10000000],
       "currentRange": [2000, 45100],
       "minRating": 10,
       "isLowest": False,
       "isLowest90": False,
       "isLowestOffer": False,
       "isOutOfStock": False,
       "titleSearch": "",
       "isRangeEnabled": True,
       "isFilterEnabled": True,
       "filterErotic": False,
       "singleVariation": True,
       "hasReviews": False,
       "isPrimeExclusive": False,
       "mustHaveAmazonOffer": False,
       "mustNotHaveAmazonOffer": False,
       "sortType": 4,
       "dateRange": 4,
       "warehouseConditions": [2, 3, 4, 5],
       "deltaLastRange": [0, 2147483647]
    }

    print("--- Testing Keepa Queries ---")

    print("\n1. Testing 'More Deals' (Expected: ~4,929 Books)")
    fetch_deals_raw(api_key, more_deals_query)

    print("\n2. Testing 'LESS Deals' (Expected: ~154 Books)")
    fetch_deals_raw(api_key, less_deals_query)

    print("\n3. Testing 'Refiller Test' (Expected: ~890 Books)")
    fetch_deals_raw(api_key, refiller_test_query)

    print("\n4. Testing 'TONS o Deals' (Expected: ~24,373 Books)")
    fetch_deals_raw(api_key, tons_deals_query)

if __name__ == "__main__":
    main()
