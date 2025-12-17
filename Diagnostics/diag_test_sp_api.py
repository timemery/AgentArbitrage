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
        print("WARNING: No deals found in database. Using fallback ASINs for testing.")
        # Use a real ASIN (Fire TV Stick) and a dummy one
        asins = ['B075CYMYK6', 'B000000000']

    print(f"Testing restriction check for ASINs: {asins}")

    # 5. Test Basic Connectivity (Marketplace Participations)
    import requests

    # Clean token just in case
    access_token = access_token.strip()

    # A. Production
    print("Testing Basic Connectivity (Production Marketplace Participations)...")
    try:
        mp_url = "https://sellingpartnerapi-na.amazon.com/sellers/v1/marketplaceParticipations"
        headers = {
            'x-amz-access-token': access_token,
            'Content-Type': 'application/json',
            'User-Agent': 'AgentArbitrage/1.0 (Language=Python/3.12)'
        }
        mp_res = requests.get(mp_url, headers=headers)
        print(f"Production Status: {mp_res.status_code}")
        if mp_res.status_code == 200:
            print("SUCCESS: Token is valid for PRODUCTION.")
        else:
            print(f"FAILURE (Production): {mp_res.text}")
    except Exception as e:
        print(f"ERROR calling Production: {e}")

    # B. Sandbox
    print("\nTesting Basic Connectivity (SANDBOX Marketplace Participations)...")
    try:
        sb_url = "https://sandbox.sellingpartnerapi-na.amazon.com/sellers/v1/marketplaceParticipations"
        headers = {
            'x-amz-access-token': access_token,
            'Content-Type': 'application/json',
            'User-Agent': 'AgentArbitrage/1.0 (Language=Python/3.12)'
        }
        sb_res = requests.get(sb_url, headers=headers)
        print(f"Sandbox Status: {sb_res.status_code}")
        if sb_res.status_code == 200:
            print("SUCCESS: Token is valid for SANDBOX.")
        else:
            print(f"FAILURE (Sandbox): {sb_res.text}")
    except Exception as e:
        print(f"ERROR calling Sandbox: {e}")

    # 6. Call API (Restrictions)
    print("\nCalling SP-API check_restrictions (this mimics the backend task)...")
    try:
        results = check_restrictions(asins, access_token, user_id)
    except Exception as e:
        print(f"ERROR calling check_restrictions: {e}")
        return

    # 7. Report Results
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
