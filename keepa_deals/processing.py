from logging import getLogger
from .business_calculations import (
    calculate_all_in_cost,
    calculate_profit_and_margin,
    calculate_min_listing_price,
    load_settings as business_load_settings,
)
from .new_analytics import get_1yr_avg_sale_price, get_percent_discount, get_trend, analyze_sales_rank_trends, get_offer_count_trend, get_offer_count_trend_180, get_offer_count_trend_365
from .seasonality_classifier import classify_seasonality, get_sells_period
from .seller_info import get_used_product_info, CONDITION_CODE_MAP
from .stable_calculations import analyze_sales_performance, recent_inferred_sale_price, infer_sale_events, calculate_seller_quality_score, get_expected_trough_price
from .stable_products import sales_rank_drops_last_30_days, sales_rank_drops_last_180_days, amazon_current
from .field_mappings import FUNCTION_LIST
import json
import os

logger = getLogger(__name__)
HEADERS_PATH = os.path.join(os.path.dirname(__file__), 'headers.json')

# Load headers at module level to avoid I/O in loop
try:
    with open(HEADERS_PATH, 'r') as f:
        HEADERS = json.load(f)
except Exception as e:
    logger.error(f"Failed to load headers from {HEADERS_PATH}: {e}")
    HEADERS = []

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

    if product_data.get('title'):
        row_data['Title'] = product_data['title']
    if product_data.get('manufacturer'):
        row_data['Manufacturer'] = product_data.get('manufacturer')

    try:
        used_product_info = get_used_product_info(product_data)
        if not used_product_info or used_product_info[0] is None:
            logger.info(f"ASIN {asin}: No used offer found. Halting processing.")
            return None
        price_now, seller_id, is_fba, condition_code = used_product_info

        row_data['Price Now'] = price_now / 100.0
        row_data['Seller'] = seller_id # Default to ID
        row_data['Seller ID'] = seller_id # Ensure ID is saved for future checks
        row_data['FBA'] = is_fba
        row_data['Condition'] = CONDITION_CODE_MAP.get(condition_code, 'N/A')

        if seller_id and seller_data_cache and seller_id in seller_data_cache:
            seller_details = seller_data_cache[seller_id]
            row_data['Seller'] = seller_details.get('sellerName', seller_details.get('name', seller_id)) # Use sellerName if available
            row_data['Seller Rating'] = seller_details.get('rating')
            row_data['Seller Review Count'] = seller_details.get('ratingCount')

            # Calculate Seller Quality Score (Trust)
            # Prioritize 'current' fields if available, otherwise fall back to history arrays
            rating_percent = seller_details.get('currentRating')
            if rating_percent is None:
                rating_percent = seller_details.get('rating', 0)
                if isinstance(rating_percent, list) and rating_percent:
                    rating_percent = rating_percent[-1]

            rating_count = seller_details.get('currentRatingCount')
            if rating_count is None:
                rating_count = seller_details.get('ratingCount', 0)
                if isinstance(rating_count, list) and rating_count:
                    rating_count = rating_count[-1]

            if rating_percent is not None and rating_count is not None and isinstance(rating_percent, (int, float)) and isinstance(rating_count, (int, float)):
                positive_ratings = int((rating_percent / 100.0) * rating_count)
                row_data['Seller_Quality_Score'] = calculate_seller_quality_score(positive_ratings, rating_count)
            else:
                row_data['Seller_Quality_Score'] = 0.0
        else:
            row_data['Seller Rating'] = "N/A"
            row_data['Seller Review Count'] = "N/A"
            row_data['Seller_Quality_Score'] = 0.0

    except Exception as e:
        logger.error(f"ASIN {asin}: Failed to get live price/seller info: {e}", exc_info=True)
        return None

    # Extract fields using FUNCTION_LIST
    try:
        headers = HEADERS

        for i, func in enumerate(FUNCTION_LIST):
            if func:
                try:
                    res = func(product_data)
                    if isinstance(res, dict):
                        val = next(iter(res.values())) if res else None
                    else:
                        val = res
                    if i < len(headers):
                        row_data[headers[i]] = val
                except Exception as e:
                    logger.warning(f"ASIN {asin}: Error extracting {headers[i] if i < len(headers) else 'Unknown'}: {e}")
    except Exception as e:
        logger.error(f"ASIN {asin}: Error in generic field extraction: {e}", exc_info=True)

    # Exclusion: List at
    val_list = row_data.get('List at')
    if not val_list or val_list == '-' or val_list == 'N/A':
        logger.info(f"ASIN {asin}: Excluding deal because 'List at' is missing (Price validation failed or insufficient data).")
        return None

    business_settings = business_load_settings()
    sale_events, _ = infer_sale_events(product_data)

    try:
        sales_perf = analyze_sales_performance(product_data, sale_events)
        if sales_perf is None:
            logger.warning(f"ASIN {asin}: Could not analyze sales performance. Skipping.")
            return None
        row_data.update(sales_perf)

        # Ensure Expected Trough Price is formatted if not already
        if 'expected_trough_price_cents' in sales_perf and sales_perf['expected_trough_price_cents'] > 0:
             row_data['Expected Trough Price'] = f"${sales_perf['expected_trough_price_cents']/100:.2f}"
        else:
             row_data['Expected Trough Price'] = None

        list_at_price = _parse_price(row_data.get('List at', '0'))
        now_price = row_data.get('Price Now', 0.0)

        # Safety: Handle None values in fbaFees or pickAndPackFee
        fba_fees_obj = product_data.get('fbaFees') or {}
        pick_and_pack = fba_fees_obj.get('pickAndPackFee')
        if pick_and_pack is None or pick_and_pack < 0:
            # If fee is missing (e.g., no dimension data), assume a safe default for a Book/Textbook.
            # Standard FBA fee for a ~1.5lb book is approx $5.50 (550 cents).
            pick_and_pack = 550
        fba_fee = pick_and_pack / 100.0

        # Safety: Handle None value in referralFeePercentage
        referral_percent = product_data.get('referralFeePercentage')
        if referral_percent is None or referral_percent < 0:
            referral_percent = 15.0

        shipping_included_flag = False
        if 'offers' in product_data and product_data['offers']:
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

        # Exclusion: Profit must be positive
        if row_data.get('Profit') is not None and row_data.get('Profit') <= 0:
            logger.info(f"ASIN {asin}: Excluding deal because Profit is zero or negative (${row_data.get('Profit', 0):.2f}).")
            return None

        # Exclusion: Validate Critical Data (prevent re-fetch loops)
        # If Self-Healing forced a re-fetch but we still lack data, we MUST reject it.
        list_at_val = row_data.get('List at')
        if not list_at_val or str(list_at_val).strip() in ['-', 'N/A', '0', '0.0', '0.00']:
             logger.info(f"ASIN {asin}: Ingestion Rejected - Invalid 'List at' ({list_at_val}).")
             return None

        yr_avg_val = row_data.get('1yr. Avg.')
        if not yr_avg_val or str(yr_avg_val).strip() in ['-', 'N/A', '0', '0.0', '0.00']:
             logger.info(f"ASIN {asin}: Ingestion Rejected - Invalid '1yr. Avg.' ({yr_avg_val}).")
             return None

    except Exception as e:
        logger.error(f"ASIN {asin}: Failed business calculations: {e}", exc_info=True)

    try:
        yr_avg_info = get_1yr_avg_sale_price(product_data)
        if yr_avg_info:
            row_data.update(yr_avg_info)

        # Exclusion: Do not collect deals with missing 1yr. Avg.
        # This implies < 1 sale event in the last year or missing history.
        if row_data.get('1yr. Avg.') is None:
            logger.info(f"ASIN {asin}: Excluding deal because '1yr. Avg.' is missing (insufficient sales data).")
            return None

        trend_info = get_trend(product_data)
        if trend_info:
            row_data.update(trend_info)

        discount_info = get_percent_discount(row_data.get('1yr. Avg.'), row_data.get('Price Now'))
        if discount_info:
            row_data.update(discount_info)

        row_data.update(recent_inferred_sale_price(product_data))
        row_data.update(analyze_sales_rank_trends(product_data))

    except Exception as e:
        logger.error(f"ASIN {asin}: Failed analytics calculations: {e}", exc_info=True)

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

        row_data['Detailed_Seasonality'] = detailed_season # Keep "Year-round" instead of "None"
        row_data['Sells'] = get_sells_period(detailed_season)
    except Exception as e:
        logger.error(f"ASIN {asin}: Failed seasonality classification: {e}", exc_info=True)

    # New Columns: Drops, Offers, AMZ, Drops 180, Offers 180, Offers 365
    try:
        # Drops
        drops_data = sales_rank_drops_last_30_days(product_data)
        if drops_data:
            row_data.update({'Drops': drops_data.get('Sales Rank - Drops last 30 days', '-')})

        # Offers
        offers_data = get_offer_count_trend(product_data)
        if offers_data:
            row_data.update(offers_data)

        # Offers 180
        offers_data_180 = get_offer_count_trend_180(product_data)
        if offers_data_180:
             row_data.update(offers_data_180)

        # Offers 365
        offers_data_365 = get_offer_count_trend_365(product_data)
        if offers_data_365:
             row_data.update(offers_data_365)

        # AMZ
        amz_data = amazon_current(product_data)
        amz_val = amz_data.get('Amazon - Current') if amz_data else '-'
        if amz_val and amz_val != '-' and amz_val != 'N/A':
            row_data['AMZ'] = '⚠️'
        else:
            row_data['AMZ'] = ''

    except Exception as e:
        logger.error(f"ASIN {asin}: Failed new columns extraction: {e}", exc_info=True)

    return row_data

