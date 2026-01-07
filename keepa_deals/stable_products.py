# stable_products.py
# (Last update: Version 5)

# Unchanged imports and globals
import requests
import logging
logger = logging.getLogger(__name__) # Added logger instance
from retrying import retry
from datetime import datetime, timedelta
from pytz import timezone
from .stable_deals import validate_asin
import json
# Removed unused import: from keepa import Keepa

# Fetch Product for Retry - starts
# We removed this whole chunk - I'm leaving it here commented out to remind us that we don't want it. Amazon - Current is unique because it relies on stats.current[1], which requires a direct Keepa API call
#@retry(stop_max_attempt_number=3, wait_fixed=2000)
#def fetch_product_for_retry(asin):
#    with open('config.json') as f:
#        config = json.load(f)
#    api = Keepa(config['api_key'])
#    product = api.query(asin, product_code_is_asin=True, stats=90, domain='US', history=True, offers=20)
#    if not product or not product[0]:
#        logging.error(f"fetch_product_for_retry failed: no product data for ASIN {asin}")
#        return {}
#    stats = product[0].get('stats', {})
#    stats_current = stats.get('current', [-1] * 20)
#    offers = product.get('offers', []) if product.get('offers') is not None else []
#    logging.debug(f"fetch_product_for_retry response for ASIN {asin}: stats_keys={list(stats.keys())}, stats_current={stats_current}, stats_raw={stats}, offers_count={len(offers)}")
#    return product[0]
# Fetch Product for Retry - ends

# Constants
KEEPA_EPOCH_DATETIME = datetime(2000, 1, 1) # Keepa epoch is Jan 1, 2000
KEEPA_EPOCH_LEGACY = datetime(2011, 1, 1) # Older epoch used in some functions
TORONTO_TZ = timezone('America/Toronto')

# Helper function to convert Keepa Time Minutes (KTM) to a formatted string
# KTM is minutes since January 1, 2000, 00:00:00 UTC
def keepa_minutes_to_datetime_str(keepa_minutes, date_format='%Y-%m-%d'):
    """Converts Keepa time minutes to a datetime string."""
    if keepa_minutes is None or not isinstance(keepa_minutes, int) or keepa_minutes <= 0:
        return '-'
    try:
        # Keepa time is minutes past January 1, 2000 UTC
        dt_utc = KEEPA_EPOCH_DATETIME + timedelta(minutes=keepa_minutes)
        # Convert to Toronto time as per other date fields in this file
        dt_toronto = dt_utc.replace(tzinfo=timezone('UTC')).astimezone(TORONTO_TZ)
        return dt_toronto.strftime(date_format)
    except Exception as e:
        logger.error(f"Error converting Keepa minutes ({keepa_minutes}) to datetime: {e}")
        return '-'

# Shared globals
API_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/90.0.4430.212'}

# Global stuff starts
def get_stat_value(stats, key, index, divisor=1, is_price=False):
    try:
        value = stats.get(key, [])
        logger.debug(f"get_stat_value: key={key}, index={index}, stats[{key}]={value}")
        if not value or len(value) <= index:
            logger.warning(f"get_stat_value: No data for key={key}, index={index}, returning '-'")
            return '-'
        value = value[index]
        logger.debug(f"get_stat_value: key={key}, index={index}, value={value}")
        if isinstance(value, list):
            value = value[1] if len(value) > 1 else -1
        if value == -1 or value is None:
            return '-'
        if is_price:
            return f"${value / divisor:.2f}"
        return f"{int(value / divisor):,}"
    except (IndexError, TypeError, AttributeError) as e:
        logger.error(f"get_stat_value failed: stats={stats}, key={key}, index={index}, error={str(e)}")
        return '-'
# Global stuff ends

# Percent Down 90 starts
def percent_down_90(product):
    logger.debug(f"percent_down_90 input: {product.get('asin', '-')}")
    stats_90 = product.get('stats', {})
    avg = stats_90.get('avg90', [-1] * 20)[2]  # Used price
    curr = stats_90.get('current', [-1] * 20)[2]  # Used price
    if avg <= 0 or curr < 0 or avg is None or curr is None:
        logger.error(f"No valid avg90 or current for ASIN {product.get('asin', '-')}: avg={avg}, curr={curr}")
        return {'Percent Down 90': '-'}
    try:
        value = ((avg - curr) / avg * 100)
        percent = f"{value:.0f}%"
        logger.debug(f"percent_down_90 result: {percent}")
        return {'Percent Down 90': percent}
    except Exception as e:
        logger.error(f"percent_down_90 failed: {str(e)}")
        return {'Percent Down 90': '-'}
# Percent Down 90 ends

# Avg. Price 90,
# Percent Down 365,
# Avg. Price 365,

# Price Now starts - This produces correct data for Sales Rank - Current -- NOT Price Now
#def price_now(product):
#    stats = product.get('stats', {})
#    result = {'Price Now': get_stat_value(stats, 'current', 3, divisor=100, is_price=True)}
#    logging.debug(f"price_now result for ASIN {product.get('asin', 'unknown')}: {result}")
#    return result
# Price Now ends

# Price Now Source,
# Deal found (stable_deals) 

# AMZ link starts
def amz_link(product):
    asin = product.get('asin', '-')
    result = {'AMZ link': f"https://www.amazon.com/dp/{asin}?psc=1&aod=1" if asin != '-' else '-'}
    logger.debug(f"amz_link result for ASIN {asin}: {result}")
    return result
# AMZ link ends

# Keepa Link starts
def keepa_link(product):
    asin = product.get('asin', '-')
    result = {'Keepa Link': f"https://keepa.com/#!product/1-{asin}" if asin != '-' else '-'}
    logger.debug(f"keepa_link result for ASIN {asin}: {result}")
    return result
# Keepa Link ends

# Title starts
def get_title(product):
    title = product.get('title', '-')
    asin = product.get('asin', 'unknown')
    if title == '-':
        logger.warning(f"get_title: No title found for ASIN {asin}")
    logger.debug(f"get_title result for ASIN {asin}: {title[:50]}")
    return {'Title': title}
# Title ends

# last update (stable_deals) 
# last price change (stable_deals)
# Sales Rank - Reference
# Reviews - Rating
# Reviews - Review Count
# FBA Pick&Pack Fee
# Referral Fee %

# Tracking since starts
@retry(stop_max_attempt_number=3, wait_fixed=5000)
def tracking_since(product):
    ts = product.get('trackingSince', 0)
    logger.debug(f"Tracking since - raw ts={ts}")
    if ts <= 100000: # This threshold might be specific to the 2011 epoch interpretation
        logger.error(f"No valid trackingSince for ASIN {product.get('asin', 'unknown')}")
        return {'Tracking since': '-'}
    try:
        # This function seems to use the older 2011 epoch based on its original implementation
        dt = KEEPA_EPOCH_LEGACY + timedelta(minutes=ts)
        # Assuming ts is minutes from 2011-01-01 and needs localization if it's naive
        if dt.tzinfo is None:
            dt_toronto = TORONTO_TZ.localize(dt)
        else:
            dt_toronto = dt.astimezone(TORONTO_TZ)
        formatted = dt_toronto.strftime('%Y-%m-%d')
        logger.debug(f"Tracking since result for ASIN {product.get('asin', 'unknown')}: {formatted}")
        return {'Tracking since': formatted}
    except Exception as e:
        logger.error(f"tracking_since failed: {str(e)}")
        return {'Tracking since': '-'}
# Tracking since ends

# Categories - Root starts
def categories_root(product):
    category_tree = product.get('categoryTree', [])
    result = {'Categories - Root': category_tree[0]['name'] if category_tree else '-'}
    logger.debug(f"categories_root result for ASIN {product.get('asin', 'unknown')}: {result}")
    return result
# Categories - Root ends

# Categories - Sub starts
def categories_sub(product):
    category_tree = product.get('categoryTree', [])
    result = {'Categories - Sub': ', '.join(cat['name'] for cat in category_tree[2:]) if len(category_tree) > 2 else '-'}
    logger.debug(f"categories_sub result for ASIN {product.get('asin', 'unknown')}: {result}")
    return result
# Categories - Sub ends

# Categories - Tree starts
def categories_tree(product):
    category_tree = product.get('categoryTree', [])
    result = {'Categories - Tree': ' > '.join(cat['name'] for cat in category_tree) if category_tree else '-'}
    logger.debug(f"categories_tree result for ASIN {product.get('asin', 'unknown')}: {result}")
    return result
# Categories - Tree ends

# ASIN starts
def get_asin(product):
    asin = product.get('asin', '-')
    result = {'ASIN': asin}
    logger.debug(f"get_asin result for ASIN {asin}: {result}")
    return result
# ASIN ends

# Freq. Bought Together
# Type

# Manufacturer starts
def manufacturer(product):
    manufacturer_value = product.get('manufacturer', '-')
    if not manufacturer_value or manufacturer_value.strip() == "": # Check if None, empty, or just whitespace
        manufacturer_value = '-'
    result = {'Manufacturer': manufacturer_value}
    logger.debug(f"manufacturer result for ASIN {product.get('asin', 'unknown')}: {result}")
    return result
# Manufacturer ends

# Brand starts
def get_brand(product):
    brand_value = product.get('brand', '-')
    if not brand_value or brand_value.strip() == "": # Check if None, empty, or just whitespace
        brand_value = '-'
    result = {'Brand': brand_value}
    logger.debug(f"get_brand result for ASIN {product.get('asin', 'unknown')}: {result}")
    return result
# Brand ends

# Product Group
# Variation Attributes
# Item Type

# Author starts
def author(product):
    author_value = product.get('author', '-')
    if not author_value or author_value.strip() == "": # Check if None, empty, or just whitespace
        author_value = '-'
    result = {'Author': author_value}
    logger.debug(f"author result for ASIN {product.get('asin', 'unknown')}: {result}")
    return result
# Author ends

# Contributors

# Binding starts
def binding(product):
    binding_value = product.get('binding', '-')
    if not binding_value or binding_value.strip() == "": # Check if None, empty, or just whitespace
        binding_value = '-'
    result = {'Binding': binding_value}
    logger.debug(f"binding result for ASIN {product.get('asin', 'unknown')}: {result}")
    return result
# Binding ends

