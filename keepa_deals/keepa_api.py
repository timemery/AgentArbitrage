# keepa_api.py
# This file will contain the functions that interact with the Keepa API.

import logging
import requests
import json
import urllib.parse
from retrying import retry
import time

logger = logging.getLogger(__name__)

# --- Jules: Local Quota Management Constants & State ---
MAX_QUOTA_TOKENS = 300
# HOURLY_REFILL_PERCENTAGE = 0.05 # Replaced by per-minute refill
TOKENS_PER_MINUTE_REFILL = 5
REFILL_CALCULATION_INTERVAL_SECONDS = 60 # Check for refills every minute

# TOKEN_COST_PER_ASIN = 5 # Replaced by ESTIMATED_AVG_COST_PER_ASIN_IN_BATCH for pre-call checks
ESTIMATED_AVG_COST_PER_ASIN_IN_BATCH = 15 # Updated based on observed cost of ~9.5/ASIN. Set high for safety.
TOKEN_COST_PER_DEAL_PAGE = 1 # Cost for /deal endpoint calls (buybox=false by default)
MIN_QUOTA_THRESHOLD_BEFORE_PAUSE = 25 # General low quota pause trigger
DEFAULT_LOW_QUOTA_PAUSE_SECONDS = 900 # 15 minutes

# Initialize global state variables for quota management
current_available_tokens = MAX_QUOTA_TOKENS
last_refill_calculation_time = time.time()

# Global dictionary to track attempts for fetch_product retries
fetch_product_attempts = {}

# --- Jules: Additional Throttling & Logging Constants ---
MIN_TIME_SINCE_LAST_CALL_SECONDS = 60
# Single ASIN fetch delays
POST_FETCH_SUCCESS_DELAY_SECONDS = 5
POST_FETCH_ERROR_DELAY_SECONDS = 20
# Batch ASIN fetch delays
POST_BATCH_SUCCESS_DELAY_SECONDS = 2
POST_BATCH_ERROR_DELAY_SECONDS = 10
# Initialize global state for pre-emptive delay
LAST_API_CALL_TIMESTAMP = 0
# --- End Additional Throttling & Logging Constants ---
# --- End Local Quota Management ---

def validate_asin(asin):
    if not isinstance(asin, str) or len(asin) != 10 or not asin.isalnum():
        logger.error(f"Invalid ASIN format: {asin}")
        return False
    return True

# Do not modify fetch_deals_for_deals! It mirrors the "Show API query" (https://api.keepa.com/deal), with critical parameters.
@retry(stop_max_attempt_number=3, wait_fixed=5000)
def fetch_deals_for_deals(page, api_key):
    logger.debug(f"Fetching deals page {page} for Percent Down 90...")
    deal_query = {
        "page": page,
        "domainId": "1",
        "excludeCategories": [],
        "includeCategories": [283155],
        "priceTypes": [2],
        "deltaRange": [1950, 9900],
        "deltaPercentRange": [50, 2147483647],
        "salesRankRange": [50000, 1500000],
        "currentRange": [2000, 30100],
        "minRating": 10,
        "isLowest": False,
        "isLowest90": False,
        "isLowestOffer": False,
        "isOutOfStock": False,
        "titleSearch": "",
        "isRangeEnabled": True,
        "isFilterEnabled": True,
        "filterErotic": False,
        "singleVariation": True,
        "hasReviews": False,
        "isPrimeExclusive": False,
        "mustHaveAmazonOffer": False,
        "mustNotHaveAmazonOffer": False,
        "sortType": 4,
        "dateRange": "3"
    }
    query_json = json.dumps(deal_query, separators=(',', ':'), sort_keys=True)
    logger.debug(f"Raw query JSON: {query_json}")
    encoded_selection = urllib.parse.quote(query_json)
    url = f"https://api.keepa.com/deal?key={api_key}&selection={encoded_selection}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/90.0.4430.212'}
    logger.debug(f"Deal URL: {url}")
    try:
        response = requests.get(url, headers=headers, timeout=30)
        logger.debug(f"Full deal response: {response.text}")
        if response.status_code != 200:
            logger.error(f"Deal fetch failed: {response.status_code}, {response.text}")
            return []
        data = response.json()
        deals = data.get('deals', {}).get('dr', [])
        logger.debug(f"Fetched {len(deals)} deals: {[d.get('asin', '-') for d in deals]}")
        logger.debug(f"Deal response structure: {list(data.get('deals', {}).keys())}")
        logger.debug(f"All deal keys: {[list(d.keys()) for d in deals]}")
        logger.debug(f"Deals data: {[{'asin': d.get('asin', '-'), 'current': d.get('current', []), 'current[9]': d.get('current', [-1] * 20)[9] if len(d.get('current', [])) > 9 else -1, 'current[1]': d.get('current', [-1] * 20)[1] if len(d.get('current', [])) > 1 else -1} for d in deals]}")
        logger.info(f"Fetched {len(deals)} deals from page {page}")
        return deals
    except Exception as e:
        logger.error(f"Deal fetch exception: {str(e)}")
        return []

