# stable_calculations.py
# (Last update: Version 5)

import logging
import math
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

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
    A sale is inferred when a drop in used offer count is followed by a drop
    in sales rank within a defined time window.
    """
    asin = product.get('asin', 'N/A')
    logger = logging.getLogger(__name__)
    logger.debug(f"ASIN {asin}: Starting sale event inference with search-window logic.")

    try:
        csv_data = product.get('csv', [])
        if not isinstance(csv_data, list) or len(csv_data) < 13:
            logger.debug(f"ASIN {asin}: 'csv' data is missing or too short.")
            return [], 0

        # Robustly get history arrays
        rank_history = csv_data[3] if isinstance(csv_data[3], list) and len(csv_data[3]) > 1 else None
        price_history = csv_data[2] if isinstance(csv_data[2], list) and len(csv_data[2]) > 1 else None
        offer_count_history = csv_data[12] if isinstance(csv_data[12], list) and len(csv_data[12]) > 1 else None

        if not all([rank_history, price_history, offer_count_history]):
            logger.debug(f"ASIN {asin}: One or more required history arrays are missing or empty.")
            return [], 0
        
        if any(len(h) % 2 != 0 for h in [rank_history, price_history, offer_count_history]):
            logger.warning(f"ASIN {asin}: Malformed history data, array length is not even.")
            return [], 0

        # Create DataFrames
        df_rank = pd.DataFrame(np.array(rank_history).reshape(-1, 2), columns=['timestamp', 'rank']).pipe(_convert_ktm_to_datetime)
        df_price = pd.DataFrame(np.array(price_history).reshape(-1, 2), columns=['timestamp', 'price_cents']).pipe(_convert_ktm_to_datetime)
        df_offers = pd.DataFrame(np.array(offer_count_history).reshape(-1, 2), columns=['timestamp', 'offer_count']).pipe(_convert_ktm_to_datetime)

        # --- Filter data to the last two years ---
        two_years_ago = datetime.now() - timedelta(days=730)
        df_rank = df_rank[df_rank['timestamp'] >= two_years_ago]
        df_price = df_price[df_price['timestamp'] >= two_years_ago]
        df_offers = df_offers[df_offers['timestamp'] >= two_years_ago]

        if df_rank.empty or df_offers.empty:
            logger.debug(f"ASIN {asin}: No historical rank or offer data found within the last two years.")
            return [], 0

        # --- New "Search Window" Logic ---
        
        # 1. Find all instances of offer drops
        df_offers['offer_diff'] = df_offers['offer_count'].diff()
        offer_drops = df_offers[df_offers['offer_diff'] < 0]

        if offer_drops.empty:
            logger.info(f"ASIN {asin}: No instances of offer count decreasing were found.")
            return [], 0
            
        logger.debug(f"ASIN {asin}: Found {len(offer_drops)} potential sale trigger points (offer drops).")

        # 2. For each offer drop, search for subsequent signals
        confirmed_sales = []
        search_window = timedelta(hours=72)

        # Prepare rank and buybox data
        df_rank = df_rank.sort_values('timestamp').reset_index(drop=True)
        df_rank['rank_diff'] = df_rank['rank'].diff()
        
        buybox_history = product.get('buyBoxSellerIdHistory', [])
        if buybox_history and len(buybox_history) > 1 and len(buybox_history) % 2 == 0:
            df_buybox = pd.DataFrame(np.array(buybox_history).reshape(-1, 2), columns=['timestamp', 'sellerId']).pipe(_convert_ktm_to_datetime)
            df_buybox['sellerId_diff'] = df_buybox['sellerId'].ne(df_buybox['sellerId'].shift())
        else:
            df_buybox = pd.DataFrame(columns=['timestamp', 'sellerId', 'sellerId_diff'])


        for _, drop in offer_drops.iterrows():
            start_time = drop['timestamp']
            end_time = start_time + search_window
            
            # Signal 1: Rank Drop
            rank_changes_in_window = df_rank[(df_rank['timestamp'] > start_time) & (df_rank['timestamp'] <= end_time)]
            has_rank_drop = not rank_changes_in_window.empty and (rank_changes_in_window['rank_diff'] < 0).any()

            # Signal 2: Buy Box Seller Change
            buybox_changes_in_window = df_buybox[(df_buybox['timestamp'] > start_time) & (df_buybox['timestamp'] <= end_time)]
            has_buybox_change = not buybox_changes_in_window.empty and buybox_changes_in_window['sellerId_diff'].any()

            if has_rank_drop: # A rank drop is the minimum requirement for a confirmed sale
                price_at_sale_time = pd.merge_asof(pd.DataFrame([drop]), df_price, on='timestamp', direction='nearest')['price_cents'].iloc[0]
                
                first_rank_drop_in_window = rank_changes_in_window[rank_changes_in_window['rank_diff'] < 0].iloc[0]
                rank_after = first_rank_drop_in_window['rank']
                rank_before_index = df_rank[df_rank['timestamp'] == first_rank_drop_in_window['timestamp']].index[0] - 1
                rank_before = df_rank.iloc[rank_before_index]['rank'] if rank_before_index >= 0 else -1

                confidence = 'High' if has_buybox_change else 'Medium'

                confirmed_sales.append({
                    'event_timestamp': start_time,
                    'inferred_sale_price_cents': price_at_sale_time,
                    'rank_before': rank_before,
                    'rank_after': rank_after,
                    'offer_count_before': drop['offer_count'] + 1,
                    'offer_count_after': drop['offer_count'],
                    'confidence': confidence
                })
        
        if not confirmed_sales:
            logger.info(f"ASIN {asin}: Found 0 confirmed sale events out of {len(offer_drops)} offer drops.")
            return [], len(offer_drops)

        # --- Outlier Rejection ---
        prices = [sale['inferred_sale_price_cents'] for sale in confirmed_sales]
        q1 = np.percentile(prices, 25)
        q3 = np.percentile(prices, 75)
        iqr = q3 - q1
        upper_bound = q3 + (1.5 * iqr)
        
        sane_sales = [sale for sale in confirmed_sales if sale['inferred_sale_price_cents'] <= upper_bound]
        
        outliers_found = len(confirmed_sales) - len(sane_sales)
        if outliers_found > 0:
            logger.info(f"ASIN {asin}: Rejected {outliers_found} outlier(s) from inferred sales list (e.g., prices > {upper_bound / 100:.2f}).")

        logger.info(f"ASIN {asin}: Found {len(sane_sales)} sane sale events after outlier rejection.")
        return sane_sales, len(offer_drops)

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

def analyze_seasonality(sale_events):
    """
    Analyzes inferred sale events to identify seasonal patterns and pricing.
    """
    logger = logging.getLogger(__name__)
    MIN_SALES_FOR_ANALYSIS = 3
    SEASONAL_STD_DEV_THRESHOLD = 0.35  # Heuristic for seasonality detection

    if not sale_events or len(sale_events) < MIN_SALES_FOR_ANALYSIS:
        return {}

    df = pd.DataFrame(sale_events)
    df['event_timestamp'] = pd.to_datetime(df['event_timestamp'])
    df['month'] = df['event_timestamp'].dt.month
    
    prices = df['inferred_sale_price_cents'].tolist()
    logger.debug(f"Analyzing seasonality with {len(prices)} sale prices: {prices}")


    # --- Seasonality Analysis (New Pattern-Based Logic) ---
    
    # Define seasonal patterns
    seasons = {
        "Textbook": {"months": {1, 2, 8, 9}, "peak_str": "Aug-Sep, Jan-Feb", "trough_str": "Apr-May"},
        # Future seasons like "Grilling" or "Christmas" can be added here
    }
    SEASON_SALES_THRESHOLD = 0.4 # 40% of sales must be in-season to be classified

    sales_per_month = df['month'].value_counts()
    total_sales = sales_per_month.sum()
    
    seasonality_type = "Year-Round" # Default
    peak_season_str = "-"
    trough_season_str = "-"

    # Check against defined seasonal patterns
    for season_name, season_details in seasons.items():
        in_season_sales = sales_per_month[sales_per_month.index.isin(season_details["months"])].sum()
        if total_sales > 0 and (in_season_sales / total_sales) >= SEASON_SALES_THRESHOLD:
            seasonality_type = season_name
            peak_season_str = season_details["peak_str"]
            trough_season_str = season_details["trough_str"]
            logger.info(f"ASIN classified as '{season_name}'. In-season sales: {in_season_sales}/{total_sales} ({in_season_sales/total_sales:.2%})")
            break # Stop after finding the first matching season

    # --- Peak/Trough Price Calculation (runs for all items) ---
    monthly_stats = df.groupby('month')['inferred_sale_price_cents'].agg(['median', 'count'])
    if len(monthly_stats) < 2:
         # Not enough data for price analysis, return with type only
        return {'seasonality_type': seasonality_type, 'peak_season': peak_season_str, 'expected_peak_price_cents': -1, 'trough_season': trough_season_str, 'expected_trough_price_cents': -1}

    peak_month = monthly_stats['median'].idxmax()
    trough_month = monthly_stats['median'].idxmin()
    peak_price_cents = monthly_stats.loc[peak_month]['median']
    trough_price_cents = monthly_stats.loc[trough_month]['median']

    logger.debug(f"Peak price of {peak_price_cents} calculated from month {peak_month}. Trough price of {trough_price_cents} from month {trough_month}.")


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
    analysis = analyze_seasonality(sale_events)
    
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