# Number of Items
# Number of Pages
# Publication Date starts
def get_publication_date(product_data):
    """
    Retrieves and formats the publication date of the product to a standard 'YYYY-MM-DD' format.
    Handles Keepa Time Minutes (KTM), YYYYMMDD integers, and various common date string formats.
    """
    asin = product_data.get('asin', 'unknown')
    logger.debug(f"ASIN {asin}: Attempting to get and standardize publication date.")

    date_value = product_data.get('publicationDate') or product_data.get('releaseDate')

    if date_value is None:
        logger.warning(f"ASIN {asin}: Neither 'publicationDate' nor 'releaseDate' found. Outputting '-'.")
        return {'Publication Date': '-'}

    dt_object = None

    # --- INTEGER PROCESSING ---
    if isinstance(date_value, int):
        date_str = str(date_value)
        try:
            if len(date_str) == 8 and 19000101 <= date_value <= 20991231:
                dt_object = datetime.strptime(date_str, '%Y%m%d')
            elif date_value > 0: # Fallback to Keepa Time Minutes
                dt_object = KEEPA_EPOCH_DATETIME + timedelta(minutes=date_value)
        except (ValueError, TypeError):
            logger.warning(f"ASIN {asin}: Could not parse integer date '{date_value}'.")
            dt_object = None

    # --- STRING PROCESSING ---
    elif isinstance(date_value, str):
        # List of possible formats to try, from most to least specific
        formats_to_try = [
            '%Y-%m-%d',         # 2023-05-15
            '%m/%d/%y',         # 4/15/22
            '%m/%d/%Y',         # 4/15/2022
            '%Y-%m',            # 2003-05
            '%b-%y',            # Jun-85
            '%Y'                # 2000
        ]
        for fmt in formats_to_try:
            try:
                dt_object = datetime.strptime(date_value, fmt)
                break # Stop after first successful parse
            except ValueError:
                continue # Try next format
    
    if dt_object:
        # Standardize the output format
        formatted_date = dt_object.strftime('%Y-%m-%d')
        logger.info(f"ASIN {asin}: Parsed date '{date_value}' to standard format '{formatted_date}'.")
        return {'Publication Date': formatted_date}

    logger.warning(f"ASIN {asin}: Date value '{date_value}' (type: {type(date_value)}) could not be parsed. Outputting '-'.")
    return {'Publication Date': '-'}
# Publication Date ends
# Languages

# Package - Quantity starts
# This one doesn't work - but we're keeping it as a reminder:
#@retry(stop_max_attempt_number=3, wait_fixed=5000)
#def package_quantity(asin, api_key):
#    if not validate_asin(asin):
#        return {'Package - Quantity': '-'}
#    url = f"https://api.keepa.com/product?key={api_key}&domain=1&asin={asin}"
#    try:
#        response = requests.get(url, headers=API_HEADERS, timeout=30)
#        logging.debug(f"package_quantity response status for ASIN {asin}: {response.status_code}")
#        if response.status_code != 200:
#            logging.error(f"package_quantity request failed for ASIN {asin}: {response.status_code}")
#            return {'Package - Quantity': '-'}
#        data = response.json()
#        products = data.get('products', [])
#        if not products:
#            logging.error(f"package_quantity no product data for ASIN {asin}")
#            return {'Package - Quantity': '-'}
#        quantity = products[0].get('packageQuantity', -1)
#        logging.debug(f"package_quantity result for ASIN {asin}: {quantity}")
#        return {'Package - Quantity': str(quantity) if quantity != -1 else '-'}
#    except Exception as e:
#        logging.error(f"package_quantity fetch failed for ASIN {asin}: {str(e)}")
#        return {'Package - Quantity': '-'}
# Package - Quantity ends

# Package Weight starts
def package_weight(product):
    weight = product.get('packageWeight', -1)
    result = {'Package Weight': f"{weight / 1000:.2f} kg" if weight != -1 else '-'}
    return result
# Package Weight ends

# Package Height starts
def package_height(product):
    height = product.get('packageHeight', -1)
    if height == -1 or height == 0:
        result = {'Package Height': "Missing"}
    else:
        result = {'Package Height': f"{height / 10:.1f} cm"}
    return result
# Package Height ends

# Package Length starts
def package_length(product):
    length = product.get('packageLength', -1)
    if length == -1 or length == 0:
        result = {'Package Length': "Missing"}
    else:
        result = {'Package Length': f"{length / 10:.1f} cm"}
    return result
# Package Length ends

# Package Width starts
def package_width(product):
    width = product.get('packageWidth', -1)
    if width == -1 or width == 0:
        result = {'Package Width': "Missing"}
    else:
        result = {'Package Width': f"{width / 10:.1f} cm"}
    return result
# Package Width ends

# Listed since starts
def listed_since(product):
    ts = product.get('listedSince', 0)
    asin = product.get('asin', 'unknown')
    logger.debug(f"Listed since - raw ts={ts} for ASIN {asin}")
    if ts <= 0: # This field likely uses the 2011 epoch as well, or is a direct timestamp
        logger.info(f"No valid listedSince (ts={ts}) for ASIN {asin}")
        return {'Listed since': '-'}
    try:
        # This function also seems to use the older 2011 epoch
        dt = KEEPA_EPOCH_LEGACY + timedelta(minutes=ts)
        if dt.tzinfo is None:
            dt_toronto = TORONTO_TZ.localize(dt)
        else:
            dt_toronto = dt.astimezone(TORONTO_TZ)
        formatted = dt_toronto.strftime('%Y-%m-%d')
        logger.debug(f"Listed since result for ASIN {asin}: {formatted}")
        return {'Listed since': formatted}
    except Exception as e:
        logger.error(f"listed_since failed for ASIN {asin}: {str(e)}")
        return {'Listed since': '-'}
# Listed since ends

# Edition
# Release Date
# Format

# Sales Rank - Current starts
def sales_rank_current(product):
    stats = product.get('stats', {})
    val = get_stat_value(stats, 'current', 3, is_price=False)

    if val != '-':
        return {'Sales Rank - Current': val}

    # Fallback to CSV (index 3 is Sales Rank)
    csv = product.get('csv')
    if csv and len(csv) > 3 and csv[3]:
        history = csv[3]
        # history is [time, val, time, val...]
        if len(history) >= 2:
             last_val = history[-1]
             if last_val != -1:
                 logger.info(f"ASIN {product.get('asin', 'unknown')}: Using CSV fallback for Sales Rank: {last_val}")
                 return {'Sales Rank - Current': f"{last_val:,}"}

    # Fallback to salesRanks
    sales_ranks = product.get('salesRanks')
    if sales_ranks and isinstance(sales_ranks, dict):
        best_val = -1
        max_ts = -1

        for cat_id, history in sales_ranks.items():
            if history and len(history) >= 2:
                # history is [time, val, time, val...]
                # Iterate in pairs from the end
                # Actually, standard keepa history is a flat list [ts, val, ts, val...]
                # So -2 is timestamp, -1 is value of the last entry.
                ts = history[-2]
                val = history[-1]
                if val != -1 and ts > max_ts:
                    max_ts = ts
                    best_val = val

        if best_val != -1:
             logger.info(f"ASIN {product.get('asin', 'unknown')}: Using salesRanks fallback for Sales Rank: {best_val}")
             return {'Sales Rank - Current': f"{best_val:,}"}

    return {'Sales Rank - Current': '-'}
# Sales Rank - Current ends

# Sales Rank - 30 days avg starts
def sales_rank_30_days_avg(product):
    stats = product.get('stats', {})
    result = {'Sales Rank - 30 days avg.': get_stat_value(stats, 'avg30', 3, is_price=False)}
    return result
# Sales Rank - 30 days avg ends

# Sales Rank - 60 days avg.

# Sales Rank - 90 days avg starts
def sales_rank_90_days_avg(product):
    stats = product.get('stats', {})
    result = {'Sales Rank - 90 days avg.': get_stat_value(stats, 'avg90', 3, is_price=False)}
    logger.debug(f"Sales Rank - 90 days avg. for ASIN {product.get('asin', 'unknown')}: {result}")
    return result
# Sales Rank - 90 days avg ends

# Sales Rank - 180 days avg starts
def sales_rank_180_days_avg(product):
    stats = product.get('stats', {})
    result = {'Sales Rank - 180 days avg.': get_stat_value(stats, 'avg180', 3, is_price=False)}
    return result
# Sales Rank - 180 days avg ends

# Sales Rank - 365 days avg starts
def sales_rank_365_days_avg(product):
    stats = product.get('stats', {})
    result = {'Sales Rank - 365 days avg.': get_stat_value(stats, 'avg365', 3, is_price=False)}
    return result
# Sales Rank - 365 days avg ends

# Sales Rank - Lowest
# Sales Rank - Lowest 365 days
# Sales Rank - Highest
# Sales Rank - Highest 365 days

# Sales Rank - Drops last 30 days starts
def sales_rank_drops_last_30_days(product):
    asin = product.get('asin', 'unknown')
    stats = product.get('stats', {})
    value = stats.get('salesRankDrops30', -1)
    logger.debug(f"Sales Rank - Drops last 30 days - raw value={value} for ASIN {asin}")
    if value < 0:
        logger.info(f"No valid Sales Rank - Drops last 30 days (value={value}) for ASIN {asin}")
        return {'Sales Rank - Drops last 30 days': '-'}
    try:
        formatted = str(value)
        logger.debug(f"Sales Rank - Drops last 30 days result for ASIN {asin}: {formatted}")
        return {'Sales Rank - Drops last 30 days': formatted}
    except Exception as e:
        logger.error(f"sales_rank_drops_last_30_days failed for ASIN {asin}: {str(e)}")
        return {'Sales Rank - Drops last 30 days': '-'}
# Sales Rank - Drops last 30 days ends

# Sales Rank - Drops last 60 days
# Sales Rank - Drops last 90 days
# Sales Rank - Drops last 180 days

# Sales Rank - Drops last 365 days starts
def sales_rank_drops_last_365_days(product):
    asin = product.get('asin', 'unknown')
    stats = product.get('stats', {})
    value = stats.get('salesRankDrops365', -1)
    logger.debug(f"Sales Rank - Drops last 365 days - raw value={value} for ASIN {asin}")
    if value < 0:
        logger.info(f"No valid Sales Rank - Drops last 365 days (value={value}) for ASIN {asin}")
        return {'Sales Rank - Drops last 365 days': '-'}
    try:
        formatted = str(value)
        logger.debug(f"Sales Rank - Drops last 365 days result for ASIN {asin}: {formatted}")
        return {'Sales Rank - Drops last 365 days': formatted}
    except Exception as e:
        logger.error(f"sales_rank_drops_last_365_days failed for ASIN {asin}: {str(e)}")
        return {'Sales Rank - Drops last 365 days': '-'}
# Sales Rank - Drops last 365 days ends

