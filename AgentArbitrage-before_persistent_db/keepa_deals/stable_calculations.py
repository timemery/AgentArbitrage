# stable_calculations.py
# (Last update: Version 5)

import logging
import math
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from .seasonal_config import SEASONAL_KEYWORD_MAP

# Keepa epoch is minutes from 2011-01-01
KEEPA_EPOCH = datetime(2011, 1, 1)

# Percent Down 365 starts
def percent_down_365(product):
    """
    Calculates the percentage difference between the current used price and the 
    365-day average used price. Prepends symbols for above/below average.
    """
    asin = product.get('asin', 'unknown')
    logging.debug(f"percent_down_365 input for ASIN {asin}: product data received.")

    stats = product.get('stats', {})
    if not stats:
        logging.warning(f"ASIN {asin}: 'stats' object is missing or empty. Cannot calculate Percent Down 365.")
        return {'Percent Down 365': '-'}

    current_used_price_raw = stats.get('current', [])
    avg_365_price_raw = stats.get('avg365', [])

    # Index 2 is for 'USED' price
    current_used = -1
    if len(current_used_price_raw) > 2 and current_used_price_raw[2] is not None:
        current_used = current_used_price_raw[2]
    
    avg_365 = -1
    if len(avg_365_price_raw) > 2 and avg_365_price_raw[2] is not None:
        avg_365 = avg_365_price_raw[2]

    logging.debug(f"ASIN {asin}: Raw current_used (stats.current[2]): {current_used}, Raw avg_365 (stats.avg365[2]): {avg_365}")

    if avg_365 <= 0 or current_used < 0: # current_used can be 0 if item is free, but avg_365 should be positive
        logging.warning(f"ASIN {asin}: Invalid or missing prices for Percent Down 365 calculation. current_used: {current_used}, avg_365: {avg_365}. Returning '-'")
        return {'Percent Down 365': '-'}

    try:
        # Calculate percentage difference
        # Formula: ((avg - current) / avg) * 100 gives % down from average
        # If current > avg, this will be negative, meaning it's % *up* from average.
        
        # Calculate percentage difference.
        # If current_used < avg_365 (price is down), percentage_diff will be positive.
        # If current_used > avg_365 (price is up), percentage_diff will be negative.
        # If current_used == avg_365, percentage_diff will be zero.
        percentage_diff = ((avg_365 - current_used) / avg_365) * 100
        
        # Format to zero decimal places. The f-string formatting handles the sign.
        # If percentage_diff is 0, it will be "0%".
        # If positive (price is down), e.g., "20%".
        # If negative (price is up), e.g., "-15%".
        result_str = f"{percentage_diff:.0f}%"

        logging.info(f"ASIN {asin}: Percent Down 365 calculated. Current: {current_used/100:.2f}, Avg365: {avg_365/100:.2f}, Diff: {percentage_diff:.2f}%, Result: {result_str}")
        return {'Percent Down 365': result_str}

    except ZeroDivisionError:
        logging.error(f"ASIN {asin}: ZeroDivisionError in percent_down_365 (avg_365 was {avg_365}). Returning '-'")
        return {'Percent Down 365': '-'}
    except Exception as e:
        logging.error(f"ASIN {asin}: Exception in percent_down_365: {str(e)}. current_used: {current_used}, avg_365: {avg_365}. Returning '-'")
        return {'Percent Down 365': '-'}
# Percent Down 365 ends

### END of stable_calculations.py ###

def _convert_ktm_to_datetime(df):
    """Converts a DataFrame's timestamp column from Keepa Time Minutes to datetime objects."""
    # Coerce to numeric, turning any non-numeric strings into NaN (which becomes NaT)
    numeric_timestamps = pd.to_numeric(df['timestamp'], errors='coerce')
    df['timestamp'] = pd.to_datetime(numeric_timestamps, unit='m', origin=KEEPA_EPOCH)
    return df

