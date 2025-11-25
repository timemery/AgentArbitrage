# stable_deals.py 
# (Last update: Version 8)

import logging
import json
from retrying import retry
from datetime import datetime, timedelta
from pytz import timezone

# Configure logging - REMOVED basicConfig to avoid overriding Keepa_Deals.py settings.
# Each module should use getLogger.
logger = logging.getLogger(__name__)

# Constants
KEEPA_EPOCH = datetime(2011, 1, 1)
TORONTO_TZ = timezone('America/Toronto')

def validate_asin(asin):
    if not isinstance(asin, str) or len(asin) != 10 or not asin.isalnum():
        logger.error(f"Invalid ASIN format: {asin}")
        return False
    return True

# Do not modify fetch_deals_for_deals! It mirrors the "Show API query" (https://api.keepa.com/deal), with critical parameters.
@retry(stop_max_attempt_number=3, wait_fixed=5000)
def fetch_deals_for_deals(page, api_key):
    logger.debug(f"Fetching deals page {page} for Percent Down 90...")
    print(f"Fetching deals page {page} for Percent Down 90...")
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
            print(f"Deal fetch failed: {response.status_code}, {response.text}")
            return []
        data = response.json()
        deals = data.get('deals', {}).get('dr', [])
        logger.debug(f"Fetched {len(deals)} deals: {[d.get('asin', '-') for d in deals]}")
        logger.debug(f"Deal response structure: {list(data.get('deals', {}).keys())}")
        logger.debug(f"All deal keys: {[list(d.keys()) for d in deals]}")
        logger.debug(f"Deals data: {[{'asin': d.get('asin', '-'), 'current': d.get('current', []), 'current[9]': d.get('current', [-1] * 20)[9] if len(d.get('current', [])) > 9 else -1, 'current[1]': d.get('current', [-1] * 20)[1] if len(d.get('current', [])) > 1 else -1} for d in deals]}")
        print(f"Fetched {len(deals)} deals")
        return deals
    except Exception as e:
        logger.error(f"Deal fetch exception: {str(e)}")
        print(f"Deal fetch exception: {str(e)}")
        return []
        
# Deal Found starts
def deal_found(deal_object, logger_param=None): # Renamed logger to logger_param to avoid conflict
    # Use logger_param if provided, otherwise use the module-level logger
    current_logger = logger_param if logger_param else logger
    
    asin = deal_object.get('asin', 'Unknown ASIN')
    ts = deal_object.get('creationDate', 0)
    current_logger.debug(f"Deal found - raw ts={ts}")
    if ts <= 100000: # If timestamp is invalid or too old
        dt = None
    else:
        dt = KEEPA_EPOCH + timedelta(minutes=ts) # This is a naive datetime, assumed to be UTC

    if dt:
        utc_dt = timezone('UTC').localize(dt) # Make it timezone-aware UTC
        toronto_dt = utc_dt.astimezone(TORONTO_TZ) # Convert to Toronto time
        
        func_name = 'deal_found'
        current_logger.debug(f"ASIN: {asin} - Timezone Debug ({func_name}) - KEEPA_EPOCH.tzinfo: {KEEPA_EPOCH.tzinfo}")
        current_logger.debug(f"ASIN: {asin} - Timezone Debug ({func_name}) - dt (naive UTC from Keepa): {dt.isoformat()}")
        current_logger.debug(f"ASIN: {asin} - Timezone Debug ({func_name}) - utc_dt (aware UTC): {utc_dt.isoformat()}")
        current_logger.debug(f"ASIN: {asin} - Timezone Debug ({func_name}) - TORONTO_TZ object: {TORONTO_TZ}")
        current_logger.debug(f"ASIN: {asin} - Timezone Debug ({func_name}) - toronto_dt (converted to Toronto): {toronto_dt.isoformat()}")
        current_logger.debug(f"ASIN: {asin} - Timezone Debug ({func_name}) - toronto_dt.tzinfo: {toronto_dt.tzinfo}")
        current_logger.debug(f"ASIN: {asin} - Timezone Debug ({func_name}) - toronto_dt.utcoffset(): {toronto_dt.utcoffset()}")
        
        return {'Deal found': toronto_dt.isoformat()}
    else:
        return {'Deal found': '-'}