# Buy Box - Current starts - stopped working after a change to new 3rd party fbm current
# Buy Box - Current starts
def buy_box_current(product):
    asin = product.get('asin', 'unknown')
    stats = product.get('stats', {})
    buy_box_price_raw = stats.get('buyBoxPrice', -1)
    logger.debug(f"Buy Box - Current - ASIN {asin} - Attempting to use 'buyBoxPrice' field. Raw value: {buy_box_price_raw}")

    if buy_box_price_raw is not None and buy_box_price_raw > 0:
        try:
            formatted_price = f"${buy_box_price_raw / 100:.2f}"
            logger.info(f"Buy Box - Current for ASIN {asin}: Using 'buyBoxPrice', value: {formatted_price}")
            return {'Buy Box - Current': formatted_price}
        except Exception as e:
            logger.error(f"Buy Box - Current - ASIN {asin} - Error formatting 'buyBoxPrice' ({buy_box_price_raw}): {str(e)}")
            # Fall through to fallback if formatting fails, though it's unlikely for a number.
    else:
        logger.warning(f"Buy Box - Current - ASIN {asin} - 'buyBoxPrice' is missing, None, or invalid ({buy_box_price_raw}). Attempting fallback.")

    # Fallback logic
    buy_box_seller_id = product.get('buyBoxSellerId')
    # Default to condition 1 (New) if not specified. Keepa API docs suggest 0-11 for condition.
    buy_box_condition = product.get('buyBoxCondition', 1) 
    logger.debug(f"Buy Box - Current - ASIN {asin} - Fallback: buyBoxSellerId='{buy_box_seller_id}', buyBoxCondition='{buy_box_condition}'")

    if buy_box_seller_id:
        offers = product.get('offers', [])
        if not offers:
            logger.warning(f"Buy Box - Current - ASIN {asin} - Fallback: No offers array found to search for sellerId {buy_box_seller_id}.")
        for i, offer in enumerate(offers):
            offer_seller_id = offer.get('sellerId')
            offer_condition = offer.get('condition') # Assuming numeric, directly comparable
            offer_price_cents = offer.get('price', -1) # Assuming price is in cents

            logger.debug(f"Buy Box - Current - ASIN {asin} - Fallback: Checking offer {i}: sellerId='{offer_seller_id}', condition='{offer_condition}', price='{offer_price_cents}'")

            if offer_seller_id == buy_box_seller_id and offer_condition == buy_box_condition:
                if offer_price_cents > 0:
                    try:
                        formatted_price = f"${offer_price_cents / 100:.2f}"
                        logger.info(f"Buy Box - Current for ASIN {asin}: Using Fallback Logic - Found matching offer for sellerId '{buy_box_seller_id}' and condition '{buy_box_condition}'. Price: {formatted_price}")
                        return {'Buy Box - Current': formatted_price}
                    except Exception as e:
                        logger.error(f"Buy Box - Current - ASIN {asin} - Fallback: Error formatting offer price ({offer_price_cents}): {str(e)}")
                        # If formatting this specific offer fails, continue, maybe another offer matches.
                else:
                    logger.warning(f"Buy Box - Current - ASIN {asin} - Fallback: Matching offer found for sellerId '{buy_box_seller_id}' but price is invalid ({offer_price_cents}).")
        logger.warning(f"Buy Box - Current - ASIN {asin} - Fallback: No matching offer found for sellerId '{buy_box_seller_id}' and condition '{buy_box_condition}' with a positive price.")
    else:
        logger.warning(f"Buy Box - Current - ASIN {asin} - Fallback: 'buyBoxSellerId' is missing. Cannot perform fallback search.")

    logger.warning(f"Buy Box - Current - ASIN {asin} - Final decision: No valid Buy Box price found through primary or fallback methods. Returning '-'.")
    return {'Buy Box - Current': '-'}
# Buy Box - Current ends

# Buy Box - 30 days avg.
# Buy Box - 60 days avg.
# Buy Box - 90 days avg.
# Buy Box - 180 days avg.
# Buy Box - 365 days avg.
# Buy Box - Lowest
# Buy Box - Lowest 365 days
# Buy Box - Highest
# Buy Box - Highest 365 days
# Buy Box - 90 days OOS
# Buy Box - Stock

# Amazon - Current starts
# Amazon - Current is unique because it relies on stats.current[1], which requires a direct Keepa API call.
from retrying import retry
@retry(stop_max_attempt_number=3, wait_fixed=5000)
def amazon_current(product):
    asin = product.get('asin', 'unknown')
    stats = product.get('stats', {})
    # stats.current[0] is typically Amazon's price, while current[1] is New overall.
    price = stats.get('current', [None] * 23)[0] # <--- Changed to 1
    if price is None or price <= 0:
        logger.warning(f"No valid Amazon - Current price for ASIN {asin}")
        return {'Amazon - Current': '-'}
    formatted = f"${price / 100:.2f}"
    logger.debug(f"Amazon - Current result for ASIN {asin}: {formatted}")
    return {'Amazon - Current': formatted}
# Amazon - Current ends

# This one doesn't work - but we're keeping it as a reminder:
# 2025-05-20: Removed &buyBox=1 from fetch_product URL (commit 95aac66e) to fix Amazon - Current, but stats.current[10] still -1 for ASIN 150137012X despite $6.26 offer. Reverted to commit 31cb7bee setup. Pivoted to New - Current. 
# Amazon - Current starts
# def amazon_current(product):
#    asin = product.get('asin', 'unknown')
#    stats = product.get('stats', {})
#    current = stats.get('current', [-1] * 20)
#    value = current[10] if len(current) > 10 else -1
#    logging.debug(f"Amazon - Current - raw value={value}, current array={current}, stats_keys={list(stats.keys())} for ASIN {asin}")
#    if value <= 0 or value == -1:
#        logging.warning(f"No valid Amazon - Current (value={value}, current_length={len(current)}) for ASIN {asin}")
#        return {'Amazon - Current': '-'}
#    try:
#        formatted = f"${value / 100:.2f}"
#        logging.debug(f"Amazon - Current result for ASIN {asin}: {formatted}")
#        return {'Amazon - Current': formatted}
#    except Exception as e:
#        logging.error(f"amazon_current failed for ASIN {asin}: {str(e)}")
#        return {'Amazon - Current': '-'}
# Amazon - Current ends

# Amazon - 30 days avg.
# Amazon - 60 days avg.
# Amazon - 90 days avg.
# Amazon - 180 days avg.

# Amazon - 365 days avg. starts
def amazon_365_days_avg(product):
    asin = product.get('asin', 'unknown')
    stats = product.get('stats', {})
    price_str = '-'

    logger.debug(f"Amazon - 365 days avg. for ASIN {asin}: Attempting to use stats.avg365[0].")

    avg365_array = stats.get('avg365', [])
    logger.debug(f"ASIN {asin}: stats.avg365 raw: {avg365_array}")

    if avg365_array and len(avg365_array) > 0:
        price_cents = avg365_array[0]
        logger.debug(f"ASIN {asin}: Raw value at stats.avg365[0]: {price_cents}")
        if price_cents is not None and isinstance(price_cents, (int, float)) and price_cents > 0:
            try:
                price_str = f"${price_cents / 100:.2f}"
                logger.info(f"Amazon - 365 days avg. for ASIN {asin}: Using stats.avg365[0], value: {price_str}")
            except Exception as e:
                logger.error(f"Amazon - 365 days avg. for ASIN {asin}: Error formatting price {price_cents}: {e}. Setting to '-'.")
                price_str = '-'
        else:
            logger.warning(f"Amazon - 365 days avg. for ASIN {asin}: Invalid or missing price at stats.avg365[0] ({price_cents}). Setting to '-'")
            price_str = '-'
    else:
        logger.warning(f"Amazon - 365 days avg. for ASIN {asin}: stats.avg365 array is empty or missing. Setting to '-'")
        price_str = '-'
        
    return {'Amazon - 365 days avg.': price_str}
# Amazon - 365 days avg. ends

# Amazon - Lowest
# Amazon - Lowest 365 days
# Amazon - Highest
# Amazon - Highest 365 days
# Amazon - 90 days OOS
# Amazon - Stock

# New - Current starts
def new_current(product):
    asin = product.get('asin', 'unknown')
    stats = product.get('stats', {})
    current = stats.get('current', [-1] * 20)
    value = current[1] if len(current) > 1 else -1
    logger.debug(f"New - Current - raw value={value}, current array={current}, stats_keys={list(stats.keys())} for ASIN {asin}")
    if value <= 0 or value == -1:
        logger.warning(f"No valid New - Current (value={value}, current_length={len(current)}) for ASIN {asin}")
        return {'New - Current': '-'}
    try:
        formatted = f"${value / 100:.2f}"
        logger.debug(f"New - Current result for ASIN {asin}: {formatted}")
        return {'New - Current': formatted}
    except Exception as e:
        logger.error(f"new_current failed for ASIN {asin}: {str(e)}")
        return {'New - Current': '-'}
# New - Current ends

def new_3rd_party_fba_current(product):
    asin = product.get('asin', 'unknown')
    stats = product.get('stats', {})
    current_array = stats.get('current', [])
    price_str = '-'

    logger.debug(f"New, 3rd Party FBA - Current for ASIN {asin}: Attempting to use stats.current[10]. current_array length: {len(current_array)}")

    if len(current_array) > 10:
        price_cents = current_array[10]
        logger.debug(f"ASIN {asin}: Raw value at stats.current[10]: {price_cents}")
        if price_cents is not None and price_cents > 0:
            try:
                price_str = f"${price_cents / 100:.2f}"
                logger.info(f"New, 3rd Party FBA - Current for ASIN {asin}: Using stats.current[10], value: {price_str}")
            except Exception as e:
                logger.error(f"New, 3rd Party FBA - Current for ASIN {asin}: Error formatting price {price_cents}: {e}. Setting to '-'.")
                price_str = '-'
        else:
            logger.warning(f"New, 3rd Party FBA - Current for ASIN {asin}: Invalid or missing price at stats.current[10] ({price_cents}). Setting to '-'")
            price_str = '-'
    else:
        logger.warning(f"New, 3rd Party FBA - Current for ASIN {asin}: stats.current array is too short (len {len(current_array)}) to access index 10. Setting to '-'")
        price_str = '-'
        
    return {'New, 3rd Party FBA - Current': price_str}

# New, 3rd Party FBA - Current starts

    # Finds the lowest priced New offer from a 3rd Party FBA seller by parsing the 'offers' array.
# New - 30 days avg.
# New - 60 days avg.
# New - 90 days avg.
# New - 180 days avg.
# New - 365 days avg.
# New - Lowest
# New - Lowest 365 days
# New - Highest
# New - Highest 365 days
# New - 90 days OOS
# New - Stock

# New, 3rd Party FBA - Current starts

    # Finds the lowest priced New offer from a 3rd Party FBA seller by parsing the 'offers' array.
    # Price is usually in offer_csv[1] for current offers, or in 'price' for historical snapshots
    # Condition: 1 for "New". Some offers might use string "New".
    # The 'condition' field in offers seems to be numeric from provided logs.
    # Ensure seller_id exists before comparison
    # Detailed log for each offer considered (can be very verbose, use with caution or sample)
    # logging.debug(f"ASIN {asin} - Offer {i}: price_cents={offer_price_cents}, cond_code={offer_condition_code}, is_new={is_new_condition}, is_fba={is_fba_offer}, seller_id='{seller_id}', is_3p={is_third_party}")
    # logging.debug(f"ASIN {asin} - Offer {i} MATCHED New/3P/FBA criteria: price={offer_price_cents/100}")

# New, 3rd Party FBA - Current ends

# New, 3rd Party FBA - 30 days avg.
# New, 3rd Party FBA - 60 days avg.
# New, 3rd Party FBA - 90 days avg.
# New, 3rd Party FBA - 180 days avg.
# New, 3rd Party FBA - 365 days avg.