def infer_sale_events(product):
    """
    Analyzes historical product data to infer sale events using a search-window logic.
    A sale is inferred when a drop in used or new offer count is followed by a drop
    in sales rank within a defined time window.
    """
    asin = product.get('asin', 'N/A')
    logger = logging.getLogger(__name__)
    logger.debug(f"ASIN {asin}: Starting sale event inference with search-window logic (New & Used).")

    try:
        csv_data = product.get('csv', [])
        if not isinstance(csv_data, list) or len(csv_data) < 13:
            logger.debug(f"ASIN {asin}: 'csv' data is missing or too short.")
            return [], 0

        # --- Robustly get all required history arrays ---
        rank_history = csv_data[3] if isinstance(csv_data[3], list) and len(csv_data[3]) > 1 else None
        used_price_history = csv_data[2] if isinstance(csv_data[2], list) and len(csv_data[2]) > 1 else None
        new_price_history = csv_data[1] if isinstance(csv_data[1], list) and len(csv_data[1]) > 1 else None
        used_offer_count_history = csv_data[12] if isinstance(csv_data[12], list) and len(csv_data[12]) > 1 else None
        new_offer_count_history = csv_data[11] if len(csv_data) > 11 and isinstance(csv_data[11], list) and len(csv_data[11]) > 1 else None

        if not rank_history or not (used_offer_count_history or new_offer_count_history):
            logger.debug(f"ASIN {asin}: Rank history or both offer count histories are missing.")
            return [], 0

        # --- Create DataFrames ---
        df_rank = pd.DataFrame(np.array(rank_history).reshape(-1, 2), columns=['timestamp', 'rank']).pipe(_convert_ktm_to_datetime)
        df_used_price = pd.DataFrame(np.array(used_price_history).reshape(-1, 2), columns=['timestamp', 'price_cents']).pipe(_convert_ktm_to_datetime) if used_price_history else None
        df_new_price = pd.DataFrame(np.array(new_price_history).reshape(-1, 2), columns=['timestamp', 'price_cents']).pipe(_convert_ktm_to_datetime) if new_price_history else None

        two_years_ago = datetime.now() - timedelta(days=730)
        df_rank = df_rank[df_rank['timestamp'] >= two_years_ago]

        # --- Find all instances of offer drops (New and Used) ---
        all_offer_drops_list = []
        total_offer_drops_count = 0

        # Process Used offers if they exist
        if used_offer_count_history:
            df_used_offers = pd.DataFrame(np.array(used_offer_count_history).reshape(-1, 2), columns=['timestamp', 'offer_count']).pipe(_convert_ktm_to_datetime)
            df_used_offers = df_used_offers[df_used_offers['timestamp'] >= two_years_ago]
            df_used_offers['offer_diff'] = df_used_offers['offer_count'].diff()
            used_drops = df_used_offers[df_used_offers['offer_diff'] < 0].copy()
            if not used_drops.empty:
                used_drops['offer_type'] = 'Used'
                all_offer_drops_list.append(used_drops)
                total_offer_drops_count += len(used_drops)

        # Process New offers if they exist
        if new_offer_count_history:
            df_new_offers = pd.DataFrame(np.array(new_offer_count_history).reshape(-1, 2), columns=['timestamp', 'offer_count']).pipe(_convert_ktm_to_datetime)
            df_new_offers = df_new_offers[df_new_offers['timestamp'] >= two_years_ago]
            df_new_offers['offer_diff'] = df_new_offers['offer_count'].diff()
            new_drops = df_new_offers[df_new_offers['offer_diff'] < 0].copy()
            if not new_drops.empty:
                new_drops['offer_type'] = 'New'
                all_offer_drops_list.append(new_drops)
                total_offer_drops_count += len(new_drops)

        if not all_offer_drops_list:
            logger.info(f"ASIN {asin}: No instances of any offer count decreasing were found.")
            return [], 0

        offer_drops = pd.concat(all_offer_drops_list).sort_values('timestamp').reset_index(drop=True)
        logger.debug(f"ASIN {asin}: Found {len(offer_drops)} potential sale trigger points (New & Used drops).")

        # --- Search for subsequent signals ---
        confirmed_sales = []
        search_window = timedelta(hours=72)
        df_rank = df_rank.sort_values('timestamp').reset_index(drop=True)
        df_rank['rank_diff'] = df_rank['rank'].diff()
        
        for _, drop in offer_drops.iterrows():
            start_time = drop['timestamp']
            end_time = start_time + search_window
            
            rank_changes_in_window = df_rank[(df_rank['timestamp'] > start_time) & (df_rank['timestamp'] <= end_time)]
            has_rank_drop = not rank_changes_in_window.empty and (rank_changes_in_window['rank_diff'] < 0).any()

            # Near Miss Logging
            near_miss_window_end = end_time + timedelta(hours=72)
            near_miss_rank_changes = df_rank[(df_rank['timestamp'] > end_time) & (df_rank['timestamp'] <= near_miss_window_end)]
            has_near_miss_rank_drop = not near_miss_rank_changes.empty and (near_miss_rank_changes['rank_diff'] < 0).any()
            if not has_rank_drop and has_near_miss_rank_drop:
                first_miss_time = near_miss_rank_changes[near_miss_rank_changes['rank_diff'] < 0].iloc[0]['timestamp']
                hours_missed_by = (first_miss_time - end_time).total_seconds() / 3600
                logger.info(f"ASIN {asin}: Near Miss - A rank drop occurred {hours_missed_by:.2f} hours after the 72-hour window for an offer drop at {start_time}.")

            if has_rank_drop:
                price_df_to_use = df_new_price if drop['offer_type'] == 'New' and df_new_price is not None else df_used_price
                if price_df_to_use is None:
                    logger.warning(f"ASIN {asin}: No suitable price data for offer type {drop['offer_type']}.")
                    continue

                price_at_sale_time = pd.merge_asof(pd.DataFrame([drop]), price_df_to_use, on='timestamp', direction='nearest')['price_cents'].iloc[0]

                if price_at_sale_time <= 0:
                    logger.debug(f"ASIN {asin}: Ignoring inferred sale at {start_time} because its associated price was invalid ({price_at_sale_time}).")
                    continue
                
                confirmed_sales.append({
                    'event_timestamp': start_time,
                    'inferred_sale_price_cents': price_at_sale_time,
                })
        
        if not confirmed_sales:
            logger.info(f"ASIN {asin}: Found 0 confirmed sale events out of {total_offer_drops_count} offer drops.")
            return [], total_offer_drops_count

        # --- Symmetrical Outlier Rejection ---
        prices = [sale['inferred_sale_price_cents'] for sale in confirmed_sales]
        q1 = np.percentile(prices, 25)
        q3 = np.percentile(prices, 75)
        iqr = q3 - q1
        upper_bound = q3 + (1.5 * iqr)
        lower_bound = q1 - (1.5 * iqr)
        
        sane_sales = [sale for sale in confirmed_sales if lower_bound <= sale['inferred_sale_price_cents'] <= upper_bound]
        
        outliers_found = len(confirmed_sales) - len(sane_sales)
        if outliers_found > 0:
            logger.info(f"ASIN {asin}: Rejected {outliers_found} outlier(s) from inferred sales list using symmetrical IQR.")

        logger.info(f"ASIN {asin}: Found {len(sane_sales)} sane sale events after outlier rejection.")
        return sane_sales, total_offer_drops_count

    except Exception as e:
        logger.error(f"ASIN {asin}: Error during sale event inference: {e}", exc_info=True)
        return [], 0

