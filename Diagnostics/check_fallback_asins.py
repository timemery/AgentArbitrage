import sys
import os
import json
import logging
import requests

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals.stable_calculations import analyze_sales_performance, infer_sale_events
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

asins_to_check = ['B01FIW4WL2', '163220293X', '0804007381', '0387257659']

def diagnose_asins():
    api_key = os.getenv('KEEPA_API_KEY')
    if not api_key:
        print("ERROR: Could not find KEEPA_API_KEY in environment variables. Cannot diagnose.")
        return

    print("Diagnosing ASINs to see if they relied on Keepa Stats Fallback...")

    for asin in asins_to_check:
        print(f"\n--- Checking ASIN: {asin} ---")

        # Manually fetch the product data from Keepa
        url = f"https://api.keepa.com/product?key={api_key}&domain=1&asin={asin}&history=1&stats=1&offers=20"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            if not data or 'products' not in data or not data['products']:
                print(f"Failed to fetch data for {asin}.")
                continue

            product = data['products'][0]

            # Determine how many inferred sales it has
            sale_events, total_drops = infer_sale_events(product)
            print(f"Total Drops from Keepa CSV (New+Used): {total_drops}")
            print(f"Total True Inferred Sales Found (Correlated with Rank): {len(sale_events)}")

            # Analyze sales performance
            analysis = analyze_sales_performance(product, sale_events)

            price_cents = analysis.get('peak_price_mode_cents', -1)
            print(f"Calculated 'List At' Price: ${price_cents / 100:.2f}" if price_cents > 0 else "Calculated 'List At' Price: REJECTED (-1)")
            print(f"Price Source Used: {analysis.get('price_source')}")

            if len(sale_events) < 3:
                if analysis.get('price_source') == 'Keepa Stats Fallback':
                    print("CONCLUSION: This ASIN relied on the REMOVED Keepa Stats Fallback logic (Average Listing Prices).")
                elif analysis.get('price_source') == 'Inferred Sales (Sparse)':
                    print("CONCLUSION: This ASIN relied on the Sparse Sales logic (1 or 2 True Inferred Sales).")
                else:
                    print("CONCLUSION: This ASIN was rejected.")
            else:
                print("CONCLUSION: This ASIN had 3+ sales and did not rely on any fallback logic. It is a true high-volume deal.")

        except Exception as e:
            print(f"Error checking {asin}: {e}")

if __name__ == '__main__':
    diagnose_asins()
