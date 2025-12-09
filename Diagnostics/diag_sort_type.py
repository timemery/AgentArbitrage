import os
import sys
import logging
import json

# Configure logging to see output from the task
logging.basicConfig(level=logging.INFO)

# Add the project root to the Python path to allow for correct module resolution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

from keepa_deals.keepa_api import fetch_deals_for_deals
from dotenv import load_dotenv

if __name__ == "__main__":
    print("--- Running diagnostic for Keepa API sortType ---")

    # Load environment variables from the root .env file
    dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(dotenv_path):
        load_dotenv(dotenv_path=dotenv_path)
        print("Loaded environment variables from .env file.")
    else:
        print("Warning: .env file not found. The script may fail if it relies on environment variables.")
        exit()

    api_key = os.getenv("KEEPA_API_KEY")

    for sort_type in range(11):
        try:
            print(f"--- Testing sortType: {sort_type} ---")
            deal_response, _, _ = fetch_deals_for_deals(0, api_key, sort_type=sort_type)

            if deal_response and 'deals' in deal_response and deal_response['deals']['dr']:
                deals = deal_response['deals']['dr']
                print(f"Found {len(deals)} deals.")
                for i, deal in enumerate(deals[:5]):
                    print(f"  Deal {i+1}: lastUpdate = {deal.get('lastUpdate')}")
            else:
                print("  No deals found or error in response.")
        except Exception as e:
            print(f"  An error occurred: {e}")
