
import os
import requests
import json
import logging
import time
import sqlite3
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

# Database Path
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'deals.db')

def get_db_credentials():
    """Fetches credentials from the database as a fallback."""
    if not os.path.exists(DB_PATH):
        logger.warning(f"Database not found at {DB_PATH}")
        return None, None

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_credentials'")
            if not cursor.fetchone():
                return None, None
            cursor.execute("SELECT user_id, refresh_token FROM user_credentials ORDER BY updated_at DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                return row[0], row[1]
    except Exception:
        pass
    return None, None

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
        return response.json().get('access_token')
    except Exception as e:
        logger.error(f"LWA Token Exchange Failed: {e}")
        return None

def check_single_report_permission(access_token, report_type, use_start_time=False):
    """Checks permission for a single report type, potentially with dataStartTime."""
    logger.info(f"Testing '{report_type}' (StartTime={use_start_time})...")

    url = f"{SP_API_BASE_URL}/reports/2021-06-30/reports"
    headers = {
        'x-amz-access-token': access_token,
        'Content-Type': 'application/json',
        'User-Agent': 'AgentArbitrageDiagnostic/1.0'
    }

    # IMPORTANT: GET_AFN_INVENTORY_DATA requires slightly different parameters
    # It does NOT use marketplaceIds in the body for some versions, but usually does.
    # However, GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA definitely requires marketplaceIds.

    payload = {
        "reportType": report_type,
        "marketplaceIds": ["ATVPDKIKX0DER"], # US Marketplace
    }

    if use_start_time:
        # dataStartTime: 30 days ago
        start_date = datetime.utcnow() - timedelta(days=30)
        payload["dataStartTime"] = start_date.isoformat() + "Z"

    try:
        response = requests.post(url, headers=headers, json=payload)

        if response.status_code == 202:
            report_id = response.json().get('reportId')
            logger.info(f"SUCCESS (202 Accepted): ID: {report_id}")
            preview = attempt_download_preview(access_token, report_id)
            return True, f"Report generated. Preview:\n{preview}"

        elif response.status_code == 400:
             logger.error(f"FAILURE (400 Bad Request): {response.text}")
             return False, f"400 Bad Request: {response.text}"

        elif response.status_code == 403:
            logger.error(f"FAILURE (403 Forbidden): Permission Denied.")
            return False, "403 Forbidden"

        else:
            logger.error(f"FAILURE ({response.status_code}): {response.text}")
            return False, f"{response.status_code} Error"

    except Exception as e:
        logger.error(f"Network Error: {e}")
        return False, str(e)

def attempt_download_preview(access_token, report_id):
    """Polls for report completion and downloads a snippet."""
    logger.info(f"Polling for report {report_id} completion (max 2 mins)...")
    url = f"{SP_API_BASE_URL}/reports/2021-06-30/reports/{report_id}"
    headers = {'x-amz-access-token': access_token}

    start_time = time.time()
    while time.time() - start_time < 120:
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
    url = f"{SP_API_BASE_URL}/reports/2021-06-30/documents/{document_id}"
    headers = {'x-amz-access-token': access_token}
    try:
        resp = requests.get(url, headers=headers)
        if resp.status_code != 200:
            return f"Error getting document URL: {resp.status_code}"

        data = resp.json()
        download_url = data['url']
        compression = data.get('compressionAlgorithm')

        file_resp = requests.get(download_url)
        content = file_resp.content

        if compression == 'GZIP':
            import gzip
            content = gzip.decompress(content)

        text = content.decode('utf-8', errors='replace')
        return "\n".join(text.split('\n')[:5])
    except Exception as e:
        return f"Download error: {str(e)}"

def main():
    print("=== FBA Report Diagnostic ===")

    # Credentials Logic (Simplified from check_inventory_permissions.py)
    global SELLER_ID, REFRESH_TOKEN, CLIENT_ID, CLIENT_SECRET

    # Try to load from env first, then DB
    if not REFRESH_TOKEN:
        db_uid, db_rt = get_db_credentials()
        if db_rt:
            REFRESH_TOKEN = db_rt
            if not SELLER_ID: SELLER_ID = db_uid

    # Interactive prompts if still missing
    if not CLIENT_ID:
        print("Missing CLIENT_ID in environment.")
        CLIENT_ID = input("Client ID: ").strip()
    if not CLIENT_SECRET:
        print("Missing CLIENT_SECRET in environment.")
        CLIENT_SECRET = input("Client Secret: ").strip()
    if not REFRESH_TOKEN:
        print("Missing REFRESH_TOKEN in environment or DB.")
        REFRESH_TOKEN = input("Refresh Token: ").strip()

    if not all([CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN]):
        print("Missing credentials. Aborting.")
        return

    token = get_lwa_access_token(CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN)
    if not token:
        print("Failed to get Access Token.")
        return

    # Test Reports
    tests = [
        ("GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA", False), # Current Logic (Fails FATAL)
        ("GET_FBA_MYI_ALL_INVENTORY_DATA", False),         # Include suppressed?
        ("GET_AFN_INVENTORY_DATA", False),                  # FBA Multi-Country
        # ("GET_FBA_MYI_UNSUPPRESSED_INVENTORY_DATA", True),  # With DataStartTime? (Usually not supported for this type)
    ]

    for r_type, use_time in tests:
        print(f"\n--- Testing {r_type} (Time={use_time}) ---")
        success, msg = check_single_report_permission(token, r_type, use_time)
        print(f"Result: {'PASSED' if success else 'FAILED'}")
        print(f"Details: {msg}")
        if success and "FATAL" not in msg:
            print(">>> FOUND WORKING REPORT TYPE! <<<")
            # We could break here, but let's see all options.

if __name__ == "__main__":
    main()
