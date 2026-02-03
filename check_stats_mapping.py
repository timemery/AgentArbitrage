import os
import logging
from dotenv import load_dotenv
from keepa_deals.keepa_api import fetch_current_stats_batch
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

KEEPA_EPOCH = datetime(2011, 1, 1)

def keepa_time_to_str(kt):
    if not kt or kt < 100000: return "Invalid"
    dt = KEEPA_EPOCH + timedelta(minutes=kt)
    return dt.strftime('%Y-%m-%d %H:%M')

def main():
    load_dotenv()
    api_key = os.getenv("KEEPA_API_KEY")
    asins = ["013335587X", "9997526848", "0357986342"]

    print(f"Fetching stats for: {asins}")
    data, _, _, _ = fetch_current_stats_batch(api_key, asins, days=180)

    for p in data['products']:
        asin = p.get('asin')
        print(f"\n--- Analysis for {asin} ---")

        # Stats Current
        stats = p.get('stats', {})
        current = stats.get('current', [])

        # Indices: 0=Amazon, 1=New, 2=Used
        amz = current[0] if len(current) > 0 else -1
        new = current[1] if len(current) > 1 else -1
        used = current[2] if len(current) > 2 else -1

        print(f"Stats.Current:")
        print(f"  [0] Amazon: {amz/100:.2f}")
        print(f"  [1] New:    {new/100:.2f}")
        print(f"  [2] Used:   {used/100:.2f}")

        # Check Update Times
        print(f"Last Update (Product): {keepa_time_to_str(p.get('lastUpdate'))}")
        print(f"Last Offers Update:    {keepa_time_to_str(stats.get('lastOffersUpdate'))}")

if __name__ == "__main__":
    main()