def clean_numeric_values(row_data):
    """
    Cleans and converts numeric string values in the row data to actual numbers.
    """
    for key, value in row_data.items():
        if value is None or not isinstance(value, str):
            continue
        cleaned_value = value.strip().replace('$', '').replace(',', '')
        if "Rank" in key or "Count" in key:
            try: row_data[key] = int(cleaned_value)
            except (ValueError, TypeError): row_data[key] = None
        elif "%" in value:
            try: row_data[key] = float(cleaned_value.replace('%', ''))
            except (ValueError, TypeError): row_data[key] = None
        elif any(k in key for k in ["Price", "Cost", "Fee", "Profit", "Margin"]):
            try: row_data[key] = float(cleaned_value)
            except (ValueError, TypeError): row_data[key] = None
    return row_data

def _process_lightweight_update(existing_row, product_data):
    """
    Updates an existing deal using lightweight stats data (no history).
    Preserves critical fields like 'List at', '1yr Avg', etc.
    Returns a dictionary suitable for database update, or None if update failed.
    """
    asin = product_data.get('asin')
    if not asin or not existing_row:
        return None

    # Start with existing data converted to a dict
    row_data = dict(existing_row)

    # 0. Validation: Sanity check critical fields to prevent zombie deals
    list_at_val = row_data.get('List at')
    if not list_at_val or str(list_at_val).strip() in ['-', 'N/A', '0', '0.0', '0.00']:
         logger.info(f"ASIN {asin}: Lightweight Update Rejected - Invalid 'List at' ({list_at_val}). Letting deal expire.")
         return None

    yr_avg_val = row_data.get('1yr. Avg.')
    if not yr_avg_val or str(yr_avg_val).strip() in ['-', 'N/A', '0', '0.0', '0.00']:
         logger.info(f"ASIN {asin}: Lightweight Update Rejected - Invalid '1yr. Avg.' ({yr_avg_val}). Letting deal expire.")
         return None

    # 1. Update Price Now & Seller Info
    # Reuse get_used_product_info which works with 'offers' or 'stats'
    try:
        used_product_info = get_used_product_info(product_data)
        if used_product_info and used_product_info[0] is not None:
            price_now, seller_id, is_fba, condition_code = used_product_info
            row_data['Price Now'] = price_now / 100.0

            # Seller Logic: Preserve Name if ID matches
            current_seller_id = row_data.get('Seller ID')
            if current_seller_id == seller_id:
                 # ID is unchanged, so we assume the existing 'Seller' (Name) is still valid.
                 # Do not overwrite it.
                 pass
            else:
                 # ID changed (or was missing), so we must update 'Seller'.
                 # Since lightweight update doesn't fetch names, we fallback to ID.
                 row_data['Seller'] = seller_id

            # Always update the ID reference
            row_data['Seller ID'] = seller_id

            row_data['FBA'] = is_fba
            row_data['Condition'] = CONDITION_CODE_MAP.get(condition_code, 'N/A')
        else:
             # If price missing, we proceed but log it.
             # In lightweight mode, offers=20 should catch it if it exists.
             logger.debug(f"ASIN {asin}: Lightweight update - No Used offer found.")
             pass
    except Exception as e:
        logger.error(f"ASIN {asin}: Failed to get live price (lightweight): {e}")

    # 2. Update Sales Rank & AMZ
    try:
         from .stable_products import sales_rank_current, amazon_current
         sr_data = sales_rank_current(product_data)
         if sr_data:
             row_data.update(sr_data)

         amz_data = amazon_current(product_data)
         amz_val = amz_data.get('Amazon - Current') if amz_data else '-'
         if amz_val and amz_val != '-' and amz_val != 'N/A':
             row_data['AMZ'] = '⚠️'
         else:
             row_data['AMZ'] = ''

    except Exception as e:
        logger.error(f"ASIN {asin}: Failed to update rank/AMZ (lightweight): {e}")

    # 3. Update Offers & Drops
    try:
        from .stable_products import sales_rank_drops_last_30_days
        # get_offer_count_trend, etc need to be imported or available.
        # They are imported at top of file, so we can use them.

        drops_data = sales_rank_drops_last_30_days(product_data)
        if drops_data:
             # Ensure the key matches the DB column or internal key
             if 'Sales Rank - Drops last 30 days' in drops_data:
                 row_data['Drops'] = drops_data['Sales Rank - Drops last 30 days']
             else:
                 row_data.update(drops_data)

        # Update Offers trend
        offers_data = get_offer_count_trend(product_data)
        if offers_data:
            row_data.update(offers_data)

        # Offers 180
        offers_data_180 = get_offer_count_trend_180(product_data)
        if offers_data_180:
             row_data.update(offers_data_180)

        # Offers 365
        offers_data_365 = get_offer_count_trend_365(product_data)
        if offers_data_365:
             row_data.update(offers_data_365)

    except Exception as e:
        logger.error(f"ASIN {asin}: Failed to update offers/drops (lightweight): {e}")

    # 4. Last Price Change (Lightweight Fallback)
    try:
        from .stable_deals import last_price_change
        # Pass product_data as deal_object as well, since it has been merged
        lpc_data = last_price_change(product_data, logger, product_data)
        if lpc_data:
            row_data.update(lpc_data)
    except Exception as e:
        logger.error(f"ASIN {asin}: Failed to update last price change (lightweight): {e}")

    # 5. Recalculate Profit/Margin using Preserved 'List at'
    try:
        list_at_val = row_data.get('List at')
        list_at_price = _parse_price(list_at_val) if list_at_val else 0.0
        now_price = row_data.get('Price Now', 0.0)

        # FBA Fees - try to extract from stats if available, else fallback default
        fba_fees_obj = product_data.get('fbaFees') or {}
        pick_and_pack = fba_fees_obj.get('pickAndPackFee')
        if pick_and_pack is None or pick_and_pack < 0:
            pick_and_pack = 550
        fba_fee = pick_and_pack / 100.0

        referral_percent = product_data.get('referralFeePercentage')
        if referral_percent is None or referral_percent < 0:
            referral_percent = 15.0

        business_settings = business_load_settings()

        shipping_included_flag = False
        if 'offers' in product_data and product_data['offers']:
            for offer in product_data['offers']:
                offer_csv = offer.get('offerCSV', [])
                if len(offer_csv) >=2 and offer_csv[0] + (offer_csv[1] if offer_csv[1] != -1 else 0) == now_price:
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

        # Exclusion: Profit must be positive
        if row_data.get('Profit') is not None and row_data.get('Profit') <= 0:
            logger.info(f"ASIN {asin}: Lightweight Update Rejected - Profit is zero or negative (${row_data.get('Profit', 0):.2f}). Letting deal expire.")
            return None

        # Recalculate Percent Down
        yr_avg = row_data.get('1yr. Avg.')
        if yr_avg and yr_avg != '-' and now_price > 0:
             yr_avg_val = _parse_price(yr_avg)
             if yr_avg_val > 0:
                 if now_price < yr_avg_val:
                     pct_down = ((yr_avg_val - now_price) / yr_avg_val) * 100
                     row_data['Percent Down'] = f"{pct_down:.0f}%"
                 else:
                     row_data['Percent Down'] = "0%"

    except Exception as e:
        logger.error(f"ASIN {asin}: Failed business calculations (lightweight): {e}")

    return row_data