def recent_inferred_sale_price(product):
    """
    Gets the most recent inferred sale price.
    """
    logger = logging.getLogger(__name__)
    sale_events, _ = infer_sale_events(product)
    if not sale_events:
        return {'Recent Inferred Sale Price': '-'}
    
    # Events are already sorted by timestamp
    most_recent_event = sale_events[-1]
    price_cents = most_recent_event.get('inferred_sale_price_cents', -1)

    if price_cents and price_cents > 0:
        return {'Recent Inferred Sale Price': f"${price_cents / 100:.2f}"}
    else:
        return {'Recent Inferred Sale Price': '-'}

def analyze_seasonality(product, sale_events):
    """
    Analyzes product category and inferred sale events to identify seasonal patterns and pricing.
    First checks for keywords in the product's category tree. If a match is found,
    it uses the predefined seasonal data. Otherwise, it falls back to analyzing sale event density.
    """
    logger = logging.getLogger(__name__)
    asin = product.get('asin', 'N/A')

    # --- Category-Aware Analysis (New) ---
    category_tree = product.get('categoryTree', [])
    category_string = ' > '.join(cat['name'] for cat in category_tree).lower() if category_tree else ''

    if category_string:
        for season_name, season_details in SEASONAL_KEYWORD_MAP.items():
            for keyword in season_details['keywords']:
                if keyword in category_string:
                    logger.info(f"ASIN {asin}: Found keyword '{keyword}' for season '{season_name}' in category tree. Applying predefined seasonality.")
                    # For category-based seasons, we don't calculate peak/trough prices from sales,
                    # as the season is predefined. We can enhance this later if needed.
                    return {
                        'seasonality_type': season_name,
                        'peak_season': season_details['peak_season'],
                        'trough_season': season_details['trough_season'],
                        'expected_peak_price_cents': -1, # Indicates price should be calculated from historical avg if needed
                        'expected_trough_price_cents': -1
                    }

    # --- Fallback to Sales-Density Analysis ---
    logger.debug(f"ASIN {asin}: No seasonal keyword match. Falling back to sales-density analysis.")
    MIN_SALES_FOR_ANALYSIS = 3
    if not sale_events or len(sale_events) < MIN_SALES_FOR_ANALYSIS:
        return {'seasonality_type': 'Year-Round', 'peak_season': '-', 'expected_peak_price_cents': -1, 'trough_season': '-', 'expected_trough_price_cents': -1}


    df = pd.DataFrame(sale_events)
    df['event_timestamp'] = pd.to_datetime(df['event_timestamp'])
    df['month'] = df['event_timestamp'].dt.month
    
    prices = df['inferred_sale_price_cents'].tolist()
    logger.debug(f"Analyzing seasonality with {len(prices)} sale prices: {prices}")
    
    seasonality_type = "Year-Round" # Default
    
    # --- Peak/Trough Price Calculation (based on sales density) ---
    monthly_stats = df.groupby('month')['inferred_sale_price_cents'].agg(['median', 'mean', 'count'])
    if len(monthly_stats) < 2:
         # Not enough data for price analysis, return with type only
        return {'seasonality_type': seasonality_type, 'peak_season': '-', 'expected_peak_price_cents': -1, 'trough_season': '-', 'expected_trough_price_cents': -1}

    # Determine if seasonal based on sales volume deviation
    if monthly_stats['count'].std() / monthly_stats['count'].mean() > 0.35: # Heuristic
        seasonality_type = "Seasonal"

    peak_month_median = monthly_stats['median'].idxmax()
    trough_month_median = monthly_stats['median'].idxmin()
    peak_price_cents_median = monthly_stats.loc[peak_month_median]['median']
    trough_price_cents_median = monthly_stats.loc[trough_month_median]['median']

    peak_month_mean = monthly_stats['mean'].idxmax()
    trough_month_mean = monthly_stats['mean'].idxmin()
    peak_price_cents_mean = monthly_stats.loc[peak_month_mean]['mean']
    trough_price_cents_mean = monthly_stats.loc[trough_month_mean]['mean']
    
    logger.info(f"ASIN {asin}: Peak Price (Median): {peak_price_cents_median/100:.2f}, (Mean): {peak_price_cents_mean/100:.2f}")
    logger.info(f"ASIN {asin}: Trough Price (Median): {trough_price_cents_median/100:.2f}, (Mean): {trough_price_cents_mean/100:.2f}")

    # Use the mean for the official value as requested.
    peak_price_cents = peak_price_cents_mean
    trough_price_cents = trough_price_cents_mean
    peak_season_str = datetime(2000, int(peak_month_mean), 1).strftime('%b')
    trough_season_str = datetime(2000, int(trough_month_mean), 1).strftime('%b')

    logger.debug(f"Peak price of {peak_price_cents} (using mean) calculated from month {peak_month_mean}. Trough price of {trough_price_cents} (using mean) from month {trough_month_mean}.")


    return {
        'seasonality_type': seasonality_type,
        'peak_season': peak_season_str,
        'expected_peak_price_cents': peak_price_cents,
        'trough_season': trough_season_str,
        'expected_trough_price_cents': trough_price_cents,
    }

