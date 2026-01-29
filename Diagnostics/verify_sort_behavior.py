import sys
import os
import logging
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from keepa_deals.keepa_api import fetch_deals_for_deals
from keepa_deals.token_manager import TokenManager

def _convert_keepa_time_to_iso(keepa_minutes):
    """Converts Keepa time (minutes since 2011-01-01) to ISO 8601 UTC string."""
    keepa_epoch = datetime(2011, 1, 1, tzinfo=timezone.utc)
    dt_object = keepa_epoch + timedelta(minutes=keepa_minutes)
    return dt_object

def test_sort_behavior():
    api_key = os.getenv("KEEPA_API_KEY")
    if not api_key:
        logger.error("KEEPA_API_KEY not set.")
        return

    tm = TokenManager(api_key)
    tm.sync_tokens()

    logger.info(f"Initial Tokens: {tm.tokens}")

    # Test Sort 0 (Sales Rank)
    logger.info("--- Testing Sort Type 0 (Sales Rank) ---")
    try:
        resp0, consumed, left = fetch_deals_for_deals(0, api_key, sort_type=0, token_manager=tm)
        if resp0 and 'deals' in resp0 and resp0['deals']['dr']:
            deals = resp0['deals']['dr']
            logger.info(f"Fetched {len(deals)} deals.")
            for i, d in enumerate(deals[:3]):
                kt = d.get('lastUpdate')
                iso = _convert_keepa_time_to_iso(kt)
                age = datetime.now(timezone.utc) - iso
                logger.info(f"Deal {i} (Sort 0): Update={iso}, Age={age}")
        else:
            logger.warning("No deals returned for Sort 0")
    except Exception as e:
        logger.error(f"Error fetching Sort 0: {e}")

    # Test Sort 4 (Last Update)
    logger.info("--- Testing Sort Type 4 (Last Update) ---")
    try:
        resp4, consumed, left = fetch_deals_for_deals(0, api_key, sort_type=4, token_manager=tm)
        if resp4 and 'deals' in resp4 and resp4['deals']['dr']:
            deals = resp4['deals']['dr']
            logger.info(f"Fetched {len(deals)} deals.")
            for i, d in enumerate(deals[:3]):
                kt = d.get('lastUpdate')
                iso = _convert_keepa_time_to_iso(kt)
                age = datetime.now(timezone.utc) - iso
                logger.info(f"Deal {i} (Sort 4): Update={iso}, Age={age}")
        else:
            logger.warning("No deals returned for Sort 4")
    except Exception as e:
        logger.error(f"Error fetching Sort 4: {e}")

if __name__ == "__main__":
    test_sort_behavior()
