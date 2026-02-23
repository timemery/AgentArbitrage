# VERIFIED_UPDATE: Condition-aware deep linking
"""
This module encapsulates all interactions with the Amazon Selling Partner API (SP-API).
"""

import time
import logging
import os
import requests
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

# Constants for the SP-API
# Default to Production. Use SP_API_URL env var to override (e.g. for Sandbox testing).
SP_API_BASE_URL_NA = os.getenv("SP_API_URL", "https://sellingpartnerapi-na.amazon.com")
MARKETPLACE_ID_US = "ATVPDKIKX0DER"


def refresh_sp_api_token(refresh_token: str) -> str | None:
    """
    Refreshes the SP-API access token using the refresh token.
    """
    logger.info("Attempting to refresh SP-API access token.")

    client_id = os.getenv("SP_API_CLIENT_ID")
    client_secret = os.getenv("SP_API_CLIENT_SECRET")
    token_url = "https://api.amazon.com/auth/o2/token"

    if not all([client_id, client_secret]):
        logger.error("SP_API_CLIENT_ID or SP_API_CLIENT_SECRET are not configured.")
        return None

    refresh_payload = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': client_id,
        'client_secret': client_secret
    }

    try:
        response = requests.post(token_url, data=refresh_payload, timeout=30)
        response.raise_for_status()
        token_data = response.json()

        new_access_token = token_data.get('access_token')
        if new_access_token:
            logger.info("Successfully refreshed SP-API access token.")
            return new_access_token
        else:
            logger.error("Token refresh response did not contain an access_token.")
            return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to refresh SP-API token: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during token refresh: {e}", exc_info=True)
        return None


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
    Uses only LWA Access Token (no AWS SigV4 required for private apps as of Oct 2023).

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
            # Set a strict timeout to prevent indefinite hangs
            response = session.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()

            restrictions = data.get('restrictions', [])
            is_restricted = bool(restrictions)  # If the list is not empty, it's restricted

            approval_url = None
            # Attempt to find a direct approval link from the API response
            if is_restricted:
                # Determine simple condition for the URL (new, used, etc.)
                simple_cond = None
                if condition:
                    c_lower = str(condition).lower()
                    if 'new' in c_lower:
                        simple_cond = 'new'
                    elif 'used' in c_lower:
                        simple_cond = 'used'
                    elif 'collectible' in c_lower:
                        simple_cond = 'collectible'
                    elif 'refurbished' in c_lower:
                        simple_cond = 'refurbished'

                if simple_cond:
                    # Specific deep link (Best UX)
                    approval_url = f"https://sellercentral.amazon.com/hz/approvalrequest/restrictions/approve?asin={asin}&itemcondition={simple_cond}"
                else:
                    # Fallback: "Add a Product" search page
                    approval_url = f"https://sellercentral.amazon.com/product-search/keywords/search?q={asin}"

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

            # --- NEW DIAGNOSTIC CHECK ---
            # If we get a 403 on Production, check if the token works on Sandbox.
            # This helps users identify if they are using Sandbox credentials with the Production URL.
            if e.response.status_code == 403 and "sellingpartnerapi-na.amazon.com" in url and "sandbox" not in url:
                try:
                    logger.info("403 Forbidden on Production. Attempting diagnostic check against Sandbox...")
                    sandbox_url = "https://sandbox.sellingpartnerapi-na.amazon.com/listings/2021-08-01/restrictions"
                    # Use the same params, but Sandbox might not have the ASIN.
                    # Actually, Sandbox restriction check is mocked. It usually returns 200 OK (and restricted status).
                    # If we get 200 OK, it means the TOKEN is valid for Sandbox.
                    sb_resp = session.get(sandbox_url, params=params, timeout=10)

                    if sb_resp.status_code == 200:
                        logger.critical("MISCONFIGURATION DETECTED: The SP-API Token is valid for Sandbox but rejected by Production (403). "
                                        "You are likely using Sandbox Credentials with the Production URL. "
                                        "Please update SP_API_CLIENT_ID and SP_API_CLIENT_SECRET in .env to your Production App credentials, "
                                        "and generate a new Refresh Token.")
                    else:
                        logger.warning(f"Diagnostic Sandbox check also failed: Status {sb_resp.status_code}")
                except Exception as dx:
                    logger.error(f"Diagnostic check failed: {dx}")
            # -----------------------------

            # Mark as error state
            results[asin] = {"is_restricted": -1, "approval_url": "ERROR"}
        except requests.exceptions.Timeout:
            logger.error(f"Timeout checking ASIN {asin}. The SP-API endpoint took too long to respond.")
            results[asin] = {"is_restricted": -1, "approval_url": "ERROR"}
        except Exception as e:
            logger.error(f"Unexpected error checking ASIN {asin}: {e}", exc_info=True)
            results[asin] = {"is_restricted": -1, "approval_url": "ERROR"}

    logger.info("SP-API restriction check complete.")
    return results