# --- Memoization cache for analysis results ---
_analysis_cache = {}

def _get_analysis(product):
    """Helper to get or compute analysis, caching the result."""
    asin = product.get('asin')
    if asin and asin in _analysis_cache:
        return _analysis_cache[asin]
    
    sale_events, _ = infer_sale_events(product)
    # The product object is passed to analyze_seasonality to allow for category-based analysis
    analysis = analyze_seasonality(product, sale_events)
    
    if asin:
        _analysis_cache[asin] = analysis
    return analysis

def get_seasonality_type(product):
    """Wrapper to get the Seasonality Type."""
    analysis = _get_analysis(product)
    return {'Seasonality Type': analysis.get('seasonality_type', 'Year-Round')}

def get_peak_season(product):
    """Wrapper to get the Peak Season."""
    analysis = _get_analysis(product)
    return {'Peak Season': analysis.get('peak_season', '-')}

def get_expected_peak_price(product):
    """Wrapper to get the Expected Peak Price."""
    analysis = _get_analysis(product)
    price_cents = analysis.get('expected_peak_price_cents', -1)
    if price_cents and price_cents > 0:
        return {'Expected Peak Price': f"${price_cents / 100:.2f}"}
    return {'Expected Peak Price': '-'}

def get_trough_season(product):
    """Wrapper to get the Trough Season."""
    analysis = _get_analysis(product)
    return {'Trough Season': analysis.get('trough_season', '-')}