@retry(stop_max_attempt_number=3, wait_fixed=10)
def fetch_product(api_key, asin, no_cache, days=365, offers=100, rating=1, history=1):
    global current_available_tokens # Moved to top of function for all reads/writes
    # Increment and log attempt number for this ASIN
    # This requires a way to store attempt counts across calls triggered by @retry for the same ASIN.
    # A simple global dictionary can serve this purpose for now.
    global fetch_product_attempts
    if asin not in fetch_product_attempts:
        fetch_product_attempts[asin] = 0
    fetch_product_attempts[asin] += 1
    attempt_num = fetch_product_attempts[asin]

    logger.info(f"fetch_product: Attempt #{attempt_num} for ASIN {asin} (days={days}, offers={offers}, rating={rating}, history={history}, no_cache={no_cache})")

    if not validate_asin(asin):
        # Reset attempt count for this ASIN if it fails validation before any actual attempt
        fetch_product_attempts[asin] = 0 # Or handle as needed - this error is pre-API call
        logging.error(f"Invalid ASIN format: {asin}")
        # Consistent return for validation failure
        rate_limit_info_on_error = {'limit': None, 'remaining': None, 'reset': None, 'error_status_code': 'VALIDATION_ERROR'}
        return {'stats': {'current': [-1] * 30}, 'asin': asin, 'error': True, 'status_code': 'VALIDATION_ERROR', 'message': 'Invalid ASIN format'}, rate_limit_info_on_error

    url = f"https://api.keepa.com/product?key={api_key}&domain=1&asin={asin}&stats={days}&offers={offers}&rating={rating}&history={history}&stock=1&buybox=1"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/90.0.4430.212'}
    try:
        logger.debug(f"fetch_product (Attempt #{attempt_num}): Making HTTP GET request for ASIN {asin} to {url}")
        response = requests.get(url, headers=headers, timeout=60)

        logger.debug(f"fetch_product (Attempt #{attempt_num}): Response status {response.status_code} for ASIN {asin}")
        response.raise_for_status() # Will raise HTTPError for 4xx/5xx, which is a RequestException

        fetch_product_attempts[asin] = 0 # Reset on success
        data = response.json()
        products = data.get('products', [])
        if not products:
            logging.error(f"No product data for ASIN {asin} despite 2xx status.")
            rate_limit_info_on_error = { # Simplified rate_limit_info
                'limit': None, 'remaining': None, 'reset': None,
                'error_status_code': response.status_code
            }
            return {'stats': {'current': [-1] * 30}, 'asin': asin, 'error': True, 'status_code': response.status_code, 'message': 'No product data found in response'}, rate_limit_info_on_error

        product = products[0]
        stats = product.get('stats', {})
        current = stats.get('current', [-1] * 30)
        offers = product.get('offers', []) if product.get('offers') is not None else []
        logging.info(f"HTTP Stats for ASIN {asin}: Found product data. current_array_length={len(current)}, offers_count={len(offers)}. Stat keys: {list(stats.keys())}")
        logger.debug(f"HTTP Stats for ASIN {asin}: current_data={current}, stats_raw={stats}")
        if len(current) < 11:
            logging.warning(f"Short current array for ASIN {asin}: {current}")
        if current[1] == -1:
            logging.warning(f"Invalid Amazon - Current price for ASIN {asin}: current[1]={current[1]}")

        rate_limit_info = {'limit': None, 'remaining': None, 'reset': None}
        return product, rate_limit_info
    except requests.exceptions.RequestException as e:
        logging.error(f"HTTP Fetch failed for ASIN {asin}: {str(e)}")
        status_code = e.response.status_code if e.response is not None else None
        rate_limit_info = {
            'limit': None, 'remaining': None, 'reset': None,
            'error_status_code': status_code
        }
        if status_code == 429:
             logger.error(f"ASIN {asin} - 429 ERROR. Script tokens at time of call: {current_available_tokens:.2f}.")
        return {'stats': {'current': [-1] * 30}, 'asin': asin, 'error': True, 'status_code': status_code}, rate_limit_info
    except Exception as e:
        logging.error(f"Generic Fetch failed for ASIN {asin}: {str(e)}")
        rate_limit_info = {'limit': None, 'remaining': None, 'reset': None, 'error_status_code': None}
        return {'stats': {'current': [-1] * 30}, 'asin': asin, 'error': True, 'status_code': None}, rate_limit_info

