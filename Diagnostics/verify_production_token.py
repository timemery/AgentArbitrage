import os
import sys
import requests
import logging
from dotenv import load_dotenv

# Add parent dir
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load env
load_dotenv()

from keepa_deals.sp_api_tasks import _refresh_sp_api_token

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def verify_token(refresh_token):
    print(f"--- Verifying Refresh Token against PRODUCTION ---")

    # 1. Get Access Token
    try:
        # Note: _refresh_sp_api_token uses SP_API_CLIENT_ID/SECRET from env
        access_token = _refresh_sp_api_token(refresh_token)
    except Exception as e:
        print(f"ERROR: Failed to refresh token: {e}")
        return False

    if not access_token:
        print("ERROR: API returned no access token.")
        return False

    print("Access Token generated successfully.")

    # 2. Test Production Endpoint
    mp_url = "https://sellingpartnerapi-na.amazon.com/sellers/v1/marketplaceParticipations"
    headers = {
        'x-amz-access-token': access_token,
        'Content-Type': 'application/json',
        'User-Agent': 'AgentArbitrage/1.0 (Language=Python/3.12)'
    }

    try:
        print(f"Requesting: {mp_url}")
        res = requests.get(mp_url, headers=headers)
        print(f"Status Code: {res.status_code}")

        if res.status_code == 200:
            print("SUCCESS! Token is valid for Production.")
            return True
        elif res.status_code == 403:
            print("FAILURE: 403 Forbidden. This token is likely Sandbox-only or missing permissions.")
            return False
        else:
            print(f"FAILURE: Unexpected status {res.status_code}. Body: {res.text}")
            return False

    except Exception as e:
        print(f"ERROR during request: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        token = sys.argv[1]
    else:
        token = os.getenv("TEST_REFRESH_TOKEN")

    if not token:
        print("Usage: python verify_production_token.py <REFRESH_TOKEN>")
        sys.exit(1)

    verify_token(token)