def fetch_orders(access_token: str, last_updated_after: str = None, created_after: str = None) -> list:
    """
    Fetches orders from Amazon SP-API using the Orders API v0.
    Handles pagination automatically.

    Args:
        access_token: The OAuth access token.
        last_updated_after: ISO 8601 date string (e.g., '2023-01-01T00:00:00Z').
                            Returns orders updated after this date.
        created_after: ISO 8601 date string. Returns orders created after this date.
                       (Note: Use either last_updated_after OR created_after, rarely both).

    Returns:
        A list of order dictionaries (flattened/simplified if needed, or raw).
    """
    logger.info("Starting SP-API fetch_orders.")
    all_orders = []

    if not access_token:
        logger.error("No access token provided for fetch_orders.")
        return []

    headers = {
        'x-amz-access-token': access_token,
        'Content-Type': 'application/json',
        'User-Agent': 'AgentArbitrage/1.0 (Language=Python/3.12)'
    }

    url = f"{SP_API_BASE_URL_NA}/orders/v0/orders"

    # Marketplace ID for US
    params = {
        'MarketplaceIds': MARKETPLACE_ID_US,
        'MaxResultsPerPage': 100
    }

    if last_updated_after:
        params['LastUpdatedAfter'] = last_updated_after
    elif created_after:
        params['CreatedAfter'] = created_after
    else:
        # Default to fetch last 30 days if nothing specified?
        # Or better, let the caller decide.
        # For safety, if no date provided, API requires CreatedAfter or LastUpdatedAfter.
        # We'll default to a reasonable window if missing to prevent 400 errors.
        # However, caller should really provide it.
        pass

    try:
        session = requests.Session()
        session.headers.update(headers)

        while True:
            logger.info(f"Requesting Orders URL: {url} with params: {params}")
            response = session.get(url, params=params, timeout=30)

            if response.status_code == 429:
                logger.warning("Rate limit exceeded (429). Waiting 60s...")
                time.sleep(60)
                continue

            response.raise_for_status()
            data = response.json()

            payload = data.get('payload', {})
            orders = payload.get('Orders', [])
            all_orders.extend(orders)

            # Check for NextToken
            next_token = payload.get('NextToken')
            if next_token:
                logger.info("Pagination: Found NextToken, fetching next page...")
                params = {'NextToken': next_token} # Only NextToken is needed for subsequent calls
                # Rate limiting sleep
                time.sleep(1)
            else:
                break

        logger.info(f"Successfully fetched {len(all_orders)} orders.")
        return all_orders

    except Exception as e:
        logger.error(f"Error fetching orders: {e}", exc_info=True)
        return all_orders # Return whatever we got so far

def fetch_order_items(access_token: str, order_id: str) -> list:
    """
    Fetches specific line items for a given Amazon Order ID.
    Required to get ASIN, SKU, and Price details (Order object only has total).
    """
    if not access_token or not order_id:
        return []

    headers = {
        'x-amz-access-token': access_token,
        'Content-Type': 'application/json',
        'User-Agent': 'AgentArbitrage/1.0 (Language=Python/3.12)'
    }

    url = f"{SP_API_BASE_URL_NA}/orders/v0/orders/{order_id}/orderItems"

    try:
        logger.info(f"Fetching items for Order ID: {order_id}")

        # Simple Retry Logic for Rate Limits
        max_retries = 3
        for attempt in range(max_retries):
            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                break
            elif response.status_code == 429:
                sleep_time = 2 ** (attempt + 1) # Exponential backoff: 2, 4, 8
                logger.warning(f"Rate limit 429 for order {order_id}. Retrying in {sleep_time}s...")
                time.sleep(sleep_time)
            else:
                response.raise_for_status()

        if response.status_code != 200:
             logger.error(f"Failed to fetch items for order {order_id} after retries. Status: {response.status_code}")
             return []

        data = response.json()

        items = data.get('payload', {}).get('OrderItems', [])
        return items

    except Exception as e:
        logger.error(f"Error fetching items for order {order_id}: {e}", exc_info=True)
        return []