@retry(stop_max_attempt_number=3, wait_fixed=15000) # Increased wait for batch calls
def fetch_product_batch(api_key, asins_list, days=365, offers=100, rating=1, history=1):
    global current_available_tokens # For logging current token state if 429 occurs

    if not asins_list:
        logger.warning("fetch_product_batch called with an empty list of ASINs.")
        return [], {'requestTokens': 0, 'tokensLeft': None, 'refillIn': None, 'refillRate': None, 'error_status_code': 'EMPTY_ASIN_LIST'}, 0

    logger.info(f"fetch_product_batch: Attempting to fetch batch of {len(asins_list)} ASINs: {','.join(asins_list[:3])}...")

    comma_separated_asins = ','.join(asins_list)
    url = f"https://api.keepa.com/product?key={api_key}&domain=1&asin={comma_separated_asins}&stats={days}&offers={offers}&rating={rating}&history={history}&stock=1&buybox=1"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/90.0.4430.212'} # Standard User-Agent

    try:
        logger.debug(f"fetch_product_batch: Making HTTP GET request for {len(asins_list)} ASINs to {url}")
        response = requests.get(url, headers=headers, timeout=120) # Increased timeout for batch calls

        logger.debug(f"fetch_product_batch: Response status {response.status_code} for ASINs {','.join(asins_list[:3])}...")
        response.raise_for_status()

        data = response.json()

        tokens_consumed_from_api = data.get('tokensConsumed')
        actual_batch_cost = 0 # Default if not found or not applicable

        if tokens_consumed_from_api is not None:
            actual_batch_cost = int(tokens_consumed_from_api)
            logger.info(f"Batch API call cost {actual_batch_cost} tokens according to 'tokensConsumed' field in response.")
        else:
            actual_batch_cost = len(asins_list) * ESTIMATED_AVG_COST_PER_ASIN_IN_BATCH # Fallback estimation
            logger.warning(f"'tokensConsumed' field NOT found in successful batch response. Using estimated cost: {actual_batch_cost} tokens. This is unexpected.")

        api_info = {
            'tokensConsumed': tokens_consumed_from_api, # Store what we got
            'error_status_code': None # Will be set in except blocks if error
        }

        products_data = data.get('products', [])
        if not products_data and len(asins_list) > 0: # Successful call but no product data for any ASIN
            logger.error(f"No product data in batch response for ASINs {','.join(asins_list[:3])}... despite 2xx status. Cost was {actual_batch_cost} tokens.")
            error_products = [{'asin': asin, 'error': True, 'status_code': response.status_code, 'message': 'No product data found in batch response'} for asin in asins_list]
            return error_products, api_info, actual_batch_cost

        logger.info(f"Successfully fetched data for {len(products_data)} products in batch for {len(asins_list)} requested ASINs.")
        return products_data, api_info, actual_batch_cost

    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP Fetch failed for batch ASINs {','.join(asins_list[:3])}...: {str(e)}")
        status_code = e.response.status_code if e.response is not None else None

        tokens_consumed_on_error = 0 # Default if we can't parse it
        if e.response is not None:
            try:
                error_data = e.response.json()
                if error_data.get('tokensConsumed') is not None:
                    tokens_consumed_on_error = int(error_data['tokensConsumed'])
                    logger.info(f"HTTP error response included 'tokensConsumed': {tokens_consumed_on_error}.")
                else:
                    logger.warning(f"HTTP error response (status {status_code}) did not include 'tokensConsumed'. Assuming 0 for this failed attempt.")
            except json.JSONDecodeError:
                logger.warning(f"HTTP error response (status {status_code}) was not valid JSON. Assuming 0 tokens consumed for this failed attempt.")

        api_info_on_error = {
            'tokensConsumed': tokens_consumed_on_error if status_code == 429 else None, # Only really relevant for 429s if we want to account for cost of failed call
            'error_status_code': status_code
        }

        cost_to_report = tokens_consumed_on_error

        if status_code == 429:
             logger.error(f"Batch ASINs - 429 ERROR. Script tokens at time of call: {current_available_tokens:.2f}. Keepa reported {tokens_consumed_on_error} tokens consumed for this failed call.")

        error_products = [{'asin': asin, 'error': True, 'status_code': status_code, 'message': str(e)} for asin in asins_list]
        return error_products, api_info_on_error, cost_to_report

    except Exception as e: # Generic exceptions (e.g., JSONDecodeError for successful status but bad body, though less likely here)
        logger.error(f"Generic Fetch failed for batch ASINs {','.join(asins_list[:3])}...: {str(e)}")
        api_info_on_error = {'tokensConsumed': None, 'error_status_code': 'GENERIC_SCRIPT_ERROR'}
        cost_to_report_generic_error = 0
        error_products = [{'asin': asin, 'error': True, 'status_code': 'GENERIC_SCRIPT_ERROR', 'message': str(e)} for asin in asins_list]
        return error_products, api_info_on_error, cost_to_report_generic_error

