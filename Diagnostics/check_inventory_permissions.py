
import os
import requests
import json
import logging
from datetime import datetime

# Configure logging to console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration ---
# Hardcoded for direct testing or read from environment if available.
# In a real user scenario, they would edit this file or export these vars.
SELLER_ID = os.getenv("SP_API_SELLER_ID", "")
REFRESH_TOKEN = os.getenv("SP_API_REFRESH_TOKEN", "")
CLIENT_ID = os.getenv("SP_API_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("SP_API_CLIENT_SECRET", "")

# SP-API Endpoints
TOKEN_URL = "https://api.amazon.com/auth/o2/token"
SP_API_BASE_URL = "https://sellingpartnerapi-na.amazon.com" # Production

def get_lwa_access_token(client_id, client_secret, refresh_token):
    """Exchanges Refresh Token for LWA Access Token."""
    logger.info("Requesting LWA Access Token...")

    payload = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': client_id,
        'client_secret': client_secret
    }

    try:
        response = requests.post(TOKEN_URL, data=payload)
        response.raise_for_status()
        token_data = response.json()
        logger.info("Successfully obtained LWA Access Token.")
        return token_data.get('access_token')
    except requests.exceptions.HTTPError as e:
        logger.error(f"LWA Token Exchange Failed: {e.response.status_code} - {e.response.text}")
        return None
    except Exception as e:
        logger.error(f"Error getting LWA token: {e}")
        return None

def check_inventory_permission(access_token):
    """
    Attempts to request the GET_MERCHANT_LISTINGS_ALL_DATA report.
    This report type specifically requires the 'Inventory and Order Tracking' role.
    """
    logger.info("Checking permission for 'GET_MERCHANT_LISTINGS_ALL_DATA'...")

    url = f"{SP_API_BASE_URL}/reports/2021-06-30/reports"

    headers = {
        'x-amz-access-token': access_token,
        'Content-Type': 'application/json',
        'User-Agent': 'AgentArbitrageDiagnostic/1.0'
    }

    # Requesting a report for the last 24 hours just to test access
    payload = {
        "reportType": "GET_MERCHANT_LISTINGS_ALL_DATA",
        "marketplaceIds": ["ATVPDKIKX0DER"], # US Marketplace
        "dataStartTime": datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    }

    try:
        response = requests.post(url, headers=headers, json=payload)

        if response.status_code == 202:
            report_id = response.json().get('reportId')
            logger.info(f"SUCCESS (202 Accepted): Permission Verified. Report ID: {report_id}")
            print("\n[RESULT] SUCCESS: Your token HAS the 'Inventory and Order Tracking' permission.")
            return True

        elif response.status_code == 403:
            logger.error(f"FAILURE (403 Forbidden): Permission Denied.")
            logger.error(f"Response Body: {response.text}")
            print("\n[RESULT] FAILURE (403): Your token LACKS the 'Inventory and Order Tracking' role.")
            print("Please confirm in Seller Central that the role is active for your application.")
            return False

        elif response.status_code == 401:
            logger.error(f"FAILURE (401 Unauthorized): Authentication Failed.")
            print("\n[RESULT] FAILURE (401): The Access Token is invalid or expired immediately.")
            return False

        else:
            logger.error(f"FAILURE ({response.status_code}): Unexpected status.")
            logger.error(f"Response: {response.text}")
            print(f"\n[RESULT] FAILURE ({response.status_code}): API request failed unexpectedly.")
            return False

    except requests.exceptions.RequestException as e:
        logger.error(f"Network Error: {e}")
        return False

def main():
    print("==================================================")
    print("   Agent Arbitrage: SP-API Permission Diagnostic  ")
    print("==================================================")

    # Check for credentials
    if not all([CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN]):
        print("ERROR: Missing Credentials in environment variables.")
        print("Please export SP_API_CLIENT_ID, SP_API_CLIENT_SECRET, and SP_API_REFRESH_TOKEN before running.")
        print("Example: export SP_API_CLIENT_ID='amzn1.application...'")
        return

    # 1. Get Access Token
    access_token = get_lwa_access_token(CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN)

    if access_token:
        # 2. Check Permission
        check_inventory_permission(access_token)
    else:
        print("\n[RESULT] FAILURE: Could not obtain Access Token. Check Client ID/Secret and Refresh Token.")

if __name__ == "__main__":
    main()
