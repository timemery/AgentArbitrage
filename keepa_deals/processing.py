# This file will contain shared data processing logic to avoid circular imports.
import logging
from .field_mappings import FUNCTION_LIST
from .seller_info import get_all_seller_info
from .business_calculations import (
    calculate_total_amz_fees,
    calculate_all_in_cost,
    calculate_profit_and_margin,
    calculate_min_listing_price,
)
from .new_analytics import get_1yr_avg_sale_price, get_percent_discount, get_trend
from .seasonality_classifier import classify_seasonality, get_sells_period
from .db_utils import sanitize_col_name

logger = logging.getLogger(__name__)

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


def _process_single_deal(product_data, api_key, token_manager, xai_api_key, business_settings, headers):
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
        seller_info = get_all_seller_info(product_data, api_key=api_key, token_manager=token_manager)
        row_data.update(seller_info)
    except Exception as e:
        logger.error(f"ASIN {asin}: Failed to get seller info: {e}", exc_info=True)

    # 3. Business Calculations
    try:
        peak_price = _parse_price(row_data.get('Expected Peak Price', '0'))
        fba_fee = _parse_price(row_data.get('FBA Pick&Pack Fee', '0'))
        referral_percent = _parse_percent(row_data.get('Referral Fee %', '0'))
        best_price = _parse_price(row_data.get('Best Price', '0'))
        shipping_included_flag = str(row_data.get('Shipping Included', 'no')).lower() == 'yes'

        total_amz_fees = calculate_total_amz_fees(peak_price, fba_fee, referral_percent)
        all_in_cost = calculate_all_in_cost(best_price, total_amz_fees, business_settings, shipping_included_flag)
        profit_margin = calculate_profit_and_margin(peak_price, all_in_cost)
        min_listing = calculate_min_listing_price(all_in_cost, business_settings)

        row_data.update({
            'Total AMZ fees': total_amz_fees, 'All-in Cost': all_in_cost,
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
        detailed_season = classify_seasonality(title, categories, manufacturer, xai_api_key=xai_api_key)

        row_data['Detailed_Seasonality'] = "None" if detailed_season == "Year-round" else detailed_season
        row_data['Sells'] = get_sells_period(detailed_season)
    except Exception as e:
        logger.error(f"ASIN {asin}: Failed seasonality classification: {e}", exc_info=True)

    return row_data

def clean_and_prepare_row_for_db(row_dict, original_headers, schema_info, as_tuple=False):
    """
    Cleans and type-casts a single row of data based on the database schema.
    Returns a tuple of values by default.
    """
    cleaned_values = []
    for header in original_headers:
        sanitized_header = sanitize_col_name(header)
        col_type = schema_info.get(sanitized_header, 'TEXT')
        is_numeric_column = 'REAL' in col_type or 'INT' in col_type
        value = row_dict.get(header)

        if is_numeric_column:
            if value is None or (isinstance(value, str) and value.strip() in ['-', 'N/A', '']):
                cleaned_values.append(None)
            else:
                try:
                    cleaned_str = str(value).replace('$', '').replace(',', '').replace('%', '').strip()
                    cleaned_values.append(float(cleaned_str) if cleaned_str else None)
                except (ValueError, TypeError):
                    logger.warning(f"Could not convert '{value}' to float for '{header}'. Storing as NULL.")
                    cleaned_values.append(None)
        else:
            cleaned_values.append(str(value) if value is not None and value != '-' else None)

    if as_tuple:
        return tuple(cleaned_values)

    # This part is not used by the current implementation but is kept for potential future flexibility
    sanitized_headers = [sanitize_col_name(h) for h in original_headers]
    return dict(zip(sanitized_headers, cleaned_values))