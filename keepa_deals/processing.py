from logging import getLogger
from .business_calculations import (
    calculate_all_in_cost,
    calculate_profit_and_margin,
    calculate_min_listing_price,
    load_settings as business_load_settings,
)
from .new_analytics import get_1yr_avg_sale_price, get_percent_discount, get_trend
from .seasonality_classifier import classify_seasonality, get_sells_period
from .seller_info import get_used_product_info, CONDITION_CODE_MAP
from .stable_calculations import analyze_sales_performance, recent_inferred_sale_price
from .field_mappings import FUNCTION_LIST


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

def _process_single_deal(product_data, seller_data_cache, xai_api_key):
    asin = product_data.get('asin')
    if not asin:
        return None

    row_data = {'ASIN': asin}

    # Simplified initial data extraction
    if product_data.get('title'):
        row_data['Title'] = product_data['title']
    if product_data.get('manufacturer'):
        row_data['Manufacturer'] = product_data.get('manufacturer')

    # 1. Get live price and seller info directly from the product data
    try:
        price_now, seller_id, is_fba, condition_code = get_used_product_info(product_data)
        if price_now is None:
            logger.info(f"ASIN {asin}: No used offer found. Halting processing.")
            return None

        row_data['Price Now'] = price_now / 100.0  # Convert cents to dollars
        row_data['Seller'] = seller_id
        row_data['FBA'] = is_fba
        row_data['Condition'] = CONDITION_CODE_MAP.get(condition_code, 'N/A')

        if seller_id and seller_data_cache and seller_id in seller_data_cache:
            seller_details = seller_data_cache[seller_id]
            row_data['Seller Rating'] = seller_details.get('rating')
            row_data['Seller Review Count'] = seller_details.get('ratingCount')
        else:
            row_data['Seller Rating'] = "N/A"
            row_data['Seller Review Count'] = "N/A"

    except Exception as e:
        logger.error(f"ASIN {asin}: Failed to get live price/seller info: {e}", exc_info=True)
        return None

    business_settings = business_load_settings()

    # 2. Business Calculations
    try:
        # These analytics need to be run first to get the 'List at' price
        sales_perf = analyze_sales_performance(product_data)
        if sales_perf is None:
            logger.warning(f"ASIN {asin}: Could not analyze sales performance. Skipping.")
            return None
        row_data.update(sales_perf)

        list_at_price = _parse_price(row_data.get('List at', '0'))
        now_price = row_data.get('Price Now', 0.0)
        fba_fee = product_data.get('fbaFees', {}).get('pickAndPackFee', 0) / 100.0

        referral_percent = product_data.get('referralFeePercentage', 15.0)

        # Determine shipping included flag from the live offer data if possible
        shipping_included_flag = False
        if 'offers' in product_data and product_data['offers']:
            # Find the offer that corresponds to our 'Price Now'
            for offer in product_data['offers']:
                offer_csv = offer.get('offerCSV', [])
                if len(offer_csv) >=2 and offer_csv[0] + (offer_csv[1] if offer_csv[1] != -1 else 0) == price_now:
                     shipping_included_flag = (offer_csv[1] == 0)
                     break

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


    # 3. Analytics
    try:
        yr_avg_info = get_1yr_avg_sale_price(product_data)
        if yr_avg_info:
            row_data.update(yr_avg_info)

        trend_info = get_trend(product_data)
        if trend_info:
            row_data.update(trend_info)

        discount_info = get_percent_discount(row_data.get('1yr. Avg.'), row_data.get('Price Now'))
        if discount_info:
            row_data.update(discount_info)

        row_data.update(recent_inferred_sale_price(product_data))
        row_data.update(recent_inferred_sales_velocity(product_data))
        row_data.update(analyze_sales_rank_trends(product_data))


    except Exception as e:
        logger.error(f"ASIN {asin}: Failed analytics calculations: {e}", exc_info=True)


    # 4. Seasonality
    try:
        title = row_data.get('Title', '')
        categories = ', '.join([cat['name'] for cat in product_data.get('categoryTree', [])])
        manufacturer = row_data.get('Manufacturer', '')

        peak_season_str = row_data.get('Peak Sales Month', '-')
        trough_season_str = row_data.get('Trough Sales Month', '-')

        detailed_season = classify_seasonality(
            title, categories, manufacturer,
            peak_season_str, trough_season_str,
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
                row_data[key] = None
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
