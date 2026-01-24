import sys
import os

# Add the project root to sys.path to allow importing modules
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals.db_utils import save_watermark, load_watermark
from datetime import datetime, timedelta, timezone

def main():
    print("--- Manual Watermark Reset Tool ---")
    current_watermark = load_watermark()
    print(f"Current Watermark: {current_watermark}")

    # Set to yesterday
    yesterday = datetime.now(timezone.utc) - timedelta(days=1)
    new_watermark = yesterday.isoformat()

    print(f"Resetting watermark to: {new_watermark}")
    save_watermark(new_watermark)

    # Verify
    verify_watermark = load_watermark()
    print(f"New Watermark in DB: {verify_watermark}")
    print("-----------------------------------")
    print("Watermark reset complete. The 'update_recent_deals' task should now skip the backlog.")

if __name__ == "__main__":
    main()
