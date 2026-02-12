
import os
import sys
import json
import logging
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Add repo root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals.keepa_api import fetch_deals_for_deals
from keepa_deals.db_utils import load_watermark

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _convert_keepa_time_to_iso(keepa_minutes):
    """Converts Keepa time (minutes since 2011-01-01) to ISO 8601 UTC string."""
    keepa_epoch = datetime(2011, 1, 1, tzinfo=timezone.utc)
    dt_object = keepa_epoch + timedelta(minutes=keepa_minutes)
    return dt_object.isoformat()

def main():
    load_dotenv()
    api_key = os.getenv("KEEPA_API_KEY")
    
    print("--- Inspecting Live Deal Stream vs Watermark ---")
    
    # 1. Get Current Watermark
    wm_iso = load_watermark()
    print(f"Current DB Watermark: {wm_iso}")
    
    # 2. Fetch Page 0
    print("Fetching Page 0...")
    data, consumed, left = fetch_deals_for_deals(0, api_key, sort_type=4)
    
    if not data or 'deals' not in data or not data['deals']['dr']:
        print("No deals returned.")
        return

    deals = data['deals']['dr']
    print(f"Returned {len(deals)} deals.")
    
    # 3. Analyze Timestamps
    first_deal = deals[0]
    last_deal = deals[-1]
    
    first_iso = _convert_keepa_time_to_iso(first_deal['lastUpdate'])
    last_iso = _convert_keepa_time_to_iso(last_deal['lastUpdate'])
    
    print(f"Newest Deal (Top of Page 0): {first_iso} (ASIN: {first_deal.get('asin')})")
    print(f"Oldest Deal (Bottom of Page 0): {last_iso}")
    
    if wm_iso and first_iso < wm_iso:
        print("\nCRITICAL FINDING: The NEWEST deal from API is OLDER than the Watermark.")
        print("This explains why the Ingestor stops immediately.")
        print("Recommendation: Rewind watermark further.")
    elif wm_iso and last_iso > wm_iso:
        print("\nSTATUS: Healthy gap. Page 0 is entirely newer than watermark.")
    else:
        print("\nSTATUS: Overlap. Some deals on Page 0 are newer, some older.")
        
    # Check specifically for the 'blocker' deal if possible
    # We can't search by ASIN in the list easily unless we iterate
    blocker_asin = '8804520469'
    for d in deals:
        if d.get('asin') == blocker_asin:
            d_iso = _convert_keepa_time_to_iso(d['lastUpdate'])
            print(f"\nFound Blocker ASIN {blocker_asin}!")
            print(f"Timestamp: {d_iso}")
            if wm_iso and d_iso <= wm_iso:
                print("Confirmed: This deal is older/equal to watermark -> STOP TRIGGER.")

if __name__ == "__main__":
    main()
