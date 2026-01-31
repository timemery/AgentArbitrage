import sys
import os
import requests
import json
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
load_dotenv()

API_KEY = os.getenv("KEEPA_API_KEY")
if not API_KEY:
    print("Error: KEEPA_API_KEY not found in .env")
    sys.exit(1)

ASIN = "0321558235"  # Example ASIN

def fetch(history, stats):
    url = f"https://api.keepa.com/product?key={API_KEY}&domain=1&asin={ASIN}&stats={stats}&history={history}&offers=20&rating=1&only_live_offers=1"
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        consumed = data.get('tokensConsumed', 0)
        print(f"Fetch (history={history}, stats={stats}): Consumed {consumed} tokens.")

        products = data.get('products')
        if products:
            p = products[0]
            stats_obj = p.get('stats')
            if stats_obj:
                print(f"  Stats keys present: {len(stats_obj.keys())} keys")
                print(f"  salesRankDrops30: {stats_obj.get('salesRankDrops30')}")
                print(f"  current: {stats_obj.get('current')}")
                # print(f"  avg30: {stats_obj.get('avg30')}") # Removed to reduce noise
            else:
                print("  No stats object found.")

            # Check for offers
            offers = p.get('offers')
            if offers:
                print(f"  Offers count: {len(offers)}")
            else:
                print("  No offers found.")

        else:
            print("  No products found.")

    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        if e.response is not None:
             print(f"Response: {e.response.text}")
    except Exception as e:
        print(f"Error: {e}")

print("--- Testing Heavy Fetch (Current) ---")
fetch(history=1, stats=365) # Current usage uses stats=days=365

print("\n--- Testing Light Fetch (Proposed) ---")
fetch(history=0, stats=90) # Proposed usage
