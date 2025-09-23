# Keepa_Deals.py
# (Last update: Version 5.1)

# Chunk 1 starts:
# Added argparse
import json, csv, logging, sys, requests, urllib.parse, time, argparse, math
from retrying import retry
from stable_deals import validate_asin, fetch_deals_for_deals
from field_mappings import FUNCTION_LIST
import os
CSV_PATH = os.path.join(os.path.dirname(__file__), "Keepa_Deals_Export.csv")

# Get the main script logger instance
logger = logging.getLogger('KeepaDeals') # Use the same logger as in main()

# --- Jules: Local Quota Management Constants & State ---
MAX_QUOTA_TOKENS = 300
# HOURLY_REFILL_PERCENTAGE = 0.05 # Replaced by per-minute refill
TOKENS_PER_MINUTE_REFILL = 5
REFILL_CALCULATION_INTERVAL_SECONDS = 60 # Check for refills every minute

# TOKEN_COST_PER_ASIN = 5 # Replaced by ESTIMATED_AVG_COST_PER_ASIN_IN_BATCH for pre-call checks
ESTIMATED_AVG_COST_PER_ASIN_IN_BATCH = 6 # Updated based on full run analysis (previously 4). Actual cost from API's 'tokensConsumed'.
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

# Logging for terminal and file output - starts
# import sys # sys is already imported globally
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),  # Terminal output
        logging.FileHandler('debug_log.txt', mode='w')  # File output, mode 'w' to overwrite
    ]
)
# Force flush for real-time output
logging.getLogger().handlers[0].flush = sys.stdout.flush

#kept but commented out in case the new one above doesn't work.
#logging.basicConfig(
#    level=logging.INFO,
#    format='%(asctime)s - %(message)s',
#    handlers=[
#        logging.StreamHandler(),  # Terminal output
#        logging.FileHandler('debug_log.txt')  # File output
#    ]
#)
#logger = logging.getLogger(__name__)
# Logging for terminal and file output - ends

# Command-line arguments
parser = argparse.ArgumentParser(description="Keepa Deals Script")
parser.add_argument("--no-cache", action="store_true", help="Force fresh Keepa API calls")
# args = parser.parse_args() # Moved to main()

# Logging - removed this one since we have a new/better one above
#logging.basicConfig(filename='debug_log.txt', level=logging.DEBUG, format='%(asctime)s %(levelname)s: %(message)s')

# Cache config and headers
try:
    with open('config.json') as f:
        config = json.load(f)
        api_key = config['api_key']
        print(f"API key loaded: {api_key[:5]}...")
    with open('headers.json') as f:
        HEADERS = json.load(f)
        logging.debug(f"Loaded headers: {len(HEADERS)} fields")
        print(f"Headers loaded: {len(HEADERS)} fields")
except Exception as e:
    logging.error(f"Startup failed: {str(e)}")
    print(f"Startup failed: {str(e)}")
    sys.exit(1)
# Chunk 1 ends

# Chunk 2 starts
# 2025-05-20: Removed &buyBox=1 from fetch_product URL (commit 95aac66e) to fix Amazon - Current, but stats.current[10] still -1 for ASIN 150137012X despite $6.26 offer. Reverted to commit 31cb7bee setup. Pivoted to New - Current.
# 2025-05-22: Updated offers=100, enhanced logging (commit a03ceb87).
# 2025-05-22: Switched to Python client, offers=100 (commit 69d2801d).
# 2025-05-22: Reverted to HTTP, offers=100, added Python client fallback (commit e1f6f52e).
# 2025-05-22: Increased timeout=60, wait_fixed=10000, sleep=2 to fix timeouts for ASINs 1848638930, B0CS6RL7D6, B0C1VSRNNH.
# 2025-05-26: Added --no-cache flag to force fresh API calls.
# It's hard to inject attempt numbers directly when using the @retry decorator from the 'retrying' library
# without access to its internal state or a more complex setup.
# However, we can log entry and exit/exceptions to see if it's being called multiple times for an ASIN.

# Let's add a global or a class member to track attempts per ASIN if we want to be more explicit,
# but for now, just more detailed logging within the function might reveal multiple calls.

# We will add a specific log at the very start of the function call.
# If the @retry decorator calls this function multiple times for the same ASIN,
# we will see this log message repeated for that ASIN.

