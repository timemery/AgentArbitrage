"""
This module encapsulates all interactions with the Amazon Selling Partner API (SP-API).
"""

import time
import logging
import os
import requests
from requests_aws4auth import AWS4Auth
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

# Constants for the SP-API
SP_API_BASE_URL_NA = "https://sellingpartnerapi-na.amazon.com"
MARKETPLACE_ID_US = "ATVPDKIKX0DER"


def check_restrictions(asins: list[str], access_token: str, seller_id: str) -> dict:
    """
    Checks the restriction status for a list of ASINs using the real Amazon SP-API.
    Signs the request using AWS SigV4.

    Args:
        asins: A list of ASIN strings to check.
        access_token: The OAuth access token for the SP-API.
        seller_id: The selling partner ID for the user.

    Returns:
        A dictionary where keys are ASINs and values are another dictionary
        with 'is_restricted' (bool) and 'approval_url' (str or None).
    """
    logger.info(f"Starting real SP-API restriction check for {len(asins)} ASINs for seller {seller_id}.")
    results = {}

    # --- AWS SigV4 Setup ---
    aws_access_key = os.getenv("SP_API_AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("SP_API_AWS_SECRET_KEY")
    aws_region = os.getenv("SP_API_AWS_REGION", "us-east-1")
    service = 'execute-api'

    if not aws_access_key or not aws_secret_key:
        logger.error("Missing AWS Credentials (SP_API_AWS_ACCESS_KEY_ID / SP_API_AWS_SECRET_KEY). Cannot sign request.")
        # If credentials are missing, we cannot proceed. Mark as failure/restricted.
        return {asin: {"is_restricted": True, "approval_url": None} for asin in asins}

    auth = AWS4Auth(aws_access_key, aws_secret_key, aws_region, service)

    headers = {
        'x-amz-access-token': access_token,
        'Content-Type': 'application/json'
    }

    # Use a session for efficiency and to attach auth
    session = requests.Session()
    session.auth = auth
    session.headers.update(headers)

    for asin in asins:
        # Respect the official 1 request/second rate limit with a small buffer
        time.sleep(1.1)

        params = {
            'asin': asin,
            'sellerId': seller_id,
            'marketplaceIds': MARKETPLACE_ID_US
        }

        url = f"{SP_API_BASE_URL_NA}/listings/2021-08-01/restrictions"

        try:
            response = session.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            restrictions = data.get('restrictions', [])
            is_restricted = bool(restrictions)  # If the list is not empty, it's restricted

            approval_url = None
            # Attempt to find a direct approval link from the API response
            if is_restricted:
                # Default fallback: Generic Seller Central add product page
                approval_url = f"https://sellercentral.amazon.com/product-search/search?q={asin}"

                # Try to find a specific deep link if available
                if restrictions[0].get('links', {}).get('actions'):
                    for action in restrictions[0]['links']['actions']:
                        if action.get('verb') == 'GET' and 'approval' in action.get('uri', ''):
                            approval_url = action['uri']
                            break

            results[asin] = {
                "is_restricted": is_restricted,
                "approval_url": approval_url
            }
            logger.info(f"ASIN {asin}: is_restricted={is_restricted}")

        except requests.exceptions.HTTPError as e:
            # Enhanced error logging
            error_body = e.response.text
            logger.error(f"SP-API error for ASIN {asin}: Status {e.response.status_code}, Body: {error_body}")
            # Default to restricted on error to be safe
            results[asin] = {"is_restricted": True, "approval_url": None}
        except Exception as e:
            logger.error(f"Unexpected error checking ASIN {asin}: {e}", exc_info=True)
            results[asin] = {"is_restricted": True, "approval_url": None}

    logger.info("SP-API restriction check complete.")
    return results