def get_expected_trough_price(product):
    """Wrapper to get the Expected Trough Price."""
    analysis = _get_analysis(product)
    price_cents = analysis.get('expected_trough_price_cents', -1)
    if price_cents and price_cents > 0:
        return {'Expected Trough Price': f"${price_cents / 100:.2f}"}
    return {'Expected Trough Price': '-'}

def profit_confidence(product):
    """Calculates a confidence score based on how many offer drops correlate with a rank drop."""
    sale_events, total_offer_drops = infer_sale_events(product)
    if total_offer_drops == 0:
        return {'Profit Confidence': '-'}
    
    confidence = (len(sale_events) / total_offer_drops) * 100
    return {'Profit Confidence': f"{confidence:.0f}%"}

def calculate_seller_quality_score(positive_ratings, total_ratings):
    """
    Calculates the Wilson Score Confidence Interval for a seller's rating.
    """
    if total_ratings == 0:
        return 0.0

    p_hat = positive_ratings / total_ratings
    n = total_ratings
    z = 1.96  # Z-score for 95% confidence interval

    try:
        # Wilson score lower bound calculation
        numerator = p_hat + (z**2 / (2 * n)) - z * math.sqrt((p_hat * (1 - p_hat) / n) + (z**2 / (4 * n**2)))
        denominator = 1 + (z**2 / n)
        
        score = numerator / denominator
        return score

    except Exception as e:
        logging.error(f"Error calculating Wilson score for {positive_ratings} positive ratings and {total_ratings} total ratings: {e}")
        return 0.0