# New, 3rd Party FBA - Lowest starts
def new_3rd_party_fba_lowest(product):
    asin = product.get('asin', 'unknown')
    price_str = '-' # Default to '-'

    try:
        stats = product.get('stats', {})
        min_prices_array = stats.get('min', []) # This is an array of arrays

        logger.debug(f"ASIN {asin} - new_3rd_party_fba_lowest: stats.min raw: {min_prices_array}")

        # Index 10 corresponds to 'New, 3rd Party FBA'
        # Each element in min_prices_array is typically [timestamp, price_in_cents]
        if min_prices_array and len(min_prices_array) > 10:
            fba_lowest_pair = min_prices_array[10]
            logger.debug(f"ASIN {asin} - new_3rd_party_fba_lowest: stats.min[10] pair: {fba_lowest_pair}")
            if isinstance(fba_lowest_pair, list) and len(fba_lowest_pair) > 1:
                price_cents = fba_lowest_pair[1] # Get the price (second element)
                if price_cents is not None and isinstance(price_cents, (int, float)) and price_cents > 0:
                    price_str = f"${price_cents / 100:.2f}"
                    logger.info(f"New, 3rd Party FBA - Lowest for ASIN {asin}: Found price {price_str} from stats.min[10][1]")
                else:
                    logger.warning(f"New, 3rd Party FBA - Lowest for ASIN {asin}: Invalid price value in stats.min[10][1] ({price_cents}).")
            else:
                logger.warning(f"New, 3rd Party FBA - Lowest for ASIN {asin}: stats.min[10] is not a valid pair: {fba_lowest_pair}")
        else:
            logger.warning(f"New, 3rd Party FBA - Lowest for ASIN {asin}: stats.min array is too short or missing (length: {len(min_prices_array)}), cannot access index 10.")

    except Exception as e:
        logger.error(f"Error processing new_3rd_party_fba_lowest for ASIN {asin}: {str(e)}")
        price_str = '-' # Ensure it defaults to '-' on error

    return {'New, 3rd Party FBA - Lowest': price_str}
# New, 3rd Party FBA - Lowest ends

# New, 3rd Party FBA - Lowest 365 days
# New, 3rd Party FBA - Highest
# New, 3rd Party FBA - Highest 365 days
# New, 3rd Party FBA - 90 days OOS
# New, 3rd Party FBA - Stock

# New, 3rd Party FBM - Current starts
# 2025-05-21: Minimal filters, enhanced logging (commit 83b9e853).
# 2025-05-21: Minimal filters, detailed offer logging (commit 923d4e20).
# 2025-05-22: Enhanced logging for offers=100 (commit a03ceb87).
# 2025-05-22: Enhanced logging for Python client, offers=100 (commit 69d2801d).
# 2025-05-22: Added Python client fallback for offers (commit e1f6f52e).
# 2025-05-22: Removed Python client, use HTTP fetch_product offers=100.
def new_3rd_party_fbm_current(product):
    asin = product.get('asin', 'unknown')
    stats = product.get('stats', {})
    current_array = stats.get('current', [])
    price_str = '-'
    source = "None"

    logger.debug(f"New, 3rd Party FBM - Current for ASIN {asin}: Attempting to use stats.current[7]. current_array: {current_array}")

    if len(current_array) > 7:
        price_cents = current_array[7]
        logger.debug(f"ASIN {asin}: Raw value at stats.current[7]: {price_cents}")
        if price_cents is not None and isinstance(price_cents, (int, float)) and price_cents > 0:
            try:
                price_str = f"${price_cents / 100:.2f}"
                source = "stats.current[7]"
                logger.info(f"New, 3rd Party FBM - Current for ASIN {asin}: Using {source}, value: {price_str}")
            except Exception as e:
                logger.error(f"New, 3rd Party FBM - Current for ASIN {asin}: Error formatting price {price_cents} from stats.current[7]: {e}. Setting to '-'.")
                price_str = '-'
                source = "stats.current[7] (formatting error)"
        else:
            logger.warning(f"New, 3rd Party FBM - Current for ASIN {asin}: Invalid or non-positive price at stats.current[7] ({price_cents}). Setting to '-'")
            price_str = '-'
            source = "stats.current[7] (invalid value)"
    else:
        logger.warning(f"New, 3rd Party FBM - Current for ASIN {asin}: stats.current array is too short (len {len(current_array)}) to access index 7. Setting to '-'")
        price_str = '-'
        source = "stats.current (too short)"
    
    # As per AGENTS.md: "If this direct source is invalid... the column should output "-" rather than falling back to parsing general offers."
    # The offer parsing logic previously here has been removed to adhere to this.

    logger.info(f"New, 3rd Party FBM - Current for ASIN {asin}: Final result: {price_str}, Source: {source}")
    return {'New, 3rd Party FBM - Current': price_str}
# New, 3rd Party FBM - Current ends





# New, 3rd Party FBM starts
# !!! This one doesn't work - these should all be individual ... maybe !!!
#def new_3rd_party_fbm(product):
#    stats = product.get('stats', {})
#    asin = product.get('asin', 'unknown')
#    stock = sum(1 for o in product.get('offers', []) if o.get('condition') == 'New' and not o.get('isFBA', False) and o.get('stock', 0) > 0)
#    result = {
#        'New, 3rd Party FBM - 30 days avg.': get_stat_value(stats, 'avg30', 1, divisor=100, is_price=True),
#        'New, 3rd Party FBM - 60 days avg.': get_stat_value(stats, 'avg60', 1, divisor=100, is_price=True),
#        'New, 3rd Party FBM - 90 days avg.': get_stat_value(stats, 'avg90', 1, divisor=100, is_price=True),
#        'New, 3rd Party FBM - 180 days avg.': get_stat_value(stats, 'avg180', 1, divisor=100, is_price=True),
#        'New, 3rd Party FBM - 365 days avg.': get_stat_value(stats, 'avg365', 1, divisor=100, is_price=True),
#        'New, 3rd Party FBM - Stock': str(stock) if stock > 0 else '0'
#    }
#    logging.debug(f"new_3rd_party_fbm result for ASIN {asin}: {result}")
#    return result
# New, 3rd Party FBM ends
# !!! This one doesn't work - these should all be individual ... maybe !!!

# New, 3rd Party FBM - 30 days avg. -- ABOVE - but doesn't work ... 
# New, 3rd Party FBM - 60 days avg. -- ABOVE - but doesn't work ... 
# New, 3rd Party FBM - 90 days avg. -- ABOVE - but doesn't work ... 
# New, 3rd Party FBM - 180 days avg. -- ABOVE - but doesn't work ... 
# New, 3rd Party FBM - 365 days avg. -- ABOVE - but doesn't work ... 

# New, 3rd Party FBM - 365 days avg. starts
def new_3rd_party_fbm_365_days_avg(product_data):
    """
    Retrieves the 365-day average price for new items from 3rd party FBM sellers.
    Corresponds to stats.avg365[7].
    Prices are in cents, converted to dollars. Returns '-' if data is unavailable or invalid.
    """
    asin = product_data.get('asin', 'unknown')
    price_str = '-'
    try:
        stats = product_data.get('stats', {})
        if not stats:
            logger.warning(f"ASIN {asin}: 'stats' object missing for new_3rd_party_fbm_365_days_avg.")
            return {"New, 3rd Party FBM - 365 days avg.": "-"}

        avg365_array = stats.get('avg365', [])
        logger.debug(f"ASIN {asin} - new_3rd_party_fbm_365_days_avg: stats.avg365 raw: {avg365_array}")

        # Index 7 is for "New, 3rd Party FBM" (NEW_FBM) average price
        fbm_avg_index = 7

        if len(avg365_array) > fbm_avg_index and            avg365_array[fbm_avg_index] is not None and            isinstance(avg365_array[fbm_avg_index], (int, float)) and            avg365_array[fbm_avg_index] > 0:
            
            price_in_cents = avg365_array[fbm_avg_index]
            price_in_dollars = price_in_cents / 100.0
            formatted_price = f"${price_in_dollars:.2f}" # Format to ensure two decimal places
            logger.info(f"ASIN {asin}: New, 3rd Party FBM - 365 days avg. found: {formatted_price} from stats.avg365[{fbm_avg_index}]")
            price_str = formatted_price
        else:
            logger.info(f"ASIN {asin}: New, 3rd Party FBM - 365 days avg. not available or invalid (avg365[{fbm_avg_index}]). Value: {avg365_array[fbm_avg_index] if len(avg365_array) > fbm_avg_index else 'N/A'}. avg365 array: {avg365_array}")
            price_str = "-"

    except IndexError:
        logger.warning(f"ASIN {asin}: IndexError accessing stats.avg365[{fbm_avg_index}] for New, 3rd Party FBM - 365 days avg. avg365 array: {product_data.get('stats', {}).get('avg365', [])}")
        price_str = "-"
    except TypeError:
        logger.warning(f"ASIN {asin}: TypeError accessing stats.avg365[{fbm_avg_index}] for New, 3rd Party FBM - 365 days avg. avg365 array: {product_data.get('stats', {}).get('avg365', [])}")
        price_str = "-"
    except Exception as e:
        logger.error(f"ASIN {asin}: Unexpected error in new_3rd_party_fbm_365_days_avg: {str(e)}")
        price_str = "-"
    
    return {"New, 3rd Party FBM - 365 days avg.": price_str}
# New, 3rd Party FBM - 365 days avg. ends

# New, 3rd Party FBM - Lowest
# New, 3rd Party FBM - Lowest 365 days
# New, 3rd Party FBM - Highest
# New, 3rd Party FBM - Highest 365 days
# New, 3rd Party FBM - 90 days OOS

# New, 3rd Party FBM - Stock -- ABOVE - but doesn't work ... 





# Buy Box Used - Current starts
# 2025-05-21: Enhanced logging for stats.current[9] debugging (commit 83b9e853).
# 2025-05-21: Detailed logging for stats.current[9] (commit 923d4e20).
# 2025-05-22: Enhanced logging for stats.current[9], offers=100 (commit a03ceb87).
# 2025-05-22: Enhanced logging for Python client, stats.current[9], offers=100 (commit 69d2801d).
# 2025-05-22: Added Python client fallback for stats.current[9] (commit e1f6f52e).
# from keepa import Keepa - we removed this - I'm keeping it commented out to remind us we don't want it
def buy_box_used_current(product):
    asin = product.get('asin', 'unknown')
    stats = product.get('stats', {})
    
    logger.debug(f"Buy Box Used - Current for ASIN {asin}: Starting process. Relevant stats keys: buyBoxUsedIsFBA, buyBoxUsedPrice, buyBoxUsedShipping.")

    final_price_cents = -1
    price_source_info = "No valid price found"

    buy_box_used_is_fba = stats.get('buyBoxUsedIsFBA') # Can be True, False, or None
    item_price_cents = stats.get('buyBoxUsedPrice', -1)

    if item_price_cents is not None and item_price_cents > 0:
        if buy_box_used_is_fba is True:
            final_price_cents = item_price_cents
            price_source_info = f"FBA item price: {item_price_cents}"
        else: # FBM or buyBoxUsedIsFBA is None (treat as FBM for safety)
            shipping_price_cents = stats.get('buyBoxUsedShipping', -1)
            price_source_info = f"FBM item price: {item_price_cents}"
            if shipping_price_cents is not None and shipping_price_cents >= 0:
                final_price_cents = item_price_cents + shipping_price_cents
                price_source_info += f" + shipping: {shipping_price_cents} = {final_price_cents}"
            else: # No valid shipping, use item price only for FBM
                final_price_cents = item_price_cents
                price_source_info += " (shipping not specified or invalid)"
    
    if final_price_cents > 0:
        try:
            formatted_price = f"${final_price_cents / 100:.2f}"
            logger.info(f"Buy Box Used - Current for ASIN {asin}: Price found via primary logic. {price_source_info}. Formatted: {formatted_price}")
            return {'Buy Box Used - Current': formatted_price}
        except Exception as e:
            logger.error(f"Buy Box Used - Current for ASIN {asin}: Error formatting price ({final_price_cents}) from primary logic: {str(e)}. Will attempt fallback.")
            # Fall through to fallback if formatting fails
    else:
        logger.info(f"Buy Box Used - Current for ASIN {asin}: Primary FBA/FBM logic did not yield a valid price ({price_source_info}). Attempting fallback to stats.current[32].")

    # Fallback method: Try stats.current[32]
    current = stats.get('current', [])
    if len(current) > 32:
        value_from_current_32 = current[32]
        logger.debug(f"Buy Box Used - Current for ASIN {asin}: Fallback check of stats.current[32]. Value: {value_from_current_32}")
        if value_from_current_32 is not None and value_from_current_32 > 0:
            try:
                formatted_price = f"${value_from_current_32 / 100:.2f}"
                logger.info(f"Buy Box Used - Current for ASIN {asin}: Using fallback stats.current[32]. Raw: {value_from_current_32}, Formatted: {formatted_price}")
                return {'Buy Box Used - Current': formatted_price}
            except Exception as e:
                logger.error(f"Buy Box Used - Current for ASIN {asin}: Error formatting stats.current[32] value ({value_from_current_32}): {str(e)}")
        else:
            logger.info(f"Buy Box Used - Current for ASIN {asin}: Fallback stats.current[32] is missing, None or invalid ({value_from_current_32}).")
    else:
        logger.info(f"Buy Box Used - Current for ASIN {asin}: Fallback stats.current array is too short (len: {len(current)}) to access index 32.")

    logger.warning(f"Buy Box Used - Current for ASIN {asin}: No valid price found. Initial FBA/FBM price calc: {final_price_cents}. Fallback stats.current[32] also failed or not applicable. Returning '-'.")
    return {'Buy Box Used - Current': '-'}