# Deal Found ends
# Last update starts
@retry(stop_max_attempt_number=3, wait_fixed=5000)
def last_update(deal_object, logger_param, product_data=None): # Renamed logger to logger_param
    current_logger = logger_param if logger_param else logger # Use passed logger or module logger

    asin = deal_object.get('asin', product_data.get('asin', 'Unknown ASIN') if product_data else 'Unknown ASIN')
    
    possible_timestamps = []
    sources_checked = []

    # 1. product_data['products'][0]['lastUpdate']
    if product_data and isinstance(product_data, dict) and \
       product_data.get('products') and isinstance(product_data['products'], list) and \
       len(product_data['products']) > 0 and isinstance(product_data['products'][0], dict) and \
       'lastUpdate' in product_data['products'][0]:
        ts_product_general = product_data['products'][0]['lastUpdate']
        if isinstance(ts_product_general, (int, float)) and ts_product_general > 100000:
            possible_timestamps.append(ts_product_general)
            sources_checked.append(f"product_data.products[0].lastUpdate ({ts_product_general})")
            current_logger.debug(f"ASIN: {asin} - Found ts_product_general: {ts_product_general}")
        else:
            current_logger.debug(f"ASIN: {asin} - ts_product_general ({ts_product_general}) is invalid or None.")

    # 2. deal_object.get('lastUpdate')
    ts_deal_general = deal_object.get('lastUpdate')
    if isinstance(ts_deal_general, (int, float)) and ts_deal_general > 100000:
        possible_timestamps.append(ts_deal_general)
        sources_checked.append(f"deal_object.lastUpdate ({ts_deal_general})")
        current_logger.debug(f"ASIN: {asin} - Found ts_deal_general: {ts_deal_general}")
    else:
        current_logger.debug(f"ASIN: {asin} - ts_deal_general ({ts_deal_general}) is invalid or None.")

    # 3. product_data.get('stats', {}).get('lastOffersUpdate')
    if product_data and isinstance(product_data, dict) and product_data.get('stats'):
        ts_offers_update = product_data['stats'].get('lastOffersUpdate')
        if isinstance(ts_offers_update, (int, float)) and ts_offers_update > 100000: # This is also a Keepa minute timestamp
            possible_timestamps.append(ts_offers_update)
            sources_checked.append(f"product_data.stats.lastOffersUpdate ({ts_offers_update})")
            current_logger.debug(f"ASIN: {asin} - Found ts_offers_update: {ts_offers_update}")
        else:
            current_logger.debug(f"ASIN: {asin} - ts_offers_update ({ts_offers_update}) from product_data.stats is invalid or None.")

    if not possible_timestamps:
        current_logger.error(f"ASIN: {asin} - No valid timestamps found for last_update from any source. Sources checked: {sources_checked if sources_checked else 'None'}.")
        return {'last update': '-'}

    latest_ts = max(possible_timestamps)
    current_logger.info(f"ASIN: {asin} - last_update: Selected latest_ts={latest_ts} from candidates {possible_timestamps}. Sources considered: {sources_checked}")
    
    # Ensure ts is used for the rest of the function, not latest_ts directly before this check
    ts = latest_ts # This is the chosen final timestamp in Keepa minutes.
    
    if ts <= 100000: # Should be redundant if checks above are > 100000, but good failsafe
        current_logger.error(f"ASIN: {asin} - No valid lastUpdate after considering all sources (final ts={ts})")
        return {'last update': '-'}
    try:
        dt = KEEPA_EPOCH + timedelta(minutes=ts) # This is a naive datetime, assumed to be UTC
        utc_dt = timezone('UTC').localize(dt) # Make it timezone-aware UTC
        toronto_dt = utc_dt.astimezone(TORONTO_TZ) # Convert to Toronto time
        
        current_logger.debug(f"ASIN: {asin} - Timezone Debug - KEEPA_EPOCH.tzinfo: {KEEPA_EPOCH.tzinfo}")
        current_logger.debug(f"ASIN: {asin} - Timezone Debug - dt (naive UTC from Keepa): {dt.isoformat()}")
        current_logger.debug(f"ASIN: {asin} - Timezone Debug - utc_dt (aware UTC): {utc_dt.isoformat()}")
        current_logger.debug(f"ASIN: {asin} - Timezone Debug - TORONTO_TZ object: {TORONTO_TZ}")
        current_logger.debug(f"ASIN: {asin} - Timezone Debug - toronto_dt (converted to Toronto): {toronto_dt.isoformat()}")
        current_logger.debug(f"ASIN: {asin} - Timezone Debug - toronto_dt.tzinfo: {toronto_dt.tzinfo}")
        current_logger.debug(f"ASIN: {asin} - Timezone Debug - toronto_dt.utcoffset(): {toronto_dt.utcoffset()}")
        
        formatted = toronto_dt.strftime('%Y-%m-%d %H:%M:%S')
        current_logger.debug(f"last update result: {formatted}")
        return {'last update': formatted}
    except Exception as e:
        current_logger.error(f"last_update failed: {str(e)}")
        return {'last update': '-'}