@retry(stop_max_attempt_number=3, wait_fixed=10)
def fetch_product(asin, days=365, offers=100, rating=1, history=1):
    global current_available_tokens # Moved to top of function for all reads/writes
    # Increment and log attempt number for this ASIN
    # This requires a way to store attempt counts across calls triggered by @retry for the same ASIN.
    # A simple global dictionary can serve this purpose for now.
    global fetch_product_attempts
    if asin not in fetch_product_attempts:
        fetch_product_attempts[asin] = 0
    fetch_product_attempts[asin] += 1
    attempt_num = fetch_product_attempts[asin]

    logger.info(f"fetch_product: Attempt #{attempt_num} for ASIN {asin} (days={days}, offers={offers}, rating={rating}, history={history}, no_cache={args.no_cache})")

    if not validate_asin(asin):
        # Reset attempt count for this ASIN if it fails validation before any actual attempt
        fetch_product_attempts[asin] = 0 # Or handle as needed - this error is pre-API call
        logging.error(f"Invalid ASIN format: {asin}")
        print(f"Invalid ASIN format: {asin}")
        # Consistent return for validation failure
        rate_limit_info_on_error = {'limit': None, 'remaining': None, 'reset': None, 'error_status_code': 'VALIDATION_ERROR'}
        return {'stats': {'current': [-1] * 30}, 'asin': asin, 'error': True, 'status_code': 'VALIDATION_ERROR', 'message': 'Invalid ASIN format'}, rate_limit_info_on_error

    # print(f"Fetching ASIN {asin}...") # Replaced by logger above
    url = f"https://api.keepa.com/product?key={api_key}&domain=1&asin={asin}&stats={days}&offers={offers}&rating={rating}&history={history}&stock=1&buybox=1"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/90.0.4430.212'}
    try:
        logger.debug(f"fetch_product (Attempt #{attempt_num}): Making HTTP GET request for ASIN {asin} to {url}")
        response = requests.get(url, headers=headers, timeout=60)

        logger.debug(f"fetch_product (Attempt #{attempt_num}): Response status {response.status_code} for ASIN {asin}")
        # Removed logging of ALL RESPONSE HEADERS as Keepa is confirmed not to send rate limit headers we were looking for.
        response.raise_for_status() # Will raise HTTPError for 4xx/5xx, which is a RequestException

        # If raise_for_status() doesn't raise, then status_code is 200 or similar non-error
        fetch_product_attempts[asin] = 0 # Reset on success
        data = response.json()
        products = data.get('products', [])
        if not products:
            logging.error(f"No product data for ASIN {asin} despite 2xx status.")
            print(f"No product data for ASIN {asin} despite 2xx status.")
            rate_limit_info_on_error = { # Simplified rate_limit_info
                'limit': None, 'remaining': None, 'reset': None,
                'error_status_code': response.status_code
            }
            return {'stats': {'current': [-1] * 30}, 'asin': asin, 'error': True, 'status_code': response.status_code, 'message': 'No product data found in response'}, rate_limit_info_on_error

        product = products[0]
        stats = product.get('stats', {})
        current = stats.get('current', [-1] * 30)
        offers = product.get('offers', []) if product.get('offers') is not None else []
        # Reduced verbosity for INFO log, moved raw stats to DEBUG
        logging.info(f"HTTP Stats for ASIN {asin}: Found product data. current_array_length={len(current)}, offers_count={len(offers)}. Stat keys: {list(stats.keys())}")
        logger.debug(f"HTTP Stats for ASIN {asin}: current_data={current}, stats_raw={stats}")
        if len(current) < 11:
            logging.warning(f"Short current array for ASIN {asin}: {current}")
        if current[1] == -1:
            logging.warning(f"Invalid Amazon - Current price for ASIN {asin}: current[1]={current[1]}")

        # Simplified rate_limit_info as Keepa does not send these headers.
        rate_limit_info = {'limit': None, 'remaining': None, 'reset': None}

        # All logic related to parsing Keepa's x-rate-limit-* headers,
        # token discrepancy checks, and dynamic token adjustments has been removed
        # as it's confirmed Keepa does not provide these headers.

        return product, rate_limit_info
    except requests.exceptions.RequestException as e:
        logging.error(f"HTTP Fetch failed for ASIN {asin}: {str(e)}")
        print(f"HTTP Fetch failed for ASIN {asin}: {str(e)}")
        status_code = e.response.status_code if e.response is not None else None
        # Simplified rate_limit_info for errors
        rate_limit_info = {
            'limit': None, 'remaining': None, 'reset': None,
            'error_status_code': status_code
        }
        # Removed specific logging for x-rate-limit-remaining on 429, as it's not expected.
        # General 429 logging remains useful.
        if status_code == 429:
             logger.error(f"ASIN {asin} - 429 ERROR. Script tokens at time of call: {current_available_tokens:.2f}.")
        return {'stats': {'current': [-1] * 30}, 'asin': asin, 'error': True, 'status_code': status_code}, rate_limit_info
    except Exception as e:
        logging.error(f"Generic Fetch failed for ASIN {asin}: {str(e)}")
        print(f"Generic Fetch failed for ASIN {asin}: {str(e)}")
        # For other exceptions, we might not have response headers
        rate_limit_info = {'limit': None, 'remaining': None, 'reset': None, 'error_status_code': None}
        return {'stats': {'current': [-1] * 30}, 'asin': asin, 'error': True, 'status_code': None}, rate_limit_info

