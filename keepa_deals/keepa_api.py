# keepa_api.py
# This file will contain the functions that interact with the Keepa API.

import logging
import requests
import json
import os
import urllib.parse
from retrying import retry
import time

logger = logging.getLogger(__name__)
SETTINGS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'settings.json')


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

def _load_deal_settings():
    """
    Loads deal filter settings from settings.json.
    Provides sensible defaults if the file or keys are missing.
    """
    try:
        with open(SETTINGS_PATH, 'r') as f:
            settings = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning(f"Could not load or parse {SETTINGS_PATH}. Using default deal settings.")
        settings = {}

    # These defaults match the ones provided in the wsgi_handler GET request for consistency.
    # Keepa API expects integer values for these fields and price values in cents.
    return {
        "deltaPercentRange_min": settings.get("min_percent_drop", 50),
        "deltaPercentRange_max": 2147483647,  # Max integer
        "currentRange_min": int(settings.get("min_price", 20.0) * 100),
        "currentRange_max": int(settings.get("max_price", 300.0) * 100),
        "salesRankRange_min": -1,  # -1 means no minimum
        "salesRankRange_max": settings.get("max_sales_rank", 1500000)
    }

@retry(stop_max_attempt_number=3, wait_fixed=5000)
def fetch_deals_for_deals(date_range_days, api_key, use_deal_settings=False):
    """
    Fetches deals from the Keepa API.
    If use_deal_settings is True, it loads dynamic filters from settings.json.
    `date_range_days` is the number of days to look back, which is mapped to the required Keepa enum.
    """
    # Map the number of days to the Keepa dateRange enum.
    # 0 = Day (last 24 hours), 1 = Week (last 7 days), 2 = Month (last 31 days), 3 = 3 Months (last 90 days)
    try:
        days = int(date_range_days)
        if days <= 1:
            date_range_enum = 0
        elif days <= 7:
            date_range_enum = 1
        elif days <= 31:
            date_range_enum = 2
        else:
            date_range_enum = 3
    except (ValueError, TypeError):
        logger.error(f"Invalid date_range_days: {date_range_days}. Defaulting to enum 0.")
        date_range_enum = 0

    logger.info(f"Fetching deals for date_range_days={date_range_days}, mapped to enum={date_range_enum}")

    if use_deal_settings:
        deal_settings = _load_deal_settings()
        deal_query = {
            "page": 0, "domainId": 1, "excludeCategories": [], "includeCategories": [283155],
            "priceTypes": [2],
            "deltaRange": [1, 2147483647],
            "deltaPercentRange": [deal_settings["deltaPercentRange_min"], deal_settings["deltaPercentRange_max"]],
            "salesRankRange": [deal_settings["salesRankRange_min"], deal_settings["salesRankRange_max"]],
            "currentRange": [deal_settings["currentRange_min"], deal_settings["currentRange_max"]],
            "minRating": -1,
            "isLowest": False, "isLowest90": False, "isLowestOffer": False, "isOutOfStock": False,
            "titleSearch": "", "isRangeEnabled": True, "isFilterEnabled": True, "filterErotic": False,
            "singleVariation": True, "hasReviews": False, "isPrimeExclusive": False,
            "mustHaveAmazonOffer": False, "mustNotHaveAmazonOffer": False, "sortType": 4,
            "dateRange": date_range_enum
        }
    else:
        # Fallback to a generic query if not using settings
        deal_query = {
            "page": 0, "domainId": 1, "priceTypes": [2],
            "dateRange": date_range_enum,
            "sortType": 4
        }

    query_json = json.dumps(deal_query, separators=(',', ':'), sort_keys=True)
    encoded_selection = urllib.parse.quote(query_json)
    url = f"https://api.keepa.com/deal?key={api_key}&selection={encoded_selection}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/90.0.4430.212'}
    
    try:
        response = requests.get(url, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()
        deals = data.get('deals', {}).get('dr', [])
        logger.info(f"Fetched {len(deals)} deals.")
        return data
    except requests.exceptions.RequestException as e:
        logger.error(f"Deal fetch failed: {e.response.status_code if e.response else 'N/A'}, {e.response.text if e.response else e}")
        return None
    except Exception as e:
        logger.error(f"Deal fetch exception: {str(e)}")
        return None


def fetch_product_batch(api_key, asins_list, days=365, offers=20, rating=1, history=0):
    """
    Fetches a batch of products from the Keepa API.
    Returns the response data, API info (including errors), and the authoritative token cost.
    Optimized for the upserter task by default.
    """
    if not asins_list:
        logger.warning("fetch_product_batch called with an empty list of ASINs.")
        return None, {'error_status_code': 'EMPTY_ASIN_LIST'}, 0

    logger.info(f"Fetching batch of {len(asins_list)} ASINs: {','.join(asins_list[:3])}...")

    comma_separated_asins = ','.join(asins_list)
    # Optimized URL for the upserter: no history, no stock, no buybox info.
    url = f"https://api.keepa.com/product?key={api_key}&domain=1&asin={comma_separated_asins}&stats={days}&offers={offers}&rating={rating}&history={history}&only_live_offers=1"
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