# Last update ends
# Last price change starts
@retry(stop_max_attempt_number=3, wait_fixed=5000)
def last_price_change(deal_object, logger_param=None, product_data=None): # Renamed logger, added product_data
    current_logger = logger_param if logger_param else logger # Use passed logger or module logger

    asin = deal_object.get('asin', product_data.get('asin', 'Unknown ASIN') if product_data else 'Unknown ASIN')
    
    latest_ts = -1
    source_description = "No valid timestamp found"

    # Prioritize product_data and its 'csv' field
    if product_data and isinstance(product_data, dict) and \
       product_data.get('products') and isinstance(product_data['products'], list) and \
       len(product_data['products']) > 0 and isinstance(product_data['products'][0], dict) and \
       'csv' in product_data['products'][0] and isinstance(product_data['products'][0]['csv'], list):
        
        product_csv_data = product_data['products'][0]['csv']
        # Indices for AMAZON (0), NEW (1), USED (2), NEW_FBA (10), NEW_FBM (11)
        # Refer to Keepa API documentation for full list of CSV indices.
        # We will also check common ones like:
        # LIGHTNING_DEALS (3), WAREHOUSE (4), NEW_SUPER_FAST_SHIPPING (5), USED_LIKE_NEW (6),
        # Check 'USED' (2), 'USED_LIKE_NEW' (6), 'USED_VERY_GOOD' (7), 'USED_GOOD' (8).
        relevant_used_csv_indices = [2, 6, 7, 8]
        
        timestamps_from_csv = []
        current_logger.debug(f"ASIN: {asin} - Checking product_data.csv for used item timestamps using indices: {relevant_used_csv_indices}")
        for index in relevant_used_csv_indices:
            if index < len(product_csv_data) and isinstance(product_csv_data[index], list) and product_csv_data[index]:
                last_entry = product_csv_data[index][-1]
                if isinstance(last_entry, list) and len(last_entry) > 0:
                    ts_val = last_entry[0]
                    if isinstance(ts_val, (int, float)) and ts_val > 100000:
                        timestamps_from_csv.append(ts_val)
                        current_logger.debug(f"ASIN: {asin} - Found product_data.csv timestamp for used index {index}: {ts_val}")
        
        if timestamps_from_csv:
            latest_ts = max(timestamps_from_csv)
            source_description = f"product_data.csv (max of {len(timestamps_from_csv)} used item timestamps from indices {relevant_used_csv_indices})"
            current_logger.info(f"ASIN: {asin} - Using product_data.csv for last used price change. Max timestamp: {latest_ts}. All found: {timestamps_from_csv}")

    # Fallback to deal_object.currentSince if no valid ts from product_data.csv for used items
    if latest_ts <= 100000:
        current_logger.info(f"ASIN: {asin} - No valid used item timestamp from product_data.csv (latest_ts={latest_ts}). Falling back to deal_object.currentSince for used items.")
        current_since_array = deal_object.get('currentSince', [])
        # Indices in currentSince for Used conditions (including Acceptable):
        # 2 (Used), 19 (Used-Like New), 20 (Used-Very Good), 21 (Used-Good), 22 (Used-Acceptable)
        # These correspond to stats.current indices.
        relevant_current_since_indices = [2, 19, 20, 21, 22] # Used, Used-LikeNew, Used-VeryGood, Used-Good, Used-Acceptable
        valid_current_since_ts = []

        current_logger.debug(f"ASIN: {asin} - Checking deal_object.currentSince for used item timestamps using base indices: {relevant_current_since_indices}")
        if current_since_array and isinstance(current_since_array, list):
            for i in relevant_current_since_indices:
                if i < len(current_since_array):
                    ts_val = current_since_array[i]
                    if isinstance(ts_val, (int, float)) and ts_val > 100000:
                        valid_current_since_ts.append(ts_val)
                        current_logger.debug(f"ASIN: {asin} - Found deal_object.currentSince timestamp for used index {i}: {ts_val}")
                else:
                    current_logger.debug(f"ASIN: {asin} - deal_object.currentSince index {i} out of bounds (len: {len(current_since_array)}).")
            
            # Check for Used Buy Box timestamp
            # deal_object.current[14] corresponds to product.stats.current[14] -> buyBoxIsUsed (1 if true)
            # deal_object.currentSince[32] corresponds to product.stats.current[32] -> buyBoxUsedPrice timestamp
            current_stats_array = deal_object.get('current', []) # This comes from the /deal endpoint's deal_object
            # Ensure 'current' itself is a list and has enough elements.
            # The 'product_data' (from /product endpoint) has product.stats.current, but here we use deal_object.current.
            # The structure of deal_object.current is: [AMAZON, NEW, USED, ... , buyBoxIsUsed at index 14, ... buyBoxUsedPrice at index 32]
            # This mapping needs to be precise. Assuming deal_object.current has a similar structure to product.stats.current for these specific indices.
            
            buy_box_is_used_index = 14 # Index for buyBoxIsUsed in the 'current' array of a deal object or product stats
            buy_box_used_price_ts_index = 32 # Index for buyBoxUsedPrice timestamp in 'currentSince'
            
            if len(current_stats_array) > buy_box_is_used_index and current_stats_array[buy_box_is_used_index] == 1: # buyBoxIsUsed is true
                current_logger.debug(f"ASIN: {asin} - Buy Box is Used (deal_object.current[{buy_box_is_used_index}]==1). Checking currentSince[{buy_box_used_price_ts_index}] for Used Buy Box timestamp.")
                if len(current_since_array) > buy_box_used_price_ts_index:
                    ts_val_buy_box_used = current_since_array[buy_box_used_price_ts_index]
                    if isinstance(ts_val_buy_box_used, (int, float)) and ts_val_buy_box_used > 100000:
                        valid_current_since_ts.append(ts_val_buy_box_used)
                        current_logger.debug(f"ASIN: {asin} - Found deal_object.currentSince timestamp for Used Buy Box (index {buy_box_used_price_ts_index}): {ts_val_buy_box_used}")
                    else:
                        current_logger.debug(f"ASIN: {asin} - Used Buy Box timestamp (currentSince[{buy_box_used_price_ts_index}]) is invalid or not recent: {ts_val_buy_box_used}")
                else:
                    current_logger.debug(f"ASIN: {asin} - currentSince array too short (len: {len(current_since_array)}) to check index {buy_box_used_price_ts_index} for Used Buy Box.")
            else:
                buy_box_is_used_val = current_stats_array[buy_box_is_used_index] if len(current_stats_array) > buy_box_is_used_index else 'N/A'
                current_logger.debug(f"ASIN: {asin} - Buy Box is not Used (deal_object.current[{buy_box_is_used_index}]={buy_box_is_used_val}) or current array too short. Skipping Used Buy Box timestamp check.")

        if valid_current_since_ts:
            latest_ts = max(valid_current_since_ts)
            source_description = f"deal_object.currentSince (max of {len(valid_current_since_ts)} used item timestamps including potential Used Buy Box)"
            current_logger.info(f"ASIN: {asin} - Using deal_object.currentSince for last used price change. Max timestamp: {latest_ts}. All considered: {valid_current_since_ts}")
        else:
            current_logger.warning(f"ASIN: {asin} - No valid used item timestamps in deal_object.currentSince from specified indices (incl. Used Buy Box if applicable). Array was: {current_since_array}")

    current_logger.debug(f"ASIN: {asin} - last used price change - selected raw ts={latest_ts} from {source_description}")
    
    if latest_ts <= 100000: 
        log_message = f"ASIN: {asin} - No valid last *used* price change timestamp found from any source (final ts={latest_ts})"
        current_logger.error(log_message)
        return {'last price change': '-'}
    
    try:
        dt = KEEPA_EPOCH + timedelta(minutes=latest_ts) 
        utc_dt = timezone('UTC').localize(dt) 
        toronto_dt = utc_dt.astimezone(TORONTO_TZ)

        func_name = 'last_price_change' 
        # Reduced some redundant timezone logging for brevity, main conversion steps are clear.
        current_logger.debug(f"ASIN: {asin} - Timezone Debug ({func_name}) - dt (naive UTC): {dt.isoformat()}, utc_dt (aware UTC): {utc_dt.isoformat()}, toronto_dt: {toronto_dt.isoformat()}")

        formatted = toronto_dt.strftime('%Y-%m-%d %H:%M:%S')
        current_logger.info(f"ASIN: {asin} - last price change (focused on used) result: {formatted} (from ts {latest_ts} via {source_description})")
        return {'last price change': formatted}
    except Exception as e:
        current_logger.error(f"ASIN: {asin} - last_price_change (focused on used) failed during date conversion for ts {latest_ts}: {str(e)}")
        return {'last price change': '-'}
