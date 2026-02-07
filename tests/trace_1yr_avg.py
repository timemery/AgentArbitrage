
import logging
import sys
import os
import json
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())

from keepa_deals.keepa_api import fetch_product_batch
from keepa_deals.stable_calculations import infer_sale_events, _convert_ktm_to_datetime

# Load env
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def trace_asin(asin):
    api_key = os.getenv("KEEPA_API_KEY")
    if not api_key:
        print("Error: KEEPA_API_KEY not set.")
        return

    print(f"--- TRACING ASIN: {asin} ---")
    response, _, _, _ = fetch_product_batch(api_key, [asin], days=365, history=1, offers=20)

    if not response or 'products' not in response:
        print("Error: No response from Keepa.")
        return

    product = response['products'][0]

    # 1. Raw History Check
    csv_data = product.get('csv', [])
    if len(csv_data) < 13:
        print("FAIL: Incomplete CSV history.")
        return

    rank_history = csv_data[3]
    used_offer_history = csv_data[12]

    print(f"Raw History Points - Rank: {len(rank_history)//2}, Used Offers: {len(used_offer_history)//2}")

    # 2. Offer Drops
    # We will manually inspect what infer_sale_events sees
    # Re-using logic from stable_calculations to print details

    print("\n--- Sale Inference Logic Trace ---")
    sale_events, total_drops = infer_sale_events(product)

    print(f"Total Offer Drops Found: {total_drops}")
    print(f"Confirmed Sales (Rank Drop within 240h): {len(sale_events)}")

    if not sale_events:
        print("Reason for 0 Sales: No correlation between Offer Drops and Rank Drops.")
        print("Possible Reasons: ")
        print("  1. Offers were removed but not sold (delisted).")
        print("  2. Rank drops happened too late (>10 days later).")
        print("  3. High Rank (low velocity) makes drops hard to see.")
    else:
        print("\n--- Confirmed Sales (Last 5) ---")
        for s in sale_events[-5:]:
            ts = s['event_timestamp']
            price = s['inferred_sale_price_cents'] / 100.0
            print(f"  Date: {ts}, Price: ${price:.2f}")

    # 3. 1yr Avg Calculation
    print("\n--- 1yr Avg Calculation ---")
    if sale_events:
        df = pd.DataFrame(sale_events)
        one_year_ago = datetime.now() - timedelta(days=365)
        df_last_year = df[df['event_timestamp'] >= one_year_ago]

        print(f"Sales in Last 365 Days: {len(df_last_year)}")
        if len(df_last_year) > 0:
            avg_price = df_last_year['inferred_sale_price_cents'].mean() / 100.0
            print(f"Calculated 1yr Avg: ${avg_price:.2f}")
        else:
            print("FAIL: No sales in the last 365 days (all sales were older).")
    else:
        print("FAIL: No sales inferred at all.")

if __name__ == "__main__":
    target_asin = '1455616133' # One of the problem ASINs
    trace_asin(target_asin)
