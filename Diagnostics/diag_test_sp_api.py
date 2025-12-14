import sys
import os
import logging
from datetime import datetime

# Add parent dir to path to import keepa_deals
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import sqlite3
from keepa_deals.db_utils import DB_PATH, get_all_user_credentials
from keepa_deals.sp_api_tasks import _refresh_sp_api_token
from keepa_deals.amazon_sp_api import check_restrictions

# Configure logging to stdout
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    print("--- Starting Diagnostic: SP-API Restriction Check ---")

    # 1. Check Env Vars
    print(f"Checking Environment Variables...")
    cid = os.getenv("SP_API_CLIENT_ID")
    csecret = os.getenv("SP_API_CLIENT_SECRET")
    if not cid or not csecret:
        print("ERROR: SP_API_CLIENT_ID or SP_API_CLIENT_SECRET missing in environment.")
        return
    print("Environment variables present.")

    # 2. Check DB Credentials
    print(f"Checking Database Credentials in {DB_PATH}...")
    creds = get_all_user_credentials()
    if not creds:
        print("ERROR: No user credentials found in 'user_credentials' table.")
        print("Please Connect/Save Settings via the Web UI first.")
        return

    user_id = creds[0]['user_id']
    refresh_token = creds[0]['refresh_token']
    print(f"Found credentials for User ID: {user_id}")

    # 3. Test Token Refresh
    print("Testing Token Refresh...")
    access_token = _refresh_sp_api_token(refresh_token)
    if not access_token:
        print("ERROR: Failed to generate Access Token. Check your Refresh Token or Client Secret.")
        return
    print("Successfully generated Access Token.")

    # 4. Fetch 5 ASINs
    print("Fetching 5 ASINs from database...")
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ASIN FROM deals GROUP BY ASIN ORDER BY MAX(id) DESC LIMIT 5")
            asins = [row[0] for row in cursor.fetchall()]
    except Exception as e:
        print(f"ERROR reading from database: {e}")
        return

    if not asins:
        print("ERROR: No deals found in database to check.")
        return

    print(f"Testing restriction check for ASINs: {asins}")

    # 5. Call API
    print("Calling SP-API check_restrictions (this mimics the backend task)...")
    try:
        results = check_restrictions(asins, access_token, user_id)
    except Exception as e:
        print(f"ERROR calling check_restrictions: {e}")
        return

    # 6. Report Results
    print("\n--- Results ---")
    for asin, res in results.items():
        restricted_status = "RESTRICTED" if res['is_restricted'] else "Allowed"
        url_msg = f" (Apply: {res['approval_url']})" if res['approval_url'] else ""
        print(f"ASIN: {asin} -> {restricted_status}{url_msg}")

    print("\n--- Diagnostic Complete ---")
    print("If you see results above, the API and Credentials are working.")
    print("If the Dashboard is not updating, ensure the Celery Worker is running and check 'celery_worker.log'.")

if __name__ == "__main__":
    main()
