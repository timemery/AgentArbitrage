import sys
import os
import time
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals.db_utils import save_watermark, load_watermark, create_system_state_table_if_not_exists
from keepa_deals.keepa_api import fetch_deals_for_deals

# Version Check: Smart Watermark Reset Tool
def _convert_keepa_time_to_iso(keepa_minutes):
    """Converts Keepa time (minutes since 2000-01-01) to ISO 8601 UTC string."""
    keepa_epoch = datetime(2000, 1, 1, tzinfo=timezone.utc)
    dt_object = keepa_epoch + timedelta(minutes=keepa_minutes)
    return dt_object.isoformat()

def main():
    load_dotenv()
    print("--- Smart Watermark Reset Tool ---")

    # Ensure DB table exists (crucial for fresh envs)
    create_system_state_table_if_not_exists()

    api_key = os.getenv("KEEPA_API_KEY")
    if not api_key:
        print("Error: KEEPA_API_KEY not found in .env")
        return

    print("Fetching newest deals from Keepa to determine data age...")
    # Fetch Page 0, Sort 4 (Last Update)
    response, _, _ = fetch_deals_for_deals(0, api_key, sort_type=4)

    if not response or 'deals' not in response or not response['deals']['dr']:
        print("Error: Could not fetch deals from Keepa. Cannot determine optimal watermark.")
        return

    # Find the newest deal timestamp
    newest_deal = response['deals']['dr'][0]
    newest_timestamp = newest_deal.get('lastUpdate')

    if not newest_timestamp:
        print("Error: Newest deal has no 'lastUpdate' field.")
        return

    newest_iso = _convert_keepa_time_to_iso(newest_timestamp)
    print(f"Newest Deal Found: {newest_iso} (Keepa Time: {newest_timestamp})")

    # Set watermark to 24 hours before the newest deal
    # This ensures we fetch exactly one day of "recent" data relative to the actual dataset.
    target_timestamp = newest_timestamp - (24 * 60) # Subtract 24 hours in minutes
    target_iso = _convert_keepa_time_to_iso(target_timestamp)

    print(f"\nCalculated Target Watermark: {target_iso}")
    print(f"(This is 24 hours prior to the newest available deal)")

    current_watermark = load_watermark()
    print(f"Current Watermark: {current_watermark}")

    print(f"\nResetting watermark to: {target_iso}")
    save_watermark(target_iso)

    # Verify
    verify_watermark = load_watermark()
    print(f"New Watermark in DB: {verify_watermark}")
    print("-----------------------------------")
    print("Watermark reset complete.")
    print("The 'update_recent_deals' task will now fetch deals from the last 24 hours relative to the data.")

if __name__ == "__main__":
    main()
