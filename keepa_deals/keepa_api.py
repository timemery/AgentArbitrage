# keepa_api.py
# This file will contain the functions that interact with the Keepa API.

import logging
import requests
import json
import urllib.parse
from retrying import retry
import time

logger = logging.getLogger(__name__)

def validate_asin(asin):
    if not isinstance(asin, str) or len(asin) != 10 or not asin.isalnum():
        logger.error(f"Invalid ASIN format: {asin}")
        return False
    return True

def get_token_status(api_key):
    """
    Makes a request to the /token endpoint to get the current token status.
    """
    logger.info("Requesting current token status from Keepa...")
    url = f"https://api.keepa.com/token?key={api_key}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/90.0.4430.212'}
    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        logger.info(f"Successfully retrieved token status: {data}")
        return data
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to get token status: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while getting token status: {e}")
        return None

@retry(stop_max_attempt_number=3, wait_fixed=5000)
def fetch_deals_for_deals(page, api_key):
    # This function is for a specific 'deals' query and does not use the main batch logic.
    # Its token cost is handled separately in the main script.
    logger.debug(f"Fetching deals page {page}...")
    deal_query = {
        "page": page, "domainId": "1", "excludeCategories": [], "includeCategories": [283155],
        "priceTypes": [2], "deltaRange": [1950, 9900], "deltaPercentRange": [50, 2147483647],
        "salesRankRange": [50000, 1500000], "currentRange": [2000, 30100], "minRating": 10,
        "isLowest": False, "isLowest90": False, "isLowestOffer": False, "isOutOfStock": False,
        "titleSearch": "", "isRangeEnabled": True, "isFilterEnabled": True, "filterErotic": False,
        "singleVariation": True, "hasReviews": False, "isPrimeExclusive": False,
        "mustHaveAmazonOffer": False, "mustNotHaveAmazonOffer": False, "sortType": 4, "dateRange": "3"
    }
    query_json = json.dumps(deal_query, separators=(',', ':'), sort_keys=True)
    encoded_selection = urllib.parse.quote(query_json)
    url = f"https://api.keepa.com/deal?key={api_key}&selection={encoded_selection}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/90.0.4430.212'}
    
    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code != 200:
            logger.error(f"Deal fetch failed: {response.status_code}, {response.text}")
            return None
        data = response.json()
        deals = data.get('deals', {}).get('dr', [])
        logger.info(f"Fetched {len(deals)} deals from page {page}")
        return data
    except Exception as e:
        logger.error(f"Deal fetch exception: {str(e)}")
        return None

def fetch_product_batch(api_key, asins_list, days=365, offers=20, rating=1, history=1):
    """
    Fetches a batch of products from the Keepa API.
    Returns the response data, API info (including errors), and the authoritative token cost.
    """
    if not asins_list:
        logger.warning("fetch_product_batch called with an empty list of ASINs.")
        return None, {'error_status_code': 'EMPTY_ASIN_LIST'}, 0

    logger.info(f"Fetching batch of {len(asins_list)} ASINs: {','.join(asins_list[:3])}...")

    comma_separated_asins = ','.join(asins_list)
    # Note: `offers` parameter is now set to 20, the minimum valid value.
    url = f"https://api.keepa.com/product?key={api_key}&domain=1&asin={comma_separated_asins}&stats={days}&offers={offers}&rating={rating}&history={history}&stock=1&buybox=1&only_live_offers=1"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/90.0.4430.212'}

    try:
        response = requests.get(url, headers=headers, timeout=120)
        response.raise_for_status()
        data = response.json()
        
        # Authoritative token cost from the response
        tokens_consumed = data.get('tokensConsumed', 0)
        logger.info(f"Batch API call successful. Tokens consumed: {tokens_consumed}")

        api_info = {'error_status_code': None}
        return data, api_info, tokens_consumed

    except requests.exceptions.RequestException as e:
        status_code = e.response.status_code if e.response is not None else 'N/A'
        logger.error(f"HTTP Fetch failed for batch ASINs {','.join(asins_list[:3])}... with status {status_code}: {str(e)}")
        
        tokens_consumed_on_error = 0
        if e.response is not None:
            try:
                error_data = e.response.json()
                tokens_consumed_on_error = error_data.get('tokensConsumed', 0)
                if status_code == 429:
                    logger.error(f"429 ERROR. Keepa reported {tokens_consumed_on_error} tokens consumed for this failed call.")
            except json.JSONDecodeError:
                logger.warning(f"HTTP error response (status {status_code}) was not valid JSON.")

        api_info_on_error = {'error_status_code': status_code}
        return None, api_info_on_error, tokens_consumed_on_error

    except Exception as e:
        logger.error(f"Generic Fetch failed for batch ASINs {','.join(asins_list[:3])}...: {str(e)}")
        api_info_on_error = {'error_status_code': 'GENERIC_SCRIPT_ERROR'}
        return None, api_info_on_error, 0

def fetch_seller_data(api_key, seller_ids):
    """
    Fetches data for a list of sellers from the Keepa API.
    Returns the response data, API info (including errors), and the authoritative token cost.
    """
    if not seller_ids:
        logger.warning("fetch_seller_data called with no seller_ids.")
        return None, {'error_status_code': 'EMPTY_SELLER_ID_LIST'}, 0

    if len(seller_ids) > 100:
        logger.error(f"fetch_seller_data called with a batch of {len(seller_ids)} which is over the 100 limit.")
        return None, {'error_status_code': 'BATCH_SIZE_EXCEEDED'}, 0

    seller_ids_str = ','.join(seller_ids)
    logger.info(f"Fetching data for batch of {len(seller_ids)} sellers")
    url = f"https://api.keepa.com/seller?key={api_key}&domain=1&seller={seller_ids_str}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/90.0.4430.212'}
    
    try:
        response = requests.get(url, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        tokens_consumed = data.get('tokensConsumed', 0)
        logger.info(f"Seller API call successful. Tokens consumed: {tokens_consumed}")
        
        api_info = {'error_status_code': None}
        return data, api_info, tokens_consumed

    except requests.exceptions.RequestException as e:
        status_code = e.response.status_code if e.response is not None else 'N/A'
        logger.error(f"HTTP fetch failed for seller batch with status {status_code}: {e}")
        
        tokens_consumed_on_error = 0
        if e.response is not None:
            try:
                error_data = e.response.json()
                tokens_consumed_on_error = error_data.get('tokensConsumed', 0)
                if status_code == 429:
                    logger.error(f"429 ERROR on seller batch. Keepa reported {tokens_consumed_on_error} tokens consumed.")
            except json.JSONDecodeError:
                logger.warning(f"HTTP error response (status {status_code}) was not valid JSON.")

        api_info_on_error = {'error_status_code': status_code}
        return None, api_info_on_error, tokens_consumed_on_error
        
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching seller data: {e}", exc_info=True)
        api_info_on_error = {'error_status_code': 'GENERIC_SCRIPT_ERROR'}
        return None, api_info_on_error, 0