def update_and_check_quota(logger, current_available_tokens, last_refill_calculation_time, min_quota_threshold, pause_seconds, tokens_per_minute, refill_interval_seconds, max_tokens):
    """
    Updates the available token count based on hourly refill and pauses if tokens are low.
    """
    logger.debug(f"Quota Check (entry): Current available tokens: {current_available_tokens:.2f}, Last refill calc time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_refill_calculation_time))}")

    current_time = time.time()
    time_elapsed_seconds = current_time - last_refill_calculation_time

    if time_elapsed_seconds >= refill_interval_seconds:
        intervals_passed = int(time_elapsed_seconds // refill_interval_seconds)
        
        if intervals_passed > 0:
            tokens_refilled_per_minute_interval = tokens_per_minute * (refill_interval_seconds / 60.0)
            total_refilled = intervals_passed * tokens_refilled_per_minute_interval
            
            tokens_before_refill = current_available_tokens
            current_available_tokens += total_refilled
            if current_available_tokens > max_tokens:
                current_available_tokens = max_tokens
            
            original_last_refill_time = last_refill_calculation_time
            last_refill_calculation_time += intervals_passed * refill_interval_seconds
            
            logger.info(
                f"Quota Refill: Processed {intervals_passed} interval(s) of {refill_interval_seconds}s "
                f"(from {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(original_last_refill_time))}). "
                f"Tokens before: {tokens_before_refill:.2f}. Added {total_refilled:.2f}. Tokens after: {current_available_tokens:.2f}. "
                f"New last refill calc time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_refill_calculation_time))}"
            )
    
    if current_available_tokens < min_quota_threshold:
        logger.warning(
            f"Low quota: {current_available_tokens:.2f} tokens remaining, which is below threshold {min_quota_threshold}. "
            f"Pausing for {pause_seconds / 60:.1f} minutes."
        )
        time.sleep(pause_seconds)
        
        logger.info(f"Quota: Pause complete. Re-checking quota.")
        # After pausing, re-run the check once to refill tokens accumulated during the pause.
        return update_and_check_quota(logger, current_available_tokens, last_refill_calculation_time, min_quota_threshold, pause_seconds, tokens_per_minute, refill_interval_seconds, max_tokens)


    return current_available_tokens, last_refill_calculation_time

@retry(stop_max_attempt_number=3, wait_fixed=5000)
def fetch_seller_data(api_key, seller_id):
    """
    Fetches data for a specific seller from the Keepa API.
    """
    if not seller_id:
        logger.warning("fetch_seller_data called with no seller_id.")
        return None

    logger.info(f"Fetching seller data for seller ID: {seller_id}")
    
    url = f"https://api.keepa.com/seller?key={api_key}&domain=1&seller={seller_id}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/90.0.4430.212'}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        
        if data.get('sellers'):
            seller_info = data['sellers'].get(seller_id)
            if seller_info:
                # Use the correct keys based on the log file analysis
                rating_percentage = seller_info.get('currentRating', -1)
                rating_count = seller_info.get('currentRatingCount', 0)
                
                if rating_percentage != -1:
                    return {
                        "rank": f"{rating_percentage}% ({rating_count} ratings)",
                        "rating_percentage": rating_percentage,
                        "rating_count": rating_count
                    }
                else:
                    logger.warning(f"Seller {seller_id}: 'currentRating' field not found in seller object. Full object: {seller_info}")
                    return None
        else:
            logger.warning(f"No 'sellers' data found for seller ID {seller_id} in response.")
            return None

    except requests.exceptions.RequestException as e:
        logger.error(f"HTTP fetch failed for seller ID {seller_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching seller data for {seller_id}: {e}")
        return None
