from logging import getLogger
from .field_mappings import FUNCTION_LIST
from .seller_info import get_all_seller_info
from .business_calculations import (
    calculate_all_in_cost,
    calculate_profit_and_margin,
    calculate_min_listing_price,
)
from .new_analytics import get_1yr_avg_sale_price, get_percent_discount, get_trend
from .seasonality_classifier import classify_seasonality, get_sells_period

logger = getLogger(__name__)

def _parse_price(value_str):
    if isinstance(value_str, (int, float)): return float(value_str)
    if not isinstance(value_str, str) or value_str.strip() in ['-', 'N/A', '']: return 0.0
    try: return float(value_str.strip().replace('$', '').replace(',', ''))
    except ValueError: return 0.0

def _parse_percent(value_str):
    if isinstance(value_str, (int, float)): return float(value_str)
    if not isinstance(value_str, str) or value_str.strip() in ['-', 'N/A', '']: return 0.0
    try: return float(value_str.strip().replace('%', ''))
    except ValueError: return 0.0

def _process_single_deal(product_data, seller_data_cache, xai_api_key, business_settings, headers):
    asin = product_data.get('asin')
    if not asin:
        return None

    row_data = {'ASIN': asin}

    # 1. Initial data extraction from field_mappings
    for header, func in zip(headers, FUNCTION_LIST):
        if func:
            try:
                if func.__name__ in ['last_update', 'last_price_change']:
                    result = func(product_data, logger, product_data)
                elif func.__name__ == 'deal_found':
                    result = func(product_data, logger)
                elif func.__name__ == 'get_condition':
                    result = func(product_data, logger)
                else:
                    result = func(product_data)
                row_data.update(result)
            except Exception as e:
                logger.error(f"Function {func.__name__} failed for ASIN {asin}, header '{header}': {e}", exc_info=True)

    # 2. Seller Info
    try:
        seller_info = get_all_seller_info(product_data, seller_data_cache=seller_data_cache)
        if seller_info:
            # This is the key insight from the diagnostic script.
            # The seller_info dictionary uses keys like 'Now' and 'Seller',
            # but the rest of the pipeline and the database expect keys like
            # 'Price Now' and 'Seller Name'. We remap them here.
            key_mappings = {
                'Now': 'Price Now',
                'Seller': 'Seller Name',
                'Seller ID': 'Seller ID',
                'Seller Rank': 'Seller Rank',
                'Seller_Quality_Score': 'Seller Quality Score'
            }
            remapped_seller_info = {}
            for old_key, new_key in key_mappings.items():
                if old_key in seller_info and seller_info[old_key] is not None:
                    remapped_seller_info[new_key] = seller_info[old_key]

            row_data.update(remapped_seller_info)

            # The 'Best Price' is an alias for the 'Now' price.
            if 'Price Now' in remapped_seller_info:
                row_data['Best Price'] = remapped_seller_info['Price Now']

    except Exception as e:
        logger.error(f"ASIN {asin}: Failed to get seller info: {e}", exc_info=True)

    # 3. Business Calculations
    try:
        list_at_price = _parse_price(row_data.get('List at', '0'))
        now_price = _parse_price(row_data.get('Price Now', '0')) # Corrected key
        fba_fee = _parse_price(row_data.get('FBA Pick&Pack Fee', '0'))
        referral_percent = _parse_percent(row_data.get('Referral Fee %', '0'))
        shipping_included_flag = str(row_data.get('Shipping Included', 'no')).lower() == 'yes'

        all_in_cost = calculate_all_in_cost(now_price, list_at_price, fba_fee, referral_percent, business_settings, shipping_included_flag)
        profit_margin = calculate_profit_and_margin(list_at_price, all_in_cost)
        min_listing = calculate_min_listing_price(all_in_cost, business_settings)

        row_data.update({
            'All-in Cost': all_in_cost,
            'Profit': profit_margin['profit'], 'Margin': profit_margin['margin'],
            'Min. Listing Price': min_listing
        })
    except Exception as e:
        logger.error(f"ASIN {asin}: Failed business calculations: {e}", exc_info=True)

    # 4. Analytics
    try:
        yr_avg_info = get_1yr_avg_sale_price(product_data, logger=logger)
        trend_info = get_trend(product_data, logger=logger)
        row_data.update(yr_avg_info)
        row_data.update(trend_info)

        discount_info = get_percent_discount(row_data.get('1yr. Avg.'), row_data.get('Best Price'), logger=logger)
        row_data.update(discount_info)
    except Exception as e:
        logger.error(f"ASIN {asin}: Failed analytics calculations: {e}", exc_info=True)

    # 5. Seasonality
    try:
        title = row_data.get('Title', '')
        categories = row_data.get('Categories - Sub', '')
        manufacturer = row_data.get('Manufacturer', '')

        # Extract peak and trough seasons from the pre-calculated analytics cache
        analytics_cache = product_data.get('analytics_cache', {})
        peak_season_str = analytics_cache.get('peak_season', '-')
        trough_season_str = analytics_cache.get('trough_season', '-')

        detailed_season = classify_seasonality(
            title,
            categories,
            manufacturer,
            peak_season_str,
            trough_season_str,
            xai_api_key=xai_api_key
        )

        row_data['Detailed_Seasonality'] = "None" if detailed_season == "Year-round" else detailed_season
        row_data['Sells'] = get_sells_period(detailed_season)
    except Exception as e:
        logger.error(f"ASIN {asin}: Failed seasonality classification: {e}", exc_info=True)

    return row_data

def clean_numeric_values(row_data):
    """
    Cleans and converts numeric string values in the row data to actual numbers.
    This handles values with $, %, and commas.
    """
    for key, value in row_data.items():
        if value is None or not isinstance(value, str):
            continue

        cleaned_value = value.strip().replace('$', '').replace(',', '')

        if "Rank" in key or "Count" in key:
            try:
                row_data[key] = int(cleaned_value)
            except (ValueError, TypeError):
                row_data[key] = None # Set to None if conversion fails
        elif "%" in value:
            try:
                row_data[key] = float(cleaned_value.replace('%', ''))
            except (ValueError, TypeError):
                row_data[key] = None
        elif "Price" in key or "Cost" in key or "Fee" in key or "Profit" in key or "Margin" in key:
            try:
                row_data[key] = float(cleaned_value)
            except (ValueError, TypeError):
                row_data[key] = None

    return row_data