# Buy Box Used - Current ends

# Buy Box Used - 30 days avg.
# Buy Box Used - 60 days avg.
# Buy Box Used - 90 days avg.
# Buy Box Used - 180 days avg.
# Buy Box Used - 365 days avg.
# Buy Box Used - Lowest
# Buy Box Used - Lowest 365 days
# Buy Box Used - Highest
# Buy Box Used - Highest 365 days
# Buy Box Used - 90 days OOS
# Buy Box Used - Stock

# Used - Current starts
def used_current(product):
    stats = product.get('stats', {})
    result = {'Used - Current': get_stat_value(stats, 'current', 2, divisor=100, is_price=True)}
    return result
# Used - Current ends

# Used - 365 days avg starts
def used_365_days_avg(product):
    stats = product.get('stats', {})
    result = {'Used - 365 days avg.': get_stat_value(stats, 'avg365', 2, divisor=100, is_price=True)}
    logger.debug(f"used_365_days_avg result for ASIN {product.get('asin', 'unknown')}: {result}")
    return result
# Used - 365 days avg ends

# Used - 30 days avg.,
# Used - 60 days avg.,
# Used - 90 days avg.,
# Used - 180 days avg.,
# Used - 365 days avg.,
# Used - Lowest,
# Used - Lowest 365 days,
# Used - Highest,
# Used - Highest 365 days,
# Used - 90 days OOS,
# Used - Stock,

# Used, like new - Current starts
# Retrieves the 'Used - Like New' price. Experimental: using stats.current[19]. Previously used stats.current[4].
# Relies on get_stat_value to return '-' if data is unavailable at this index
def used_like_new(product):
    stats = product.get('stats', {})
    asin = product.get('asin', 'unknown')
    current_price = get_stat_value(stats, 'current', 19, divisor=100, is_price=True) # <--- changed 'current', 4 to 'current', 19
    result = {'Used, like new - Current': current_price}
    logger.debug(f"used_like_new for ASIN {asin}: stats.current={stats.get('current', [])}, current_price={current_price}")
    return result
# Used, like new - Current ends

# Used, like new - 30 days avg.,
# Used, like new - 60 days avg.,
# Used, like new - 90 days avg.,
# Used, like new - 180 days avg.,
# Used, like new - 365 days avg.,
# Used, like new - Lowest,
# Used, like new - Lowest 365 days,
# Used, like new - Highest,
# Used, like new - Highest 365 days,
# Used, like new - 30 days avg.,
# Used, like new - 60 days avg.,
# Used, like new - 90 days avg.,
# Used, like new - 180 days avg.,

# Used, like new - 365 days avg. starts
def used_like_new_365_days_avg(product):
    """
    Retrieves the 365-day average 'Used - Like New' price from product stats.
    Corresponds to stats.avg365[19].
    Prices are in cents, converted to dollars. Returns '-' if data is unavailable or invalid.
    """
    asin = product.get('asin', 'unknown')
    price_str = '-'
    source_index = 19 

    try:
        stats = product.get('stats', {})
        if not stats:
            logger.warning(f"ASIN {asin}: 'stats' object missing for used_like_new_365_days_avg.")
            return {"Used, like new - 365 days avg.": "-"}

        avg365_array = stats.get('avg365', [])
        logger.debug(f"ASIN {asin} - used_like_new_365_days_avg: stats.avg365 raw: {avg365_array}")

        if len(avg365_array) > source_index:
            price_cents = avg365_array[source_index]
            logger.debug(f"ASIN {asin}: Raw value at stats.avg365[{source_index}] for Used, like new: {price_cents}")
            
            if price_cents is not None and isinstance(price_cents, (int, float)) and price_cents > 0:
                try:
                    price_str = f"${price_cents / 100:.2f}"
                    logger.info(f"Used, like new - 365 days avg. for ASIN {asin}: Using stats.avg365[{source_index}], value: {price_str}")
                except Exception as e:
                    logger.error(f"Used, like new - 365 days avg. for ASIN {asin}: Error formatting price {price_cents}: {e}. Setting to '-'.")
                    price_str = '-'
            else:
                logger.warning(f"Used, like new - 365 days avg. for ASIN {asin}: Invalid or non-positive price at stats.avg365[{source_index}] ({price_cents}). Setting to '-'")
                price_str = '-'
        else:
            logger.warning(f"Used, like new - 365 days avg. for ASIN {asin}: stats.avg365 array is too short (len {len(avg365_array)}) to access index {source_index}. Setting to '-'")
            price_str = '-'
            
    except Exception as e:
        logger.error(f"ASIN {asin}: Unexpected error in used_like_new_365_days_avg: {str(e)}")
        price_str = "-"
    
    return {"Used, like new - 365 days avg.": price_str}
# Used, like new - 365 days avg. ends

# Used, like new - Lowest,
# Used, like new - Lowest 365 days,
# Used, like new - Highest,
# Used, like new - Highest 365 days,
# Used, like new - 90 days OOS,
# Used, like new - Stock,

# Used, very good - Current starts
# Retrieves the 'Used - Very Good' price. Experimental: using stats.current[20]. Previously stats.current[5].
def used_very_good(product):
    stats = product.get('stats', {})
    asin = product.get('asin', 'unknown')
#    result = {
#        'Used, very good - Current': get_stat_value(stats, 'current', 5, divisor=100, is_price=True)
#    }
#    logger.debug(f"used_very_good result for ASIN {asin}: {result}")
#    return result
    price_str = get_stat_value(stats, 'current', 20, divisor=100, is_price=True)
    logger.debug(f"Used, very good - Current for ASIN {asin}: Using stats.current[20], result: {price_str}")
    return {'Used, very good - Current': price_str}
# Used, very good - Current ends

# Used, very good - 30 days avg.,
# Used, very good - 60 days avg.,
# Used, very good - 90 days avg.,
# Used, very good - 180 days avg.,
# Used, very good - 365 days avg.,
# Used, very good - Lowest,
# Used, very good - Lowest 365 days,
# Used, very good - Highest,
# Used, very good - Highest 365 days,
# Used, very good - 90 days OOS,
# Used, very good - Stock,

# Used, very good - 365 days avg. starts
def used_very_good_365_days_avg(product):
    """
    Retrieves the 365-day average 'Used - Very Good' price from product stats.
    Corresponds to stats.avg365[20].
    Prices are in cents, converted to dollars. Returns '-' if data is unavailable or invalid.
    """
    asin = product.get('asin', 'unknown')
    price_str = '-'
    source_index = 20 # Index for 'Used - Very Good' in stats.avg365

    try:
        stats = product.get('stats', {})
        if not stats:
            logger.warning(f"ASIN {asin}: 'stats' object missing for used_very_good_365_days_avg.")
            return {"Used, very good - 365 days avg.": "-"}

        avg365_array = stats.get('avg365', [])
        logger.debug(f"ASIN {asin} - used_very_good_365_days_avg: stats.avg365 raw: {avg365_array}")

        if len(avg365_array) > source_index:
            price_cents = avg365_array[source_index]
            logger.debug(f"ASIN {asin}: Raw value at stats.avg365[{source_index}] for Used, very good: {price_cents}")
            
            if price_cents is not None and isinstance(price_cents, (int, float)) and price_cents > 0:
                try:
                    price_str = f"${price_cents / 100:.2f}"
                    logger.info(f"Used, very good - 365 days avg. for ASIN {asin}: Using stats.avg365[{source_index}], value: {price_str}")
                except Exception as e:
                    logger.error(f"Used, very good - 365 days avg. for ASIN {asin}: Error formatting price {price_cents}: {e}. Setting to '-'.")
                    price_str = '-'
            else:
                logger.warning(f"Used, very good - 365 days avg. for ASIN {asin}: Invalid or non-positive price at stats.avg365[{source_index}] ({price_cents}). Setting to '-'")
                price_str = '-'
        else:
            logger.warning(f"Used, very good - 365 days avg. for ASIN {asin}: stats.avg365 array is too short (len {len(avg365_array)}) to access index {source_index}. Setting to '-'")
            price_str = '-'
            
    except Exception as e:
        logger.error(f"ASIN {asin}: Unexpected error in used_very_good_365_days_avg: {str(e)}")
        price_str = "-"
    
    return {"Used, very good - 365 days avg.": price_str}
# Used, very good - 365 days avg. ends

# Used, good - Current starts
# Retrieves the 'Used - Good' price. Experimental: using stats.current[21]. Previously stats.current[6].
def used_good(product):
    stats = product.get('stats', {})
    asin = product.get('asin', 'unknown')
#    result = {
#        'Used, good - Current': get_stat_value(stats, 'current', 6, divisor=100, is_price=True)
#    }
#    logger.debug(f"used_good result for ASIN {asin}: {result}")
#    return result
    price_str = get_stat_value(stats, 'current', 21, divisor=100, is_price=True)
    logger.debug(f"Used, good - Current for ASIN {asin}: Using stats.current[21], result: {price_str}")
    return {'Used, good - Current': price_str}
# Used, good - Current ends

# Used, good - 30 days avg.,
# Used, good - 60 days avg.,
# Used, good - 90 days avg.,
# Used, good - 180 days avg.,

