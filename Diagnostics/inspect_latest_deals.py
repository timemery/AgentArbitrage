import os
import sys
import json
import sqlite3
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals.db_utils import load_watermark, DB_PATH
from keepa_deals.smart_ingestor import _convert_iso_to_keepa_time, _convert_keepa_time_to_iso, save_safe_watermark
from keepa_deals.keepa_api import fetch_deals_for_deals
from keepa_deals.token_manager import TokenManager

def inspect_latest_deals():
    load_dotenv()
    api_key = os.getenv("KEEPA_API_KEY")
    if not api_key:
        print("ERROR: KEEPA_API_KEY not found in environment.")
        return

    print(f"--- Diagnostic: Inspect Latest Deals ---")

    # 1. Load Current Watermark
    wm_iso = load_watermark()
    wm_keepa = _convert_iso_to_keepa_time(wm_iso) if wm_iso else 0
    print(f"Current Watermark (ISO): {wm_iso}")
    print(f"Current Watermark (Keepa Minutes): {wm_keepa}")

    if wm_iso:
        wm_dt = datetime.fromisoformat(wm_iso).astimezone(timezone.utc)
        now_utc = datetime.now(timezone.utc)
        diff = (wm_dt - now_utc).total_seconds()
        print(f"Watermark vs Now: {diff:.2f} seconds difference.")
        if diff > 0:
            print(f"WARNING: Watermark is in the future!")
        else:
            print(f"Watermark is in the past.")

    # 2. Fetch Latest Deals (Page 0)
    token_manager = TokenManager(api_key)
    print("Fetching Page 0...")
    deal_response, _, _ = fetch_deals_for_deals(0, api_key, sort_type=4, token_manager=token_manager)

    if not deal_response or 'deals' not in deal_response or not deal_response['deals']['dr']:
        print("No deals found on Page 0.")
        return

    deals = deal_response['deals']['dr']
    print(f"Found {len(deals)} deals on Page 0.")

    # Sort them by lastUpdate DESC (Newest First) just to be sure
    # Keepa API returns DESC usually for sortType=4
    deals_sorted = sorted(deals, key=lambda x: x['lastUpdate'], reverse=True)

    print("\nTop 5 Newest Deals found:")
    for i, deal in enumerate(deals_sorted[:5]):
        asin = deal['asin']
        last_update = deal['lastUpdate']
        last_update_iso = _convert_keepa_time_to_iso(last_update)

        status = "NEW"
        if last_update <= wm_keepa:
            status = "SEEN (<= Watermark)"
        else:
            status = "NEW (> Watermark)"

        print(f"{i+1}. ASIN: {asin} | LastUpdate: {last_update} ({last_update_iso}) | Status: {status}")

        # Check specific future check logic
        deal_dt = datetime.fromisoformat(last_update_iso).astimezone(timezone.utc)
        now_utc = datetime.now(timezone.utc)
        future_diff = (deal_dt - now_utc).total_seconds()

        if future_diff > 0:
            print(f"   WARNING: Deal is {future_diff:.2f} seconds in the FUTURE!")

    # 3. Simulate Logic Check
    print("\n--- Logic Simulation ---")
    top_deal = deals_sorted[0]
    top_deal_iso = _convert_keepa_time_to_iso(top_deal['lastUpdate'])
    print(f"Top Deal Time: {top_deal_iso}")

    # Simulate 'save_safe_watermark'
    print("Simulating save_safe_watermark logic:")
    try:
        wm_dt = datetime.fromisoformat(top_deal_iso).astimezone(timezone.utc)
        now_utc = datetime.now(timezone.utc)
        clamped_iso = top_deal_iso
        if wm_dt > now_utc:
            print(f"   -> CLAMPING TRIGGERED: {top_deal_iso} is > {now_utc.isoformat()}")
            clamped_iso = now_utc.isoformat()
            print(f"   -> Resulting Watermark would be: {clamped_iso}")

            # Check if next run would see it again
            clamped_keepa = _convert_iso_to_keepa_time(clamped_iso)
            if top_deal['lastUpdate'] > clamped_keepa:
                print("   -> LOOP DETECTED: Next run will see this deal again because Real Time > Clamped Time.")
            else:
                print("   -> No Loop detected immediately, but risk exists.")
        else:
            print("   -> No clamping needed.")

    except Exception as e:
        print(f"Error in simulation: {e}")

if __name__ == "__main__":
    inspect_latest_deals()