# --- Jules: Quota Management Function ---
def update_and_check_quota(logger_instance):
    """
    Updates the available token count based on hourly refill and pauses if tokens are low.
    Uses and modifies global variables: current_available_tokens, last_refill_calculation_time.
    """
    global current_available_tokens
    global last_refill_calculation_time

    # Log entry state immediately
    logger_instance.debug(f"Quota Check (entry): Current available tokens: {current_available_tokens:.2f}, Last refill calc time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_refill_calculation_time))}")

    current_time = time.time()
    time_elapsed_seconds = current_time - last_refill_calculation_time

    # Check if enough time has passed for at least one refill calculation interval
    if time_elapsed_seconds >= REFILL_CALCULATION_INTERVAL_SECONDS:
        # Calculate how many refill intervals have passed
        intervals_passed = int(time_elapsed_seconds // REFILL_CALCULATION_INTERVAL_SECONDS)

        if intervals_passed > 0:
            # Calculate tokens refilled based on per-minute rate and interval duration
            # If REFILL_CALCULATION_INTERVAL_SECONDS is 60, then tokens_per_interval is TOKENS_PER_MINUTE_REFILL
            # If interval is shorter, adjust accordingly (e.g. if 30s interval, tokens_per_interval = TOKENS_PER_MINUTE_REFILL / 2)
            tokens_refilled_per_minute_interval = TOKENS_PER_MINUTE_REFILL * (REFILL_CALCULATION_INTERVAL_SECONDS / 60.0)
            total_refilled = intervals_passed * tokens_refilled_per_minute_interval

            tokens_before_refill = current_available_tokens
            current_available_tokens += total_refilled
            if current_available_tokens > MAX_QUOTA_TOKENS:
                current_available_tokens = MAX_QUOTA_TOKENS

            original_last_refill_time = last_refill_calculation_time
            last_refill_calculation_time += intervals_passed * REFILL_CALCULATION_INTERVAL_SECONDS # Advance by processed intervals

            logger_instance.info(
                f"Quota Refill: Processed {intervals_passed} interval(s) of {REFILL_CALCULATION_INTERVAL_SECONDS}s "
                f"(from {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(original_last_refill_time))}). "
                f"Tokens before: {tokens_before_refill:.2f}. Added {total_refilled:.2f}. Tokens after: {current_available_tokens:.2f}. "
                f"New last refill calc time: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_refill_calculation_time))}"
            )
        else:
            # This case should ideally not be hit if time_elapsed_seconds >= REFILL_CALCULATION_INTERVAL_SECONDS
            logger_instance.debug(f"Quota Check: No full refill interval passed despite elapsed time. Current tokens: {current_available_tokens:.2f}")
    else:
        logger_instance.debug(f"Quota Check: Not enough time for a refill interval. Elapsed: {time_elapsed_seconds:.2f}s. Current tokens: {current_available_tokens:.2f}")

    logger_instance.debug(f"Quota Check (after refill calc): Current available tokens: {current_available_tokens:.2f}")

    # Proactive Pause Logic (remains the same, uses updated current_available_tokens)
    if current_available_tokens < MIN_QUOTA_THRESHOLD_BEFORE_PAUSE:
        logger_instance.warning(
            f"Low quota: {current_available_tokens:.2f} tokens remaining, which is below threshold {MIN_QUOTA_THRESHOLD_BEFORE_PAUSE}. "
            f"Pausing for {DEFAULT_LOW_QUOTA_PAUSE_SECONDS / 60:.1f} minutes."
        )
        time.sleep(DEFAULT_LOW_QUOTA_PAUSE_SECONDS)

        logger_instance.info(f"Quota: Pause complete. Attempting to re-check quota and potential refills...")
        update_and_check_quota(logger_instance) # Recursive call to re-evaluate after pause

    # This function doesn't return anything; it modifies globals and may pause.
# --- End Quota Management Function ---

# --- Jules: Batch Product Fetch Function ---
@retry(stop_max_attempt_number=3, wait_fixed=15000) # Increased wait for batch calls
def fetch_product_batch(asins_list, days=365, offers=100, rating=1, history=1):
    global current_available_tokens # For logging current token state if 429 occurs

    if not asins_list:
        logger.warning("fetch_product_batch called with an empty list of ASINs.")
        return [], {'requestTokens': 0, 'tokensLeft': None, 'refillIn': None, 'refillRate': None, 'error_status_code': 'EMPTY_ASIN_LIST'}, 0

    logger.info(f"fetch_product_batch: Attempting to fetch batch of {len(asins_list)} ASINs: {','.join(asins_list[:3])}...")

    # ASIN validation should ideally happen before forming batches, but double-check here if necessary.
    # For now, assuming valid ASINs are passed.

    comma_separated_asins = ','.join(asins_list)
    url = f"https://api.keepa.com/product?key={api_key}&domain=1&asin={comma_separated_asins}&stats={days}&offers={offers}&rating={rating}&history={history}&stock=1&buybox=1"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/90.0.4430.212'} # Standard User-Agent

    try:
        logger.debug(f"fetch_product_batch: Making HTTP GET request for {len(asins_list)} ASINs to {url}")
        response = requests.get(url, headers=headers, timeout=120) # Increased timeout for batch calls

        logger.debug(f"fetch_product_batch: Response status {response.status_code} for ASINs {','.join(asins_list[:3])}...")
        response.raise_for_status()

        data = response.json()

        # Extract token and rate limit information if available
        # Primary goal is to get 'tokensConsumed'
        tokens_consumed_from_api = data.get('tokensConsumed')
        actual_batch_cost = 0 # Default if not found or not applicable

        if tokens_consumed_from_api is not None:
            actual_batch_cost = int(tokens_consumed_from_api)
            logger.info(f"Batch API call cost {actual_batch_cost} tokens according to 'tokensConsumed' field in response.")
        else:
            # 'tokensConsumed' not found in a successful response. This would be unexpected.
            # For now, fall back to estimation, but this needs monitoring.
            # This part might be removed if Keepa ALWAYS returns tokensConsumed on success.
            actual_batch_cost = len(asins_list) * ESTIMATED_AVG_COST_PER_ASIN_IN_BATCH # Fallback estimation
            logger.warning(f"'tokensConsumed' field NOT found in successful batch response. Using estimated cost: {actual_batch_cost} tokens. This is unexpected.")

        # Store other API info if needed, primarily for error status now
        api_info = {
            'tokensConsumed': tokens_consumed_from_api, # Store what we got
            'error_status_code': None # Will be set in except blocks if error
            # 'tokensLeft', 'refillIn', 'refillRate' are not expected from /product
        }

        products_data = data.get('products', [])
        if not products_data and len(asins_list) > 0: # Successful call but no product data for any ASIN
            logger.error(f"No product data in batch response for ASINs {','.join(asins_list[:3])}... despite 2xx status. Cost was {actual_batch_cost} tokens.")
            error_products = [{'asin': asin, 'error': True, 'status_code': response.status_code, 'message': 'No product data found in batch response'} for asin in asins_list]
            # actual_batch_cost here is what Keepa reported, even if no products were returned.
            return error_products, api_info, actual_batch_cost

        # TODO: Potentially map products back to original ASINs if order is not guaranteed,
        # or if some ASINs in the request might be missing from the response.
        # For now, assuming the 'products' array corresponds to the requested ASINs.
        # If an ASIN in the request yields no data from Keepa, it might just be omitted from the 'products' array.
        # We need to ensure that the main loop can handle this (e.g. by creating placeholders for missing ASINs).

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

        # For accounting, the cost returned is what Keepa said it consumed, or 0 if unknown.
        # The main loop will decide whether to deduct this based on the error type (e.g., deduct for 429 if tokensConsumed > 0).
        cost_to_report = tokens_consumed_on_error

        if status_code == 429:
             logger.error(f"Batch ASINs - 429 ERROR. Script tokens at time of call: {current_available_tokens:.2f}. Keepa reported {tokens_consumed_on_error} tokens consumed for this failed call.")

        error_products = [{'asin': asin, 'error': True, 'status_code': status_code, 'message': str(e)} for asin in asins_list]
        return error_products, api_info_on_error, cost_to_report

    except Exception as e: # Generic exceptions (e.g., JSONDecodeError for successful status but bad body, though less likely here)
        logger.error(f"Generic Fetch failed for batch ASINs {','.join(asins_list[:3])}...: {str(e)}")
        # For truly generic errors, we likely didn't make a Keepa call that would report tokensConsumed.
        api_info_on_error = {'tokensConsumed': None, 'error_status_code': 'GENERIC_SCRIPT_ERROR'}
        # Cost is unknown / 0 as it's likely a script-side issue before or after Keepa call.
        cost_to_report_generic_error = 0
        error_products = [{'asin': asin, 'error': True, 'status_code': 'GENERIC_SCRIPT_ERROR', 'message': str(e)} for asin in asins_list]
        return error_products, api_info_on_error, cost_to_report_generic_error
# --- End Batch Product Fetch Function ---


# Chunk 2 ends

# Global args variable, to be initialized in main
args = None
# The old current_rate_limit_info global and its constants (RATE_LIMIT_REMAINING_THRESHOLD, MIN_TIME_BETWEEN_HEADER_CHECKS_SECONDS)
# are no longer needed with the new local quota system. They are removed.

# Chunk 3 starts
def write_csv(rows, deals, diagnostic=False):
    logger.info(f"Entering write_csv. Number of deals to process: {len(deals)}. Number of rows generated: {len(rows)}.")
    if len(deals) != len(rows) and not diagnostic:
        logger.warning(f"Mismatch in write_csv: len(deals) is {len(deals)} but len(rows) is {len(rows)}. CSV might be incomplete or misaligned.")

    try:
        with open(CSV_PATH, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(HEADERS) # HEADERS is global
            if diagnostic:
                writer.writerow(['No deals fetched'] + ['-'] * (len(HEADERS) - 1))
                logger.info(f"Diagnostic CSV written: Keepa_Deals_Export.csv")
                print(f"Diagnostic CSV written: Keepa_Deals_Export.csv")
            else:
                # Ensure we only try to zip up to the shorter of the two lists if there's a mismatch,
                # though ideally they should be the same length due to placeholder logic.
                num_to_write = min(len(deals), len(rows))
                if len(deals) != len(rows): # Log if we are truncating due to mismatch
                     logger.warning(f"write_csv: Writing {num_to_write} rows due to length mismatch between deals ({len(deals)}) and rows ({len(rows)}).")

                for i in range(num_to_write):
                    deal_obj = deals[i]
                    row_content = rows[i]
                    asin_from_deal = deal_obj.get('asin', 'UNKNOWN_DEAL_ASIN')
                    asin_from_row = row_content.get('ASIN', 'UNKNOWN_ROW_ASIN')

                    # Log a summary of the row being written - changed to DEBUG
                    non_hyphen_row_items = {k: v for k, v in row_content.items() if v != '-'}
                    logger.debug(f"Writing CSV row for ASIN (from deal obj): {asin_from_deal}, ASIN (from row obj): {asin_from_row}. Non-hyphen count: {len(non_hyphen_row_items)}. Keys: {list(non_hyphen_row_items.keys())}")
                    if asin_from_deal != asin_from_row and asin_from_row not in asin_from_deal : # Check if row ASIN is a placeholder like INVALID_ASIN_SKIPPED_...
                        logger.warning(f"ASIN mismatch when writing CSV: Deal ASIN is '{asin_from_deal}', Row ASIN is '{asin_from_row}'.")

                    try:
                        # row_data = row_content.copy() # No need to copy if we're just reading
                        # missing_headers = [h for h in HEADERS if h not in row_data] # Not strictly necessary if row_data.get is used
                        # if missing_headers:
                        #     logger.warning(f"Missing headers in row_content for ASIN {asin_from_row}: {missing_headers[:5]}")

                        # print(f"Writing row for ASIN {asin_from_row}...") # Console print might be too verbose now
                        writer.writerow([row_content.get(header, '-') for header in HEADERS])
                        # logger.debug(f"Wrote row to CSV for ASIN {asin_from_row}") # Can be very verbose
                    except Exception as e:
                        logger.error(f"Failed to write row to CSV for ASIN {asin_from_row} (from deal: {asin_from_deal}): {str(e)}")
                        # Optionally, write a row of hyphens for this failed write
                        # writer.writerow([asin_from_row_or_deal] + ['ERROR_WRITING_ROW'] * (len(HEADERS)-1) )

        logger.info(f"CSV written: Keepa_Deals_Export.csv with {num_to_write if not diagnostic else 0} data rows.")
        print(f"CSV written: Keepa_Deals_Export.csv")
    except Exception as e:
        logger.error(f"Failed to write CSV Keepa_Deals_Export.csv: {str(e)}")
        print(f"Failed to write CSV Keepa_Deals_Export.csv: {str(e)}")
# Chunk 3 ends

# Chunk 4 starts
def main():
    global args, LAST_API_CALL_TIMESTAMP, current_available_tokens, last_refill_calculation_time # Added token globals
    args = parser.parse_args()
    logger = logging.getLogger('KeepaDeals')

    LAST_API_CALL_TIMESTAMP = time.time()

    try:
        logger.info("Starting Keepa_Deals...")
        print("Starting Keepa_Deals...", flush=True)
        time.sleep(2)

        all_deals = []
        page = 0
        while True:
            # --- Pre-call check for fetch_deals_for_deals ---
            update_and_check_quota(logger) # General quota check and refill
            required_tokens_for_deal_page = TOKEN_COST_PER_DEAL_PAGE
            if current_available_tokens < required_tokens_for_deal_page:
                tokens_needed = required_tokens_for_deal_page - current_available_tokens
                refill_rate_per_minute = TOKENS_PER_MINUTE_REFILL
                wait_time_seconds = 0
                if refill_rate_per_minute > 0: # Avoid division by zero
                    wait_time_seconds = math.ceil((tokens_needed / refill_rate_per_minute) * 60) # * 60 because rate is per minute
                else: # Fallback if TOKENS_PER_MINUTE_REFILL is somehow 0
                    wait_time_seconds = DEFAULT_LOW_QUOTA_PAUSE_SECONDS

                logger.warning(
                    f"Insufficient tokens for fetching deal page {page}. "
                    f"Have: {current_available_tokens:.2f}, Need: {required_tokens_for_deal_page}. "
                    f"Waiting for approx. {wait_time_seconds // 60} minutes for tokens to refill."
                )
                time.sleep(wait_time_seconds)
                update_and_check_quota(logger) # Re-check quota after waiting

            logger.info(f"Fetching deals page {page}...")
            print(f"Fetching deals page {page}...", flush=True)

            # MIN_TIME_SINCE_LAST_CALL_SECONDS check for deal calls
            current_time_deal_call = time.time()
            time_since_last_api_call = current_time_deal_call - LAST_API_CALL_TIMESTAMP
            if time_since_last_api_call < MIN_TIME_SINCE_LAST_CALL_SECONDS:
                deal_wait_duration = MIN_TIME_SINCE_LAST_CALL_SECONDS - time_since_last_api_call
                logger.info(f"Pre-emptive pause for deal page fetch: Last API call was {time_since_last_api_call:.2f}s ago. Waiting {deal_wait_duration:.2f}s.")
                time.sleep(deal_wait_duration)

            deals_page = fetch_deals_for_deals(page)
            LAST_API_CALL_TIMESTAMP = time.time() # Update after the call

            if deals_page: # Only deduct tokens if the call was presumably successful (returned data)
                current_available_tokens -= TOKEN_COST_PER_DEAL_PAGE
                logger.info(f"Token consumed for deal page {page}. Cost: {TOKEN_COST_PER_DEAL_PAGE}. Tokens remaining: {current_available_tokens:.2f}")

            if not deals_page:
                logger.info(f"No more deals found on page {page}.")
                print(f"No more deals found on page {page}.", flush=True)
                break
            all_deals.extend(deals_page)
            logger.info(f"Fetched {len(deals_page)} deals from page {page}. Total deals so far: {len(all_deals)}")
            print(f"Fetched {len(deals_page)} deals from page {page}. Total deals so far: {len(all_deals)}", flush=True)
            page += 1
            # The time.sleep(1) here is a small politeness delay, MIN_TIME_SINCE_LAST_CALL_SECONDS handles primary rate limiting.

        deals = all_deals

        # Default limit for testing, can be overridden by processing all deals if this section is commented out.
        MAX_DEALS_TO_PROCESS_FOR_TESTING = 10
        if len(deals) > MAX_DEALS_TO_PROCESS_FOR_TESTING:
            logger.warning(f"TESTING LIMIT ACTIVE: Processing only the first {MAX_DEALS_TO_PROCESS_FOR_TESTING} of {len(deals)} deals.")
            print(f"TESTING LIMIT ACTIVE: Processing only the first {MAX_DEALS_TO_PROCESS_FOR_TESTING} of {len(deals)} deals.", flush=True)
            deals_to_process = deals[:MAX_DEALS_TO_PROCESS_FOR_TESTING]
        else:
            deals_to_process = deals
        # END TEMPORARY LIMIT

        rows = []
        if not deals_to_process: # Check deals_to_process instead of deals
            logger.warning("No deals fetched or all filtered out by temporary limit, writing diagnostic CSV") # Use logger instance
            print("No deals fetched, writing diagnostic CSV", flush=True)
            write_csv([], [], diagnostic=True)
            return
        logger.debug(f"Deals ASINs: {[d.get('asin', '-') for d in deals_to_process[:5]]}") # Use logger instance, refer to deals_to_process
        print(f"Deals ASINs: {[d.get('asin', '-') for d in deals_to_process[:5]]}", flush=True)
        logger.info(f"Starting ASIN processing, found {len(deals_to_process)} deals (after potential temporary limit)") # Use logger instance
        print(f"Starting ASIN processing, found {len(deals_to_process)} deals (after potential temporary limit)", flush=True)
# Logging stuff - ends

        # --- Batch Processing Logic ---
        MAX_ASINS_PER_BATCH = 50 # Default for current testing phase

        valid_deals_to_process = []
        for deal_idx, deal_obj in enumerate(deals_to_process):
            asin = deal_obj.get('asin', '-')
            if not validate_asin(asin):
                logger.warning(f"Skipping invalid ASIN '{asin}' from deal object: {deal_obj}")
                # Placeholder for invalid ASIN will be handled later to ensure correct ordering.
                # rows.append(placeholder_row) # Add placeholder to the final rows list # Removed this line
            else:
                # Store the original deal object with its index for later association
                valid_deals_to_process.append({'original_index': deal_idx, 'asin': asin, 'deal_obj': deal_obj})

        logger.info(f"Collected {len(valid_deals_to_process)} valid ASINs for batch processing.")

        # Create batches of ASINs
        asin_batches = []
        for i in range(0, len(valid_deals_to_process), MAX_ASINS_PER_BATCH):
            batch_deals = valid_deals_to_process[i:i + MAX_ASINS_PER_BATCH]
            asin_batches.append(batch_deals)

        logger.info(f"Created {len(asin_batches)} batches for API calls.")

        all_fetched_products_map = {} # To store fetched product data by ASIN

        batch_idx = 0
        max_retries_for_batch = 2 # Allows 3 attempts total (1 initial + 2 retries)
        batch_retry_counts = [0] * len(asin_batches) # Track retries for each batch

        while batch_idx < len(asin_batches):
            current_batch_deals = asin_batches[batch_idx]
            batch_asins = [d['asin'] for d in current_batch_deals]

            logger.info(f"Processing Batch {batch_idx + 1}/{len(asin_batches)} (Attempt {batch_retry_counts[batch_idx] + 1}) with {len(batch_asins)} ASINs: {batch_asins[:3]}...")

            # --- Quota Management & Throttling (Per Batch) ---
            update_and_check_quota(logger) # General quota check and refill

            # Explicit pre-call check for product batch
            required_tokens_for_batch = len(batch_asins) * ESTIMATED_AVG_COST_PER_ASIN_IN_BATCH # Use new estimate
            if current_available_tokens < required_tokens_for_batch:
                tokens_needed_for_batch = required_tokens_for_batch - current_available_tokens
                refill_rate_per_minute_batch = TOKENS_PER_MINUTE_REFILL
                wait_time_seconds_batch = 0
                if refill_rate_per_minute_batch > 0:
                    wait_time_seconds_batch = math.ceil((tokens_needed_for_batch / refill_rate_per_minute_batch) * 60) # * 60 because rate is per minute
                else: # Fallback if TOKENS_PER_MINUTE_REFILL is somehow 0
                    wait_time_seconds_batch = DEFAULT_LOW_QUOTA_PAUSE_SECONDS

                logger.warning(
                    f"Insufficient tokens for product batch {batch_idx + 1}. "
                    f"Have: {current_available_tokens:.2f}, Need: {required_tokens_for_batch}. "
                    f"Waiting for approx. {wait_time_seconds_batch // 60} minutes for tokens to refill."
                )
                time.sleep(wait_time_seconds_batch)
                update_and_check_quota(logger) # Re-check quota after specific wait

            current_time_batch_call = time.time()
            time_since_last_api_call_batch = current_time_batch_call - LAST_API_CALL_TIMESTAMP
            if time_since_last_api_call_batch < MIN_TIME_SINCE_LAST_CALL_SECONDS:
                batch_wait_duration = MIN_TIME_SINCE_LAST_CALL_SECONDS - time_since_last_api_call_batch
                logger.info(f"Pre-emptive pause for product batch: Last API call was {time_since_last_api_call_batch:.2f}s ago. Waiting {batch_wait_duration:.2f}s.")
                time.sleep(batch_wait_duration)

            batch_product_data_list, api_info, actual_batch_cost = fetch_product_batch(batch_asins)
            LAST_API_CALL_TIMESTAMP = time.time()
            # global current_available_tokens # Already global from main's declaration

            batch_had_critical_error = False
            if api_info.get('error_status_code') and api_info.get('error_status_code') != 200:
                batch_had_critical_error = True
                logger.error(f"Batch API call for ASINs {batch_asins[:3]}... failed with status code: {api_info.get('error_status_code')}.")

            if not batch_had_critical_error:
                current_available_tokens -= actual_batch_cost
                logger.info(f"Tokens consumed for BATCH. Cost: {actual_batch_cost}. Tokens remaining: {current_available_tokens:.2f}.")
                logger.debug(f"Pausing for {POST_BATCH_SUCCESS_DELAY_SECONDS}s after successful batch fetch.")
                time.sleep(POST_BATCH_SUCCESS_DELAY_SECONDS)

                # Store successfully fetched products
                temp_product_map = {p['asin']: p for p in batch_product_data_list if isinstance(p, dict) and 'asin' in p}
                for deal_info in current_batch_deals:
                    asin_to_map = deal_info['asin']
                    if asin_to_map in temp_product_map:
                        all_fetched_products_map[asin_to_map] = temp_product_map[asin_to_map]
                    else:
                        logger.warning(f"ASIN {asin_to_map} was requested in batch but not found in response products. Marking as error.")
                        all_fetched_products_map[asin_to_map] = {'asin': asin_to_map, 'error': True, 'status_code': 'MISSING_IN_BATCH_RESPONSE', 'message': 'ASIN not found in successful batch response products list.'}

                batch_idx += 1 # Move to next batch
                if batch_idx < len(asin_batches): # Reset retry counter for the *next* batch
                    batch_retry_counts[batch_idx] = 0
                continue # Continue to next iteration of while loop (either next batch or end)

            else: # Batch had a critical error
                # actual_batch_cost here is the tokensConsumed reported by Keepa for the FAILED call, or 0 if it couldn't be determined.
                if actual_batch_cost > 0:
                    current_available_tokens -= actual_batch_cost
                    logger.warning(
                        f"Batch fetch critically failed (status: {api_info.get('error_status_code')}) but Keepa reported {actual_batch_cost} tokens consumed for this attempt. "
                        f"Deducting. Tokens remaining: {current_available_tokens:.2f}."
                    )
                else:
                    # Log that it failed but no tokens were reported consumed for *this specific failed attempt*
                    logger.error(
                        f"Batch fetch critically failed for ASINs: {batch_asins[:3]}... "
                        f"No tokens reported by Keepa as consumed for this specific failed attempt (Reported cost for attempt: {actual_batch_cost}, status: {api_info.get('error_status_code')})."
                    )

                if api_info.get('error_status_code') == 429:
                    if batch_retry_counts[batch_idx] < max_retries_for_batch: # max_retries_for_batch is 2 (for 3 total attempts)
                        batch_retry_counts[batch_idx] += 1 # Increment before using for pause logic

                        pause_duration_seconds = 0
                        if batch_retry_counts[batch_idx] == 1: # This is the first retry (2nd attempt overall)
                            pause_duration_seconds = 900 # 15 minutes
                        elif batch_retry_counts[batch_idx] == 2: # This is the second retry (3rd attempt overall)
                            pause_duration_seconds = 1800 # 30 minutes

                        logger.error(f"Batch API call received 429 error. Attempt {batch_retry_counts[batch_idx] + 1}/3 for this batch. Initiating {pause_duration_seconds // 60}-minute recovery pause.")
                        time.sleep(pause_duration_seconds)
                        logger.info(f"Recovery pause complete ({pause_duration_seconds // 60} mins). Updating quota before retrying batch.")
                        update_and_check_quota(logger)
                        # Loop continues, will retry current batch_idx
                    else: # This means batch_retry_counts[batch_idx] was already 2, and the 3rd attempt also failed
                        logger.error(f"Batch API call received 429 error on attempt 3/3 for batch {batch_idx + 1}. Max retries reached. Skipping this batch.")
                        # Populate all_fetched_products_map with error objects for this skipped batch
                        for deal_info in current_batch_deals:
                            all_fetched_products_map[deal_info['asin']] = {'asin': deal_info['asin'], 'error': True, 'status_code': 429, 'message': 'Batch skipped after max retries due to 429 error'}
                        batch_idx += 1 # Move to next batch
                        if batch_idx < len(asin_batches): # Reset retry counter for the *next* batch
                            batch_retry_counts[batch_idx] = 0
                else: # Other critical error (not 429)
                    logger.debug(f"Pausing for {POST_BATCH_ERROR_DELAY_SECONDS}s after failed batch fetch (non-429 error).")
                    time.sleep(POST_BATCH_ERROR_DELAY_SECONDS)
                    # Populate all_fetched_products_map with error objects for this failed batch
                    for deal_info in current_batch_deals:
                        error_msg_detail = api_info.get('message', 'Batch API call failed with non-429 error')
                        all_fetched_products_map[deal_info['asin']] = {'asin': deal_info['asin'], 'error': True, 'status_code': api_info.get('error_status_code', 'BATCH_CALL_FAILED_NON_429'), 'message': error_msg_detail}
                    batch_idx += 1 # Move to next batch
                    if batch_idx < len(asin_batches): # Reset retry counter for the *next* batch
                        batch_retry_counts[batch_idx] = 0
                continue # Continue to next iteration of while loop

        # --- Process all deals using the fetched product data ---
        # Iterate through the original deals_to_process to maintain order and include placeholders for skipped ASINs
        temp_rows_data = [] # Temporary list to hold processed row data with original indices

        for deal_info in valid_deals_to_process: # These are only the deals for which we attempted a fetch
            original_deal_obj = deal_info['deal_obj']
            asin = deal_info['asin']

            product = all_fetched_products_map.get(asin)

            if not product or product.get('error'): # This now correctly catches errors from all_fetched_products_map
                logger.error(f"Incomplete or error in product data for ASIN {asin}. Product: {product}")
                placeholder_row_content = {'ASIN': asin}
                for header_key in HEADERS:
                    if header_key not in placeholder_row_content:
                        placeholder_row_content[header_key] = '-'
                temp_rows_data.append({'original_index': deal_info['original_index'], 'data': placeholder_row_content})
                continue

            # Jules: Modified for debugging FBA Pick&Pack Fee - Log raw product data for a specific ASIN
            TEST_ASIN_FOR_RAW_LOG = '1562243179' # Target ASIN for raw data logging
            if asin == TEST_ASIN_FOR_RAW_LOG:
                if product and isinstance(product, dict) and not product.get('error'):
                    logger.info(f"RAW_PRODUCT_DATA_{asin}: {json.dumps(product)}")
                else:
                    logger.info(f"RAW_PRODUCT_DATA_{asin}: Product data error/missing for raw log. Data: {product}")

            # Logging for Last Used price update from product_data (already adapted for product structure)
            try:
                # The product structure from batch might be directly the item, not nested under 'products'[0] like single fetch.
                # Adjusting path if product is the direct item from batch.
                # fetch_product_batch returns a list of product items.
                # The 'product' variable here IS one of those items.
                if product and isinstance(product, dict) and \
                   'csv' in product and isinstance(product['csv'], list) and \
                   len(product['csv']) > 2 and \
                   isinstance(product['csv'][2], list) and \
                   len(product['csv'][2]) > 0:
                    last_used_entry = product['csv'][2][-1]
                    if isinstance(last_used_entry, list) and len(last_used_entry) > 0:
                        logger.info(f"ASIN: {asin} - Last Used price update from product_data.csv[2]: {last_used_entry[0]}")
                # Warnings for missing paths handled by individual functions or get_stat_value
            except (KeyError, IndexError, TypeError) as e:
                 logger.warning(f"ASIN: {asin} - Error accessing product_data.csv[2] for Used price: {e}")

            row = {}
            try:
                for header, func in zip(HEADERS, FUNCTION_LIST):
                    if func:
                        try:
                            # Call func with appropriate arguments
                            if header == 'last update' or header == 'last price change':
                                # These functions take original_deal_obj, config, logger, and product
                                result = func(original_deal_obj, config, logger, product)
                            elif header == 'Deal found':
                                # deal_found takes original_deal_obj, config, and logger
                                result = func(original_deal_obj, config, logger)
                            elif header == 'Percent Down 90':
                                result = func(product)
                            else: # Most other functions take only product data
                                result = func(product) # Changed input_data_for_func to product for clarity

                            logger.debug(f"ASIN {asin}, Header: {header}, Func: {func.__name__}, Result: {result}")
                            row.update(result)
                        except Exception as e:
                            logger.error(f"Function {func.__name__} failed for ASIN {asin}, header '{header}': {e}")
                            row[header] = '-'

                non_hyphen_items = {k: v for k, v in row.items() if v != '-'}
                logger.debug(f"ASIN {asin}: PRE-APPEND main row. Non-hyphen count: {len(non_hyphen_items)}. Keys: {list(non_hyphen_items.keys())}")
                if not non_hyphen_items and asin == product.get('asin'):
                    logger.warning(f"ASIN {asin}: Row for valid product is all hyphens. Error: {product.get('error')}, Status: {product.get('status_code')}")

                # Ensure ASIN in the row is clean and correctly sourced from the iteration's 'asin' variable
                # This 'asin' variable comes from valid_deals_to_process and is the definitive ASIN for this row.
                if 'ASIN' not in row or row.get('ASIN') != asin:
                    if 'ASIN' in row: # It exists but is different or formatted incorrectly
                        logger.warning(
                            f"ASIN {asin}: The 'ASIN' field in the processed row ('{row.get('ASIN')}') "
                            f"differs from or is not the primary source ASIN ('{asin}'). Correcting."
                        )
                    else: # ASIN field was not populated by any function
                        logger.debug(f"ASIN {asin}: 'ASIN' field not populated by functions. Setting from source ASIN.")
                    row['ASIN'] = asin # Set/Overwrite with the clean source ASIN

                temp_rows_data.append({'original_index': deal_info['original_index'], 'data': row})

            except Exception as e:
                logger.error(f"Error processing ASIN {asin} (outer loop): {e}")
                placeholder_row_content = {'ASIN': asin}
                # The invalid 'else' block and the line below it were removed here.
                # logger.error(f"Invalid product data structure in batch response: {product_data}")

        # --- Construct the final list of rows for CSV writing ---
        # Initialize final_processed_rows with None to match the length of original deals_to_process
        final_processed_rows = [None] * len(deals_to_process)

        # Populate with data from temp_rows_data using original_index
        for item in temp_rows_data:
            idx = item['original_index']
            if 0 <= idx < len(final_processed_rows):
                final_processed_rows[idx] = item['data']
            else:
                logger.error(f"Original index {idx} from temp_rows_data is out of bounds for final_processed_rows (len: {len(final_processed_rows)}). Data: {item['data']}")

        # Fill in placeholders for any items that were skipped before batch processing (e.g., due to invalid ASIN format)
        # These items would not be in valid_deals_to_process and thus not in temp_rows_data.
        for i, deal_obj in enumerate(deals_to_process):
            if final_processed_rows[i] is None:
                # This deal was filtered out before batching (e.g. invalid ASIN format by validate_asin)
                # or some other reason it wasn't in valid_deals_to_process.
                asin_for_placeholder = deal_obj.get('asin', f'UNKNOWN_ASIN_AT_INDEX_{i}')
                logger.warning(f"Creating final placeholder for ASIN '{asin_for_placeholder}' (original index {i}) as it was not in processed temp_rows_data.")
                placeholder = {'ASIN': f"SKIPPED_OR_ERROR_ASIN_{asin_for_placeholder[:10]}"}
                for header_key in HEADERS:
                    if header_key not in placeholder: # Ensure ASIN key from placeholder isn't overwritten if already set
                        placeholder[header_key] = '-'
                final_processed_rows[i] = placeholder

        # Now, final_processed_rows should have one entry for every deal in deals_to_process,
        # either a processed row or a placeholder.
        write_csv(final_processed_rows, deals_to_process)
        logger.info("Writing CSV...")
        print("Writing CSV...")
        logger.info("Script completed!") # Use logger instance
        print("Script completed!")
        print(f"Processed ASINs: {[row.get('ASIN', '-') for row in rows]}")
    except Exception as e:
        logger.error(f"Main failed: {str(e)}") # Use logger instance
        print(f"Main failed: {str(e)}")
        sys.exit(1)
# Chunk 4 ends

if __name__ == "__main__":
    main()

#### END of Keepa_Deals.py ####