# Used, good - 365 days avg. starts
def used_good_365_days_avg(product_data):
    """
    Retrieves the 365-day average 'Used - Good' price from product stats.
    Corresponds to stats.avg365[21].
    Prices are in cents, converted to dollars. Returns '-' if data is unavailable or invalid.
    """
    asin = product_data.get('asin', 'unknown')
    price_str = '-'
    source_index = 21 # Index for 'Used - Good' in stats.avg365

    try:
        stats = product_data.get('stats', {})
        if not stats:
            logger.warning(f"ASIN {asin}: 'stats' object missing for used_good_365_days_avg.")
            return {"Used, good - 365 days avg.": "-"}

        avg365_array = stats.get('avg365', [])
        logger.debug(f"ASIN {asin} - used_good_365_days_avg: stats.avg365 raw: {avg365_array}")

        if len(avg365_array) > source_index:
            price_cents = avg365_array[source_index]
            logger.debug(f"ASIN {asin}: Raw value at stats.avg365[{source_index}] for Used, good: {price_cents}")
            
            if price_cents is not None and isinstance(price_cents, (int, float)) and price_cents > 0:
                try:
                    price_str = f"${price_cents / 100:.2f}"
                    logger.info(f"Used, good - 365 days avg. for ASIN {asin}: Using stats.avg365[{source_index}], value: {price_str}")
                except Exception as e:
                    logger.error(f"Used, good - 365 days avg. for ASIN {asin}: Error formatting price {price_cents}: {e}. Setting to '-'.")
                    price_str = '-'
            else:
                logger.warning(f"Used, good - 365 days avg. for ASIN {asin}: Invalid or non-positive price at stats.avg365[{source_index}] ({price_cents}). Setting to '-'")
                price_str = '-'
        else:
            logger.warning(f"Used, good - 365 days avg. for ASIN {asin}: stats.avg365 array is too short (len {len(avg365_array)}) to access index {source_index}. Setting to '-'")
            price_str = '-'
            
    except Exception as e:
        logger.error(f"ASIN {asin}: Unexpected error in used_good_365_days_avg: {str(e)}")
        price_str = "-"
    
    return {"Used, good - 365 days avg.": price_str}
# Used, good - 365 days avg. ends

# Used, good - Lowest,
# Used, good - Lowest 365 days,
# Used, good - Highest,
# Used, good - Highest 365 days,
# Used, good - 90 days OOS,
# Used, good - Stock,

# Used, acceptable - Current starts
def used_acceptable(product):
    asin = product.get('asin', 'unknown')
    stats = product.get('stats', {})
    price = stats.get('current', [None] * 23)[22]
    if price is None or price <= 0:
        logger.warning(f"No valid Used - Acceptable price for ASIN {asin}")
        return {'Used, acceptable - Current': '-'}
    formatted = f"${price / 100:.2f}"
    logger.debug(f"Used, acceptable - Current result for ASIN {asin}: {formatted}")
    return {'Used, acceptable - Current': formatted}
# Used, acceptable - Current ends

# Used, acceptable - 30 days avg.,
# Used, acceptable - 60 days avg.,
# Used, acceptable - 90 days avg.,
# Used, acceptable - 180 days avg.,
# Used, acceptable - 365 days avg.,
# Used, acceptable - Lowest,
# Used, acceptable - Lowest 365 days,
# Used, acceptable - Highest,
# Used, acceptable - Highest 365 days,
# Used, acceptable - 90 days OOS,
# Used, acceptable - Stock,

# Used, acceptable - 365 days avg. starts
def used_acceptable_365_days_avg(product_data):
    """
    Retrieves the 365-day average 'Used - Acceptable' price from product stats.
    Corresponds to stats.avg365[22].
    Prices are in cents, converted to dollars. Returns '-' if data is unavailable or invalid.
    """
    asin = product_data.get('asin', 'unknown')
    price_str = '-'
    source_index = 22 # Index for 'Used - Acceptable' in stats.avg365

    try:
        stats = product_data.get('stats', {})
        if not stats:
            logger.warning(f"ASIN {asin}: 'stats' object missing for used_acceptable_365_days_avg.")
            return {"Used, acceptable - 365 days avg.": "-"}

        avg365_array = stats.get('avg365', [])
        logger.debug(f"ASIN {asin} - used_acceptable_365_days_avg: stats.avg365 raw: {avg365_array}")

        if len(avg365_array) > source_index:
            price_cents = avg365_array[source_index]
            logger.debug(f"ASIN {asin}: Raw value at stats.avg365[{source_index}] for Used, acceptable: {price_cents}")
            
            if price_cents is not None and isinstance(price_cents, (int, float)) and price_cents > 0:
                try:
                    price_str = f"${price_cents / 100:.2f}"
                    logger.info(f"Used, acceptable - 365 days avg. for ASIN {asin}: Using stats.avg365[{source_index}], value: {price_str}")
                except Exception as e:
                    logger.error(f"Used, acceptable - 365 days avg. for ASIN {asin}: Error formatting price {price_cents}: {e}. Setting to '-'.")
                    price_str = '-'
            else:
                logger.warning(f"Used, acceptable - 365 days avg. for ASIN {asin}: Invalid or non-positive price at stats.avg365[{source_index}] ({price_cents}). Setting to '-'")
                price_str = '-'
        else:
            logger.warning(f"Used, acceptable - 365 days avg. for ASIN {asin}: stats.avg365 array is too short (len {len(avg365_array)}) to access index {source_index}. Setting to '-'")
            price_str = '-'
            
    except Exception as e:
        logger.error(f"ASIN {asin}: Unexpected error in used_acceptable_365_days_avg: {str(e)}")
        price_str = "-"
    
    return {"Used, acceptable - 365 days avg.": price_str}
# Used, acceptable - 365 days avg. ends

# List Price - Current starts
# Retrieves List Price. Experimental: using stats.current[4]. Previously stats.current[8].
def list_price(product):
    stats = product.get('stats', {})
    asin = product.get('asin', 'unknown')
    current = stats.get('current', [-1] * 20)
    value = current[4] if len(current) > 4 else -1 # < --- changed to 4 from 8
    logger.debug(f"List Price - Current - raw value={value}, current array={current}, stats_keys={list(stats.keys())}, stats_raw={stats} for ASIN {asin}")
    if value <= 0 or value == -1:
        logger.warning(f"No valid List Price - Current (value={value}, current_length={len(current)}) for ASIN {asin}")
        return {'List Price - Current': '-'}
    try:
        formatted = f"${value / 100:.2f}"
        logger.debug(f"List Price - Current result for ASIN {asin}: {formatted}")
        return {'List Price - Current': formatted}
    except Exception as e:
        logger.error(f"list_price failed for ASIN {asin}: {str(e)}")
        return {'List Price - Current': '-'}
# List Price - Current ends

# New - 365 days avg. starts
def new_365_days_avg(product):
    """
    Retrieves the 365-day average 'New' price from product stats.
    Formats the price to two decimal places. Returns '-' if data is unavailable.
    """
    asin = product.get('asin', 'unknown')
    try:
        # The stats object contains arrays for different metrics (current, avg30, avg90, avg365, etc.)
        # Index 1 in these arrays typically corresponds to 'NEW' price.
        # Prices are usually in cents.
        avg365_prices = product.get('stats', {}).get('avg365', [])
        
        if avg365_prices and len(avg365_prices) > 1 and avg365_prices[1] is not None and avg365_prices[1] > 0:
            price_in_cents = avg365_prices[1]
            price_formatted = f"{price_in_cents / 100.0:.2f}"
        # logger.info(f"ASIN {asin}: New - 365 days avg. price found: {price_formatted}")
            return {'New - 365 days avg.': price_formatted}
        else:
        # logger.debug(f"ASIN {asin}: New - 365 days avg. price data not available or invalid. avg365_prices[1]: {avg365_prices[1] if len(avg365_prices) > 1 else 'N/A'}")
            return {'New - 365 days avg.': '-'}
    except (IndexError, TypeError, AttributeError) as e:
    # logger.warning(f"ASIN {asin}: Exception while fetching New - 365 days avg. price: {str(e)}")
        return {'New - 365 days avg.': '-'}
# New - 365 days avg. ends

# List Price - 30 days avg.,
# List Price - 60 days avg.,
# List Price - 90 days avg.,
# List Price - 180 days avg.,
# List Price - 365 days avg.,
# List Price - Lowest,
# List Price - Lowest 365 days,
# List Price - Highest,
# List Price - Highest 365 days,
# List Price - 90 days OOS,
# List Price - Stock,

# New Offer Count - Current starts
def new_offer_count_current(product):
    stats = product.get('stats', {})
    asin = product.get('asin', 'unknown')
    logger.debug(f"ASIN {asin}: Calculating New Offer Count - Current.")

    offer_count_fba = stats.get('offerCountFBA')
    offer_count_fbm = stats.get('offerCountFBM')

    logger.debug(f"ASIN {asin}: offerCountFBA = {offer_count_fba}, offerCountFBM = {offer_count_fbm}")

    if offer_count_fba is None and offer_count_fbm is None:
        logger.warning(f"ASIN {asin}: Both offerCountFBA and offerCountFBM are missing. Returning '-' for New Offer Count - Current.")
        return {'New Offer Count - Current': '-'}

    # Treat None as 0 for summation if one is present and the other is not
    val_fba = offer_count_fba if isinstance(offer_count_fba, int) and offer_count_fba >= 0 else 0
    val_fbm = offer_count_fbm if isinstance(offer_count_fbm, int) and offer_count_fbm >= 0 else 0
    
    total_new_offers = val_fba + val_fbm
    
    # If both original values were None (which is caught above), or if both are present but negative (unlikely for counts),
    # this logic correctly produces a sum. The main concern is missing keys.
    # If keys are present and counts are genuinely 0, sum is 0, which is correct.
    
    logger.info(f"ASIN {asin}: New Offer Count - Current calculated as {total_new_offers} (FBA: {val_fba}, FBM: {val_fbm}).")
    return {'New Offer Count - Current': str(total_new_offers)}
# New Offer Count - Current ends

# New Offer Count - 365 days avg. starts
def new_offer_count_365_days_avg(product):
    stats = product.get('stats', {})
    asin = product.get('asin', 'unknown')
    # Index 11 for average COUNT_NEW in stats.avg365 array, based on product.csv[11] mapping
    count = get_stat_value(stats, 'avg365', 11, is_price=False)
    logger.info(f"ASIN {asin}: New Offer Count - 365 days avg. from stats.avg365[11]: {count}")
    return {'New Offer Count - 365 days avg.': count}
# New Offer Count - 365 days avg. ends

