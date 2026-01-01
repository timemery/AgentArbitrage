import os
import sys
import logging
import sqlite3
from dotenv import load_dotenv

# mimic wsgi_handler.py logging setup
log_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'reproduce.log')
logging.basicConfig(filename=log_file_path, level=logging.DEBUG, format='%(asctime)s %(levelname)s %(name)s %(threadName)s : %(message)s')
logger = logging.getLogger('app')
logger.addHandler(logging.StreamHandler(sys.stdout)) # Also print to stdout

logger.info("Starting reproduction script with STRINGS")

# mimic wsgi_handler.py environment loading
dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(dotenv_path)

# Verify environment variable
xai_token = os.getenv("XAI_TOKEN")
if xai_token:
    logger.info(f"Environment variable XAI_TOKEN found.")
else:
    logger.error("Environment variable XAI_TOKEN NOT found after load_dotenv")

from keepa_deals.ava_advisor import generate_ava_advice

# Dummy deal data with STRINGS to test crash fix
deal_data = {
    'Title': 'Test Book Title',
    'Best_Price': "20.00", # String!
    '1yr_Avg': "$30.00", # String with $
    'Percent_Down': 33,
    'Sales_Rank_Current': 50000,
    'Sales_Rank_365_days_avg': 60000,
    'Detailed_Seasonality': 'Textbook',
    'Profit': 10.00,
    'Margin': 50,
    'Trend': 'Flat',
    'Sales_Rank_Drops_last_365_days': 12
}

logger.info("Calling generate_ava_advice with string data...")
try:
    # Mimic wsgi_handler call
    advice = generate_ava_advice(deal_data, xai_api_key=xai_token)
    logger.info(f"Advice received: {advice}")
    print(f"Advice: {advice}")
except Exception as e:
    logger.error(f"Error calling generate_ava_advice: {e}", exc_info=True)
    print("CRASHED!")
