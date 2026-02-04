import os
import sys
import requests
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from keepa_deals.db_utils import get_all_user_credentials
from keepa_deals.sp_api_tasks import _refresh_sp_api_token

def check_auth():
    logger.info("Starting SP-API Authentication Diagnostic...")

    # Check Environment Variables
    sp_api_url = os.getenv("SP_API_URL")
    client_id = os.getenv("SP_API_CLIENT_ID")

    logger.info(f"SP_API_URL: {sp_api_url}")
    if not sp_api_url:
        logger.warning("SP_API_URL is not set. Defaulting to Sandbox.")
    elif "sandbox" in sp_api_url:
        logger.info("Configured for SANDBOX.")
    else:
        logger.info("Configured for PRODUCTION.")

    if not client_id:
        logger.error("SP_API_CLIENT_ID is missing in .env!")
        return

    logger.info(f"Client ID: {client_id[:10]}...")

    # Get Credentials from DB
    creds = get_all_user_credentials()
    if not creds:
        logger.error("No user credentials found in database 'deals.db'. Please connect via Settings page.")
        return

    logger.info(f"Found {len(creds)} user credential(s) in database.")

    for c in creds:
        user_id = c['user_id']
        refresh_token = c['refresh_token']
        logger.info(f"\nTesting User: {user_id}")

        # 1. Refresh Token
        access_token = _refresh_sp_api_token(refresh_token)
        if not access_token:
            logger.error("Failed to refresh token. The Refresh Token might be invalid or mismatched with Client ID.")
            continue

        logger.info("Access Token generated successfully.")

        # 2. Test Production
        # Use marketplaceParticipations as a generic authenticated endpoint
        mp_url_prod = "https://sellingpartnerapi-na.amazon.com/sellers/v1/marketplaceParticipations"

        logger.info(f"Testing Production Endpoint: {mp_url_prod}")
        headers = {
            'x-amz-access-token': access_token,
            'Content-Type': 'application/json',
            'User-Agent': 'AgentArbitrage/1.0 (Language=Python/3.12)'
        }

        r_prod = None
        try:
            r_prod = requests.get(mp_url_prod, headers=headers)
            logger.info(f"Production Status: {r_prod.status_code}")

            if r_prod.status_code == 200:
                logger.info("SUCCESS: Token is valid for Production.")
            elif r_prod.status_code == 403:
                logger.error("FAILURE: 403 Forbidden on Production.")
            else:
                logger.warning(f"Unexpected status on Production: {r_prod.status_code}")

        except Exception as e:
            logger.error(f"Error calling Production: {e}")

        # 3. Test Sandbox
        mp_url_sb = "https://sandbox.sellingpartnerapi-na.amazon.com/sellers/v1/marketplaceParticipations"
        logger.info(f"Testing Sandbox Endpoint: {mp_url_sb}")

        r_sb = None
        try:
            r_sb = requests.get(mp_url_sb, headers=headers)
            logger.info(f"Sandbox Status: {r_sb.status_code}")

            if r_sb.status_code == 200:
                logger.info("SUCCESS: Token is valid for Sandbox.")
            elif r_sb.status_code == 403:
                logger.error("FAILURE: 403 Forbidden on Sandbox.")
            else:
                logger.warning(f"Unexpected status on Sandbox: {r_sb.status_code}")

        except Exception as e:
            logger.error(f"Error calling Sandbox: {e}")

        # Analysis
        if r_prod and r_sb:
            if r_prod.status_code == 403 and r_sb.status_code == 200:
                logger.critical("\n*** DIAGNOSIS ***")
                logger.critical("Your credentials are for the SANDBOX environment, but you are trying to use them on Production.")
                logger.critical("Action Required: Update .env with Production Client ID/Secret AND regenerate the Refresh Token.")

if __name__ == "__main__":
    check_auth()
