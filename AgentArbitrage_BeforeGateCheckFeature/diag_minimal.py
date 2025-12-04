# diag_minimal.py
import os
import sys
import json
import requests
import urllib.parse
from dotenv import load_dotenv

def run_minimal_diagnostic():
    print("--- STARTING MINIMAL DIAGNOSTIC SCRIPT ---")
    
    # 1. Load Environment
    print("\n[Step 1] Loading environment variables...")
    load_dotenv()
    api_key = os.getenv("KEEPA_API_KEY")
    if not api_key:
        print("  [FAIL] KEEPA_API_KEY not found in .env file. Aborting.")
        return
    print(f"  [OK] KEEPA_API_KEY loaded.")

    # 2. Minimal API Call
    print("\n[Step 2] Calling Keepa API with a MINIMAL request...")
    
    # This is the most basic valid query I can construct.
    minimal_query = {
        "page": 0,
        "domainId": 1,
        "priceTypes": [2],
        "dateRange": 30
    }
    
    # The API requires the 'selection' parameter to be URL-encoded JSON.
    encoded_selection = urllib.parse.quote(json.dumps(minimal_query))
    url = f"https://api.keepa.com/deal?key={api_key}&selection={encoded_selection}"
    
    print(f"  - URL being called: {url}")
    
    try:
        response = requests.get(url, timeout=60)
        
        print(f"  - Response Status Code: {response.status_code}")
        
        if response.status_code == 200:
            print("  [SUCCESS] Minimal API call was successful!")
            data = response.json()
            deals_found = len(data.get('deals', {}).get('dr', []))
            print(f"  - Deals found with minimal query: {deals_found}")
        else:
            print("  [FAIL] Minimal API call failed.")
            print(f"  - Response Text: {response.text}")

    except Exception as e:
        print(f"  [FAIL] An unexpected exception occurred: {e}")
        import traceback
        traceback.print_exc()

    print("\n--- MINIMAL DIAGNOSTIC SCRIPT FINISHED ---")

if __name__ == "__main__":
    run_minimal_diagnostic()