# Used Offer Count - Current starts
def used_offer_count_current(product):
    stats = product.get('stats', {})
    asin = product.get('asin', 'unknown')
    logger.debug(f"ASIN {asin}: Calculating Used Offer Count - Current.")

    offer_count_fba_new = stats.get('offerCountFBA')
    offer_count_fbm_new = stats.get('offerCountFBM')
    total_offer_count = stats.get('totalOfferCount')

    logger.debug(f"ASIN {asin}: totalOfferCount = {total_offer_count}, offerCountFBA_new = {offer_count_fba_new}, offerCountFBM_new = {offer_count_fbm_new}")

    # If totalOfferCount is missing, we cannot reliably calculate used offers this way.
    if total_offer_count is None or not isinstance(total_offer_count, int) or total_offer_count < 0:
        logger.warning(f"ASIN {asin}: totalOfferCount is missing or invalid ({total_offer_count}). Returning '-' for Used Offer Count - Current.")
        return {'Used Offer Count - Current': '-'}

    # Treat None as 0 for new offer counts if one is present and the other is not, or if they are invalid
    val_fba_new = offer_count_fba_new if isinstance(offer_count_fba_new, int) and offer_count_fba_new >= 0 else 0
    val_fbm_new = offer_count_fbm_new if isinstance(offer_count_fbm_new, int) and offer_count_fbm_new >= 0 else 0
    
    current_new_total = val_fba_new + val_fbm_new
    
    # Ensure total_offer_count is not less than the sum of new offers
    if total_offer_count < current_new_total:
        logger.warning(f"ASIN {asin}: totalOfferCount ({total_offer_count}) is less than calculated new offers ({current_new_total}). This might indicate inconsistent data. Returning '-' for Used Offer Count - Current.")
        # Depending on strictness, could also return str(total_offer_count) if it's implied all are used, or 0.
        # For now, returning '-' as it implies an issue.
        return {'Used Offer Count - Current': '-'}
        
    calculated_used_offers = total_offer_count - current_new_total
    
    logger.info(f"ASIN {asin}: Used Offer Count - Current calculated as {calculated_used_offers} (Total: {total_offer_count}, New FBA: {val_fba_new}, New FBM: {val_fbm_new}).")
    return {'Used Offer Count - Current': str(calculated_used_offers)}
# Used Offer Count - Current ends

# Used Offer Count - 30 days avg. starts
def used_offer_count_30_days_avg(product):
    stats = product.get('stats', {})
    asin = product.get('asin', 'unknown')
    # Index 12 for average COUNT_USED in stats.avg30 array
    count = get_stat_value(stats, 'avg30', 12, is_price=False)
    logger.info(f"ASIN {asin}: Used Offer Count - 30 days avg. from stats.avg30[12]: {count}")
    return {'Used Offer Count - 30 days avg.': count}
# Used Offer Count - 30 days avg. ends

# Used Offer Count - 365 days avg. starts
def used_offer_count_365_days_avg(product):
    stats = product.get('stats', {})
    asin = product.get('asin', 'unknown')
    # Index 12 for average COUNT_USED in stats.avg365 array, based on product.csv[12] mapping
    count = get_stat_value(stats, 'avg365', 12, is_price=False)
    logger.info(f"ASIN {asin}: Used Offer Count - 365 days avg. from stats.avg365[12]: {count}")
    return {'Used Offer Count - 365 days avg.': count}
# Used Offer Count - 365 days avg. ends

# Buy Box - 365 days avg. starts
def buy_box_365_days_avg(product):
    """
    Retrieves the 365-day average Buy Box price.
    The Buy Box price usually includes shipping.
    """
    asin = product.get('asin', 'unknown')
    try:
        stats = product.get('stats', {})
        if not stats:
            # logger.warning(f"ASIN {asin}: 'stats' object missing for buy_box_365_days_avg.")
            return {'Buy Box - 365 days avg.': '-'}

        avg365 = stats.get('avg365', [])
        
        # Index 18 is BUY_BOX_SHIPPING in Keepa stats arrays based on log analysis
        buy_box_avg_index = 18

        if len(avg365) > buy_box_avg_index and avg365[buy_box_avg_index] is not None and avg365[buy_box_avg_index] > 0:
            price_in_cents = avg365[buy_box_avg_index]
            price_in_dollars = price_in_cents / 100.0
            # logger.info(f"ASIN {asin}: Buy Box - 365 days avg. found: ${price_in_dollars:.2f}")
            return {'Buy Box - 365 days avg.': f"{price_in_dollars:.2f}"}
        else:
            # logger.info(f"ASIN {asin}: Buy Box - 365 days avg. not available or invalid (avg365[{buy_box_avg_index}]). avg365 array: {avg365}")
            return {'Buy Box - 365 days avg.': '-'}

    except IndexError:
        # logger.warning(f"ASIN {asin}: IndexError accessing avg365 for Buy Box - 365 days avg. avg365 array: {stats.get('avg365', [])}")
        return {'Buy Box - 365 days avg.': '-'}
    except TypeError:
        # logger.warning(f"ASIN {asin}: TypeError accessing avg365 for Buy Box - 365 days avg. avg365 array: {stats.get('avg365', [])}")
        return {'Buy Box - 365 days avg.': '-'}
    except Exception as e:
        # logger.error(f"ASIN {asin}: Unexpected error in buy_box_365_days_avg: {str(e)}")
        return {'Buy Box - 365 days avg.': '-'}
# Buy Box - 365 days avg. ends

# New, 3rd Party FBA - 365 days avg. starts
def new_3rd_party_fba_365_days_avg(product_data):
    """
    Retrieves the average price of new 3rd party FBA offers over the last 365 days.
    Corresponds to stats.avg365[10].
    Prices are in cents, converted to dollars. Returns '-' if data is unavailable or invalid.
    """
    asin = product_data.get('asin', 'unknown')
    try:
        stats = product_data.get('stats', {})
        if not stats:
            logger.warning(f"ASIN {asin}: 'stats' object missing for new_3rd_party_fba_365_days_avg.")
            return {"New, 3rd Party FBA - 365 days avg.": "-"}

        avg365_array = stats.get('avg365', [])
        logger.debug(f"ASIN {asin} - new_3rd_party_fba_365_days_avg: stats.avg365 raw: {avg365_array}")

        # Index 10 is assumed for "New, 3rd Party FBA" average price
        fba_avg_index = 10

        if len(avg365_array) > fba_avg_index and            avg365_array[fba_avg_index] is not None and            isinstance(avg365_array[fba_avg_index], (int, float)) and            avg365_array[fba_avg_index] > 0:
            
            price_in_cents = avg365_array[fba_avg_index]
            price_in_dollars = price_in_cents / 100.0
            formatted_price = f"{price_in_dollars:.2f}" # Format to ensure two decimal places
            logger.info(f"ASIN {asin}: New, 3rd Party FBA - 365 days avg. found: ${formatted_price}")
            return {"New, 3rd Party FBA - 365 days avg.": formatted_price}
        else:
            logger.info(f"ASIN {asin}: New, 3rd Party FBA - 365 days avg. not available or invalid (avg365[{fba_avg_index}]). avg365 array: {avg365_array}")
            return {"New, 3rd Party FBA - 365 days avg.": "-"}

    except IndexError:
        logger.warning(f"ASIN {asin}: IndexError accessing avg365 for New, 3rd Party FBA - 365 days avg. avg365 array: {product_data.get('stats', {}).get('avg365', [])}")
        return {"New, 3rd Party FBA - 365 days avg.": "-"}
    except TypeError:
        logger.warning(f"ASIN {asin}: TypeError accessing avg365 for New, 3rd Party FBA - 365 days avg. avg365 array: {product_data.get('stats', {}).get('avg365', [])}")
        return {"New, 3rd Party FBA - 365 days avg.": "-"}
    except Exception as e:
        logger.error(f"ASIN {asin}: Unexpected error in new_3rd_party_fba_365_days_avg: {str(e)}")
        return {"New, 3rd Party FBA - 365 days avg.": "-"}
# New, 3rd Party FBA - 365 days avg. ends

# Buy Box Used - 365 days avg. starts
def buy_box_used_365_days_avg(product_data):
    """
    Retrieves the 365-day average "Buy Box Used" price from product stats.
    Assumes index 32 in stats.avg365 corresponds to this value.
    Prices are in cents, converted to dollars. Returns '-' if data is unavailable or invalid.
    """
    asin = product_data.get('asin', 'unknown')
    price_str = '-'
    source_index = 32 # Hypothetical index for 'Buy Box Used - 365 days avg.'

    try:
        stats = product_data.get('stats', {})
        if not stats:
            logger.warning(f"ASIN {asin}: 'stats' object missing for buy_box_used_365_days_avg.")
            return {"Buy Box Used - 365 days avg.": "-"}

        avg365_array = stats.get('avg365', [])
        logger.debug(f"ASIN {asin} - buy_box_used_365_days_avg: stats.avg365 raw: {avg365_array}")

        if len(avg365_array) > source_index:
            price_cents = avg365_array[source_index]
            logger.debug(f"ASIN {asin}: Raw value at stats.avg365[{source_index}]: {price_cents}")
            
            if price_cents is not None and isinstance(price_cents, (int, float)) and price_cents > 0:
                try:
                    price_str = f"${price_cents / 100:.2f}"
                    logger.info(f"Buy Box Used - 365 days avg. for ASIN {asin}: Using stats.avg365[{source_index}], value: {price_str}")
                except Exception as e:
                    logger.error(f"Buy Box Used - 365 days avg. for ASIN {asin}: Error formatting price {price_cents}: {e}. Setting to '-'.")
                    price_str = '-'
            else:
                logger.warning(f"Buy Box Used - 365 days avg. for ASIN {asin}: Invalid or non-positive price at stats.avg365[{source_index}] ({price_cents}). Setting to '-'")
                price_str = '-'
        else:
            logger.warning(f"Buy Box Used - 365 days avg. for ASIN {asin}: stats.avg365 array is too short (len {len(avg365_array)}) to access index {source_index}. Setting to '-'")
            price_str = '-'
            
    except Exception as e:
        logger.error(f"ASIN {asin}: Unexpected error in buy_box_used_365_days_avg: {str(e)}")
        price_str = "-"
    
    return {"Buy Box Used - 365 days avg.": price_str}
# Buy Box Used - 365 days avg. ends

# FBA Pick&Pack Fee starts
def get_fba_pick_pack_fee(product_data):
    """
    Retrieves the FBA Pick & Pack fee from product data.
    The fee is expected to be in cents and is converted to a dollar string.
    Returns '-' if the fee is not available or invalid.
    """
    asin = product_data.get('asin', 'unknown')
    fba_fees_data = product_data.get('fbaFees') # This should be a dictionary
    logger.debug(f"ASIN {asin}: Attempting to get FBA Pick&Pack Fee. Raw 'fbaFees' dict: {fba_fees_data}")

    if not isinstance(fba_fees_data, dict):
        logger.warning(f"ASIN {asin}: 'fbaFees' is not a dictionary or is missing. Value: {fba_fees_data}. Returning '-'.")
        return {'FBA Pick&Pack Fee': '-'}

    fee_cents = fba_fees_data.get('pickAndPackFee')

    if fee_cents is None or not isinstance(fee_cents, (int, float)) or fee_cents < 0: # Allow 0 as a valid fee
        logger.warning(f"ASIN {asin}: 'pickAndPackFee' is missing from fbaFees, None, or invalid ({fee_cents}). Returning '-'.")
        return {'FBA Pick&Pack Fee': '-'}
    
    try:
        # Assuming the fee is in cents, convert to dollars
        fee_dollars = fee_cents / 100.0
        formatted_fee = f"${fee_dollars:.2f}"
        logger.info(f"ASIN {asin}: FBA Pick&Pack Fee found: {formatted_fee} (from raw {fee_cents})")
        return {'FBA Pick&Pack Fee': formatted_fee}
    except Exception as e:
        logger.error(f"ASIN {asin}: Error formatting FBA Pick&Pack Fee ({fee_cents}): {str(e)}. Returning '-'.")
        return {'FBA Pick&Pack Fee': '-'}
# FBA Pick&Pack Fee ends

