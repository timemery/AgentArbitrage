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
    Signs the request using AWS SigV4.

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

    # --- AWS SigV4 Setup ---
    aws_access_key = os.getenv("SP_API_AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("SP_API_AWS_SECRET_KEY")
    aws_region = os.getenv("SP_API_AWS_REGION", "us-east-1")
    service = 'execute-api'

    if not aws_access_key or not aws_secret_key:
        logger.error("Missing AWS Credentials (SP_API_AWS_ACCESS_KEY_ID / SP_API_AWS_SECRET_KEY). Cannot sign request.")
        # If credentials are missing, we cannot proceed. Mark as failure/restricted.
        results = {}
        for item in items:
            # Handle dicts, sqlite3.Row objects (which act like dicts but fail isinstance check sometimes), or raw ASIN strings
            if hasattr(item, '__getitem__') and not isinstance(item, str):
                try:
                    asin = item['asin']
                except (KeyError, TypeError, IndexError):
                    # Fallback if key lookup fails, assuming item might be the ASIN itself if unexpected type
                    asin = str(item)
            else:
                asin = str(item)

            results[asin] = {"is_restricted": True, "approval_url": None}
        return results

    auth = AWS4Auth(aws_access_key, aws_secret_key, aws_region, service)

    headers = {
        'x-amz-access-token': access_token,
        'Content-Type': 'application/json'
    }

    # Use a session for efficiency and to attach auth
    session = requests.Session()
    session.auth = auth
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
