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

    print(f"--- Diagnostic: Inspect Latest Deals (RAW ORDER) ---")

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

    # 2. Fetch Latest Deals (Page 0)
    token_manager = TokenManager(api_key)
    print("Fetching Page 0...")
    deal_response, _, _ = fetch_deals_for_deals(0, api_key, sort_type=4, token_manager=token_manager)

    if not deal_response or 'deals' not in deal_response or not deal_response['deals']['dr']:
        print("No deals found on Page 0.")
        return

    deals = deal_response['deals']['dr']
    print(f"Found {len(deals)} deals on Page 0.")

    print("\n--- RAW ORDER (First 10 Items from API) ---")
    # This reveals if the API returns mixed results (Old, New, Old...)
    # If Item 1 is OLD, but Item 2 is NEW, then iterating and stopping at Item 1 is WRONG.

    count_new_missed = 0

    for i, deal in enumerate(deals[:10]):
        asin = deal['asin']
        last_update = deal['lastUpdate']
        last_update_iso = _convert_keepa_time_to_iso(last_update)

        status = "NEW"
        if last_update <= wm_keepa:
            status = "SEEN (<= Watermark)"
        else:
            status = "NEW (> Watermark)"

        print(f"[{i}] ASIN: {asin} | LastUpdate: {last_update} ({last_update_iso}) | Status: {status}")

        # Check if we would have stopped here
        if i == 0 and status == "SEEN (<= Watermark)":
             print("   CRITICAL: First item is OLD. Code stops immediately.")

    # Check for ANY new deal in the list that isn't at index 0
    for deal in deals:
        if deal['lastUpdate'] > wm_keepa:
             count_new_missed += 1

    print(f"\nTotal NEW deals available on Page 0: {count_new_missed}")

    if count_new_missed > 0 and deals[0]['lastUpdate'] <= wm_keepa:
        print("\nCONCLUSION: The API returns mixed/unsorted results. The code stops at the first old deal (Index 0), missing {count_new_missed} new deals.")
        print("FIX: Must sort Page 0 explicitly by LastUpdate DESC before checking Watermark.")
    elif count_new_missed == 0:
        print("\nCONCLUSION: No new deals found on Page 0. System is up to date (or Watermark is too high).")
    else:
        print("\nCONCLUSION: First deal is New. Logic should work correctly unless subsequent sorting is weird.")

if __name__ == "__main__":
    inspect_latest_deals()
