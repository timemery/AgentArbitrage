"""
This module encapsulates all interactions with the Amazon Selling Partner API (SP-API).
"""

import time
import logging
import os
import requests
from urllib.parse import urlencode

# Attempt to import AWSSigV4 for signing
try:
    from requests_auth_aws_sigv4 import AWSSigV4
except ImportError:
    AWSSigV4 = None

logger = logging.getLogger(__name__)

# Constants for the SP-API
# Default to Sandbox for Private/Draft apps. Override with SP_API_URL env var for Production.
SP_API_BASE_URL_NA = os.getenv("SP_API_URL", "https://sandbox.sellingpartnerapi-na.amazon.com")
MARKETPLACE_ID_US = "ATVPDKIKX0DER"


def map_condition_to_sp_api(condition_input: str) -> str | None:
    """
    Maps internal condition strings or codes to Amazon SP-API conditionType enum.
    """
    if not condition_input:
        return None

    s = str(condition_input).lower().strip()

    mapping = {
        # Codes (as strings)
        "1": "new_new",
        "2": "used_like_new",
        "3": "used_very_good",
        "4": "used_good",
        "5": "used_acceptable",

        # Full strings (from DB if present)
        "new": "new_new",
        "used - like new": "used_like_new",
        "used - very good": "used_very_good",
        "used - good": "used_good",
        "used - acceptable": "used_acceptable",

        # Partial strings (from stable_deals output)
        "like new": "used_like_new",
        "very good": "used_very_good",
        "good": "used_good",
        "acceptable": "used_acceptable",

        # Collectible mappings just in case
        "collectible - like new": "collectible_like_new",
        "collectible - very good": "collectible_very_good",
        "collectible - good": "collectible_good",
        "collectible - acceptable": "collectible_acceptable",
    }

    return mapping.get(s)

def check_restrictions(items: list, access_token: str, seller_id: str) -> dict:
    """
    Checks the restriction status for a list of items using the real Amazon SP-API.
    Uses LWA Access Token AND AWS SigV4 signing (required for Production).

    Args:
        items: A list of ASIN strings OR a list of dicts {'asin': str, 'condition': str}.
        access_token: The OAuth access token for the SP-API.
        seller_id: The selling partner ID for the user.

    Returns:
        A dictionary where keys are ASINs and values are another dictionary
        with 'is_restricted' (bool) and 'approval_url' (str or None).
    """
    logger.info(f"Starting real SP-API restriction check for {len(items)} items for seller {seller_id}.")
    results = {}

    # Log token prefix for debugging
    token_prefix = access_token[:15] + "..." if access_token else "None"
    logger.info(f"Using Access Token: {token_prefix}")

    headers = {
        'x-amz-access-token': access_token,
        'Content-Type': 'application/json',
        'User-Agent': 'AgentArbitrage/1.0 (Language=Python/3.12)'
    }

    # Prepare AWS SigV4 Auth
    auth = None
    if AWSSigV4:
        aws_access_key = os.getenv("SP_API_AWS_ACCESS_KEY_ID")
        aws_secret_key = os.getenv("SP_API_AWS_SECRET_KEY")
        aws_region = os.getenv("SP_API_AWS_REGION", "us-east-1")

        if aws_access_key and aws_secret_key:
            logger.info("AWS Credentials found. Signing requests with SigV4.")
            auth = AWSSigV4('execute-api', region=aws_region,
                           aws_access_key_id=aws_access_key,
                           aws_secret_access_key=aws_secret_key)
        else:
            logger.warning("AWS Credentials (SP_API_AWS_ACCESS_KEY_ID/SECRET) missing. Requests will NOT be signed.")
    else:
        logger.warning("requests-auth-aws-sigv4 library not found. Requests will NOT be signed.")

    # Use a session for efficiency
    session = requests.Session()
    session.headers.update(headers)

    for item in items:
        # Respect the official 1 request/second rate limit with a small buffer
        time.sleep(1.1)

        if isinstance(item, dict):
            asin = item['asin']
            condition = item.get('condition')
        else:
            asin = item
            condition = None

        condition_type = map_condition_to_sp_api(condition)

        params = {
            'asin': asin,
            'sellerId': seller_id,
            'marketplaceIds': MARKETPLACE_ID_US
        }

        if condition_type:
            params['conditionType'] = condition_type
            logger.info(f"Checking restriction for ASIN {asin} with conditionType: {condition_type}")
        else:
            logger.info(f"Checking restriction for ASIN {asin} (Generic check)")

        url = f"{SP_API_BASE_URL_NA}/listings/2021-08-01/restrictions"

        # Log request details (redacting full token)
        logger.info(f"Requesting URL: {url} with params: {params}")

        try:
            # Pass 'auth' explicitly. If None, it works like a normal request.
            response = session.get(url, params=params, auth=auth)
            response.raise_for_status()
            data = response.json()

            restrictions = data.get('restrictions', [])
            is_restricted = bool(restrictions)  # If the list is not empty, it's restricted

            approval_url = None
            # Attempt to find a direct approval link from the API response
            if is_restricted:
                # Default fallback: Specific approval request page
                approval_url = f"https://sellercentral.amazon.com/hz/approvalrequest?asin={asin}"

                # Try to find a specific deep link if available
                r_links = restrictions[0].get('links')

                # Case A: Standard SP-API (links is a list of objects)
                if isinstance(r_links, list):
                    for link_obj in r_links:
                        # Standard SP-API uses 'resource', some older schemas might use 'uri'
                        url_candidate = link_obj.get('resource') or link_obj.get('uri') or ''
                        if link_obj.get('verb') == 'GET' and 'approval' in url_candidate:
                            approval_url = url_candidate
                            break

                # Case B: Legacy/Other (links is a dict with 'actions')
                elif isinstance(r_links, dict) and r_links.get('actions'):
                    for action in r_links['actions']:
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
            # Mark as error state
            results[asin] = {"is_restricted": -1, "approval_url": "ERROR"}
        except Exception as e:
            logger.error(f"Unexpected error checking ASIN {asin}: {e}", exc_info=True)
            results[asin] = {"is_restricted": -1, "approval_url": "ERROR"}

    logger.info("SP-API restriction check complete.")
    return results