# Referral Fee % starts
def get_referral_fee_percent(product_data):
    """
    Retrieves the Referral Fee Percentage from product data.
    This is speculative as the exact field is not confirmed in documentation.
    It might be in product_data.referralFeePercent or product_data.fbaFees.referralFeePercent.
    Returns '-' if not found or invalid.
    """
    asin = product_data.get('asin', 'unknown')
    logger.debug(f"ASIN {asin}: Attempting to get Referral Fee Percentage.")

    referral_fee_value = None
    source = "Not found"

    # Priority 1: Direct field 'referralFeePercentage' (more precise)
    if 'referralFeePercentage' in product_data:
        referral_fee_value = product_data.get('referralFeePercentage')
        source = "product_data.referralFeePercentage"
        logger.debug(f"ASIN {asin}: Found precise referralFeePercentage directly: {referral_fee_value}")

    # Priority 2: Direct field 'referralFeePercent' (fallback, possibly integer)
    elif 'referralFeePercent' in product_data:
        referral_fee_value = product_data.get('referralFeePercent')
        source = "product_data.referralFeePercent"
        logger.debug(f"ASIN {asin}: Found potential referralFeePercent directly: {referral_fee_value}")
    
    # Priority 3 & 4: Nested under fbaFees (more precise then less precise)
    elif 'fbaFees' in product_data and isinstance(product_data['fbaFees'], dict):
        fba_fees_dict = product_data['fbaFees']
        if 'referralFeePercentage' in fba_fees_dict:
            referral_fee_value = fba_fees_dict.get('referralFeePercentage')
            source = "product_data.fbaFees.referralFeePercentage"
            logger.debug(f"ASIN {asin}: Found precise referralFeePercentage under fbaFees: {referral_fee_value}")
        elif 'referralFeePercent' in fba_fees_dict:
            referral_fee_value = fba_fees_dict.get('referralFeePercent')
            source = "product_data.fbaFees.referralFeePercent"
            logger.debug(f"ASIN {asin}: Found potential referralFeePercent under fbaFees: {referral_fee_value}")
        # Priority 5: Deeply nested percentage
        elif 'referralFee' in fba_fees_dict and isinstance(fba_fees_dict['referralFee'], dict):
             if 'percent' in fba_fees_dict['referralFee']:
                referral_fee_value = fba_fees_dict['referralFee'].get('percent')
                source = "product_data.fbaFees.referralFee.percent"
                logger.debug(f"ASIN {asin}: Found potential referralFeePercent under fbaFees.referralFee.percent: {referral_fee_value}")

    if referral_fee_value is not None and isinstance(referral_fee_value, (int, float)) and referral_fee_value >= 0:
        try:
            # Format to two decimal places
            formatted_fee = f"{float(referral_fee_value):.2f}%" # Ensure it's treated as float for formatting
            logger.info(f"ASIN {asin}: Referral Fee Percentage found ({source}): {formatted_fee} (from raw {referral_fee_value})")
            return {'Referral Fee %': formatted_fee}
        except Exception as e:
            logger.error(f"ASIN {asin}: Error formatting Referral Fee Percentage ({referral_fee_value}) from {source}: {str(e)}. Returning '-'.")
            return {'Referral Fee %': '-'}
    else:
        if referral_fee_value is None:
            logger.warning(f"ASIN {asin}: Referral Fee Percentage not found with any known keys. Returning '-'.")
        else:
            logger.warning(f"ASIN {asin}: Referral Fee Percentage found ({source}) but value is invalid ({referral_fee_value}). Returning '-'.")
        return {'Referral Fee %': '-'}
# Referral Fee % ends

# Shipping Included starts
def get_shipping_included(product_data):
    """
    Checks if shipping is included in the price for the Used - Current offer.
    Returns 'yes' or 'no'.
    """
    asin = product_data.get('asin', 'unknown')
    logger.debug(f"ASIN {asin}: Checking for shipping included in Used - Current offer.")

    # Check the offers for shipping cost
    offers = product_data.get('offers', [])
    if offers:
        for offer in offers:
            if offer.get('condition') == 'Used' and offer.get('shippingCost', -1) == 0:
                logger.info(f"ASIN {asin}: Found a Used offer with shippingCost of 0, shipping is included.")
                return {'Shipping Included': 'yes'}

    # Check the buyBoxUsedShipping field
    if product_data.get('stats', {}).get('buyBoxUsedShipping', -1) == 0:
        logger.info(f"ASIN {asin}: Found buyBoxUsedShipping to be 0, shipping is included.")
        return {'Shipping Included': 'yes'}

    logger.info(f"ASIN {asin}: No indication of free shipping found for Used - Current offer.")
    return {'Shipping Included': 'no'}
# Shipping Included ends

# Target Buy Price starts
def target_buy_price(product):
    """
    Calculates the target buy price by finding the lowest current offer price for a book
    in 'Good' or better condition (Like New, Very Good, Good).
    """
    asin = product.get('asin', 'unknown')
    logger = logging.getLogger(__name__)
    
    offers = product.get('offers')
    if not offers or not isinstance(offers, list):
        logger.warning(f"ASIN {asin}: 'offers' array is missing or not a list. Cannot calculate Target Buy Price.")
        return {'Target Buy Price': '-'}

    # Condition codes inferred from stats array order and Amazon standards:
    # 2: Used - Like New, 3: Used - Very Good, 4: Used - Good
    # We are looking for the lowest price among these conditions.
    good_or_better_conditions = {2, 3, 4}
    
    eligible_offers = []
    for offer in offers:
        # Ensure offer is a dictionary and has the required keys
        if not isinstance(offer, dict):
            continue
        
        condition = offer.get('condition')
        price = offer.get('price') # Price is in cents
        
        # Basic validation
        if condition is None or price is None:
            continue
            
        if condition in good_or_better_conditions and isinstance(price, int) and price > 0:
            eligible_offers.append(price)
            
    if not eligible_offers:
        logger.info(f"ASIN {asin}: No current offers found in 'Good' or better condition. Cannot determine Target Buy Price.")
        return {'Target Buy Price': '-'}
        
    # Find the minimum price from the eligible offers
    min_price_cents = min(eligible_offers)
    
    try:
        formatted_price = f"${min_price_cents / 100:.2f}"
        logger.info(f"ASIN {asin}: Target Buy Price calculated as {formatted_price} from {len(eligible_offers)} eligible offer(s).")
        return {'Target Buy Price': formatted_price}
    except Exception as e:
        logger.error(f"ASIN {asin}: Error formatting Target Buy Price ({min_price_cents}): {str(e)}")
        return {'Target Buy Price': '-'}
# Target Buy Price ends

# Buy Box Seller ID starts
def get_buy_box_seller_id(product):
    """
    Extracts the Buy Box Seller ID from the product data by checking the direct
    'buyBoxSellerId' field first, then falling back to the 'buyBoxSellerIdHistory'.
    """
    asin = product.get('asin', 'unknown')
    logger = logging.getLogger(__name__)

    # --- Method 1: Check for the direct 'buyBoxSellerId' key ---
    seller_id = product.get('buyBoxSellerId')
    if seller_id and isinstance(seller_id, str) and seller_id not in ['-1', '-2']:
        logger.info(f"ASIN {asin}: Found Buy Box Seller ID directly from 'buyBoxSellerId' field: {seller_id}")
        return {'Buy Box Seller ID': seller_id}
    
    logger.info(f"ASIN {asin}: Direct 'buyBoxSellerId' not found or invalid ('{seller_id}'). Checking 'buyBoxSellerIdHistory'.")

    # --- Method 2: Fallback to parsing 'buyBoxSellerIdHistory' ---
    history = product.get('buyBoxSellerIdHistory', [])
    if not history or not isinstance(history, list):
        logger.warning(f"ASIN {asin}: 'buyBoxSellerIdHistory' not found or is not a list. Cannot determine seller.")
        return {'Buy Box Seller ID': '-'}

    # The history is a flat list: [timestamp1, sellerId1, timestamp2, sellerId2, ...]
    # We iterate backwards by pairs to find the most recent valid seller ID.
    for i in range(len(history) - 1, 0, -2):
        # i is the index of the sellerId, i-1 is the timestamp
        potential_seller_id = history[i]
        if isinstance(potential_seller_id, str) and potential_seller_id not in ['-1', '-2']:
            timestamp = history[i-1]
            logger.info(f"ASIN {asin}: Found last valid Buy Box Seller ID from history: {potential_seller_id} (at timestamp {timestamp})")
            return {'Buy Box Seller ID': potential_seller_id}

    logger.warning(f"ASIN {asin}: Could not find a valid seller ID in the history. Last entry was '{history[-1] if history else 'N/A'}'.")
    return {'Buy Box Seller ID': '-'}
# Buy Box Seller ID ends

# Profit Margin % starts
def profit_margin_percent(product):
    """
    Calculates the profit margin based on Target Buy Price and Expected Peak Sell Price.
    This function depends on other functions for its inputs.
    """
    from .stable_calculations import get_expected_peak_price # Local import to avoid circular dependency issues

    logger = logging.getLogger(__name__)
    asin = product.get('asin', 'unknown')

    # Get Target Buy Price (from this file)
    buy_price_str = target_buy_price(product).get('Target Buy Price', '-')
    
    # Get Expected Peak Sell Price (from stable_calculations)
    sell_price_str = get_expected_peak_price(product).get('Expected Peak Price', '-')

    if buy_price_str == '-' or sell_price_str == '-':
        return {'Profit Margin %': '-'}

    try:
        buy_price = float(buy_price_str.replace('$', ''))
        sell_price = float(sell_price_str.replace('$', ''))

        if buy_price <= 0:
            return {'Profit Margin %': '-'}
            
        margin = ((sell_price - buy_price) / buy_price) * 100
        return {'Profit Margin %': f"{margin:.0f}%"}

    except (ValueError, TypeError) as e:
        logger.error(f"ASIN {asin}: Could not calculate profit margin. Buy: '{buy_price_str}', Sell: '{sell_price_str}'. Error: {e}")
        return {'Profit Margin %': '-'}
# Profit Margin % ends

#### END of stable_products.py ####
def amazon_180_days_avg(product):
    """
    Retrieves the 180-day average Amazon (New) price.
    Corresponds to stats.avg180[0].
    """
    asin = product.get('asin', 'unknown')
    stats = product.get('stats', {})
    price_str = '-'

    logger.debug(f"Amazon - 180 days avg. for ASIN {asin}: Attempting to use stats.avg180[0].")

    avg180_array = stats.get('avg180', [])
    if avg180_array and len(avg180_array) > 0:
        price_cents = avg180_array[0]
        if price_cents is not None and isinstance(price_cents, (int, float)) and price_cents > 0:
            try:
                price_str = f"${price_cents / 100:.2f}"
            except Exception as e:
                logger.error(f"Amazon - 180 days avg. for ASIN {asin}: Error formatting price {price_cents}: {e}")
        else:
            logger.warning(f"Amazon - 180 days avg. for ASIN {asin}: Invalid or missing price at stats.avg180[0] ({price_cents}).")
    else:
        logger.warning(f"Amazon - 180 days avg. for ASIN {asin}: stats.avg180 array is empty or missing.")

    return {'Amazon - 180 days avg.': price_str}
# Refreshed