# Last price change ends

# Jules: "Please ensure the get_condition function in this file matches the block I sent in my last message. For clarity, here it is again. This is the correct and final version:"
# Condition starts
def get_condition(product_data, logger_param=None):
    current_logger = logger_param if logger_param else logger
    asin = product_data.get('asin', 'Unknown ASIN')

    if not product_data or not isinstance(product_data.get('offers'), list) or not product_data['offers']:
        current_logger.warning(f"ASIN: {asin} - Product data has no 'offers' list. Cannot determine condition.")
        return {'Condition': '-'}

    offers = product_data['offers']

    condition_mapping = {
        1: "New", 2: "Used, like new", 3: "Used, very good", 4: "Used, good", 5: "Used, acceptable",
        6: "Refurbished", 7: "Collectible, like new", 8: "Collectible, very good", 9: "Collectible, good", 10: "Collectible, acceptable",
    }

    lowest_price = float('inf')
    best_condition_code = None

    for offer in offers:
        offer_history = offer.get('offerCSV', [])
        if len(offer_history) < 2:
            continue

        try:
            price = int(offer_history[-2])
            shipping = int(offer_history[-1])
            if shipping == -1: shipping = 0
            total_price = price + shipping

            if total_price < lowest_price:
                lowest_price = total_price
                best_condition_code = offer.get('condition')

        except (ValueError, IndexError) as e:
            current_logger.debug(f"ASIN: {asin} - Could not parse price from offerCSV for one offer. Error: {e}. OfferCSV: {offer_history}")
            continue

    if best_condition_code is not None:
        if best_condition_code in condition_mapping:
            condition_str = condition_mapping[best_condition_code]
            current_logger.info(f"ASIN: {asin} - Found lowest priced offer at ${lowest_price/100:.2f} with condition: {condition_str} ({best_condition_code})")
            
            if "Used, " in condition_str:
                condition_str = condition_str.replace("Used, ", "")
            elif "Collectible, " in condition_str:
                condition_str = condition_str.replace("Collectible, ", "C-")
            return {'Condition': condition_str}
        else:
            current_logger.warning(f"ASIN: {asin} - Found lowest priced offer but condition code '{best_condition_code}' is unknown.")
            return {'Condition': f"Unknown ({best_condition_code})"}
    else:
        current_logger.warning(f"ASIN: {asin} - No valid offers found to determine condition.")
        return {'Condition': '-'}
# Condition ends

#### END of stable_deals.py ####