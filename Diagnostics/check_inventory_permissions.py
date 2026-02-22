
import os
import requests
import json
import logging
import time
from datetime import datetime
from dotenv import load_dotenv

# Load .env explicitly
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(dotenv_path)

# Configure logging to console
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration ---
# Read from environment
SELLER_ID = os.getenv("SP_API_SELLER_ID", "")
REFRESH_TOKEN = os.getenv("SP_API_REFRESH_TOKEN", "")
CLIENT_ID = os.getenv("SP_API_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("SP_API_CLIENT_SECRET", "")

# SP-API Endpoints
TOKEN_URL = "https://api.amazon.com/auth/o2/token"
SP_API_BASE_URL = os.getenv("SP_API_URL", "https://sellingpartnerapi-na.amazon.com")

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

def check_single_report_permission(access_token, report_type):
    """Checks permission for a single report type, and if possible, downloads a snippet."""
    logger.info(f"Checking permission for '{report_type}'...")

    url = f"{SP_API_BASE_URL}/reports/2021-06-30/reports"

    headers = {
        'x-amz-access-token': access_token,
        'Content-Type': 'application/json',
        'User-Agent': 'AgentArbitrageDiagnostic/1.0'
    }

    payload = {
        "reportType": report_type,
        "marketplaceIds": ["ATVPDKIKX0DER"], # US Marketplace
        # Request data for last 24 hours to ensure freshness
        "dataStartTime": datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    }

    try:
        response = requests.post(url, headers=headers, json=payload)

        if response.status_code == 202:
            report_id = response.json().get('reportId')
            logger.info(f"SUCCESS (202 Accepted): Permission Verified for {report_type}. Report ID: {report_id}")

            # --- Attempt Download Preview ---
            preview = attempt_download_preview(access_token, report_id)
            return True, f"Report generated. Preview:\n{preview}"

        elif response.status_code == 403:
            logger.error(f"FAILURE (403 Forbidden): Permission Denied for {report_type}.")
            logger.error(f"Response Body: {response.text}")
            return False, "403 Forbidden"

        elif response.status_code == 401:
            logger.error(f"FAILURE (401 Unauthorized): Authentication Failed.")
            return False, "401 Unauthorized"

        else:
            logger.error(f"FAILURE ({response.status_code}): Unexpected status for {report_type}.")
            logger.error(f"Response: {response.text}")
            return False, f"{response.status_code} Error"

    except requests.exceptions.RequestException as e:
        logger.error(f"Network Error: {e}")
        return False, str(e)

def attempt_download_preview(access_token, report_id):
    """Polls for report completion and downloads a snippet."""
    logger.info(f"Polling for report {report_id} completion (max 2 mins)...")

    url = f"{SP_API_BASE_URL}/reports/2021-06-30/reports/{report_id}"
    headers = {'x-amz-access-token': access_token}

    start_time = time.time()
    while time.time() - start_time < 120: # 2 mins timeout
        try:
            resp = requests.get(url, headers=headers)
            if resp.status_code != 200:
                return f"Error checking status: {resp.status_code}"

            data = resp.json()
            status = data['processingStatus']

            if status == 'DONE':
                document_id = data['reportDocumentId']
                return download_snippet(access_token, document_id)
            elif status in ['CANCELLED', 'FATAL']:
                return f"Report processing failed: {status}"

            time.sleep(10)
        except Exception as e:
            return f"Polling error: {str(e)}"

    return "Polling timed out."

def download_snippet(access_token, document_id):
    """Downloads the document and returns first 5 lines."""
    url = f"{SP_API_BASE_URL}/reports/2021-06-30/documents/{document_id}"
    headers = {'x-amz-access-token': access_token}

    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            return f"Error getting document URL: {resp.status_code}"

        data = resp.json()
        download_url = data['url']
        compression = data.get('compressionAlgorithm')

        logger.info("Downloading document content...")
        file_resp = requests.get(download_url)
        content = file_resp.content

        if compression == 'GZIP':
            import gzip
            content = gzip.decompress(content)

        text = content.decode('utf-8', errors='replace')
        lines = text.split('\n')[:5]
        return "\n".join(lines)

    except Exception as e:
        return f"Download error: {str(e)}"

def main():
    print("==================================================")
    print("   Agent Arbitrage: SP-API Permission Diagnostic  ")
    print("==================================================")

    # Check for credentials
    if not all([CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN]):
        print("ERROR: Missing Credentials in environment variables.")
        print("Diagnostic script updated to load .env automatically.")
        print(f"Loaded .env from: {dotenv_path}")
        print("Please ensure SP_API_CLIENT_ID, SP_API_CLIENT_SECRET, and SP_API_REFRESH_TOKEN are set in your .env file.")
        return

    # 1. Get Access Token
    access_token = get_lwa_access_token(CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN)

    if not access_token:
        print("\n[RESULT] FAILURE: Could not obtain Access Token. Check Client ID/Secret and Refresh Token.")
        return

    # 2. Check Permissions
    reports_to_check = [
        "GET_MERCHANT_LISTINGS_ALL_DATA",
        "GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA",
        "GET_AFN_INVENTORY_DATA"
    ]

    results = {}

    for report_type in reports_to_check:
        success, msg = check_single_report_permission(access_token, report_type)
        results[report_type] = (success, msg)

    print("\n================ REPORT SUMMARY ================")
    all_success = True
    for r_type, (success, msg) in results.items():
        status = "PASSED" if success else "FAILED"
        print(f"Report: {r_type}")
        print(f"Status: {status}")
        print(f"Details: {msg}")
        print("------------------------------------------------")
        if not success:
            all_success = False

    if all_success:
        print("\n[OVERALL RESULT] SUCCESS: All permissions verified.")
    else:
        print("\n[OVERALL RESULT] FAILURE: Some permissions are missing or reports failed.")
        print("Please confirm in Seller Central that the 'Inventory and Order Tracking' role is active.")

if __name__ == "__main__":
    main()
