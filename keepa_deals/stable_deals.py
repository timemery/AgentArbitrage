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
        
        return {'Deal found': toronto_dt.strftime('%Y-%m-%d %H:%M:%S')}
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
        # Indices in currentSince for Used conditions (excluding Acceptable):
        # 2 (Used), 19 (Used-Like New), 20 (Used-Very Good), 21 (Used-Good)
        # These correspond to stats.current indices.
        relevant_current_since_indices = [2, 19, 20, 21] # Used, Used-LikeNew, Used-VeryGood, Used-Good
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

#### END of stable_deals.py ####