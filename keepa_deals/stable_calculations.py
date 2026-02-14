# stable_calculations.py
# (Last update: Version 5)

# stable_calculations.py
# (Last update: Version 5)

import logging
import math
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from .seasonal_config import SEASONAL_KEYWORD_MAP
import os
import httpx
import time
import scipy.stats as st
from .xai_token_manager import XaiTokenManager
from .xai_cache import XaiCache

# Initialize cache and token manager at the module level
xai_cache = XaiCache()
xai_token_manager = XaiTokenManager()

# Keepa epoch is minutes from 2011-01-01
KEEPA_EPOCH = datetime(2011, 1, 1)

def _query_xai_for_reasonableness(title, category, season, price_usd, api_key, binding="N/A", page_count="N/A", image_url="N/A", rank_info="N/A", trend_info="N/A", avg_3yr_usd="N/A"):
    """
    Queries the XAI API to act as a reasonableness check for a calculated price,
    now with caching and token management.
    """
    if not api_key:
        logging.warning("XAI_API_KEY not provided. Skipping reasonableness check.")
        return True

    # 1. Create a unique cache key (include new fields to differentiate contexts)
    cache_key = f"reasonableness:{title}|{category}|{season}|{price_usd:.2f}|{binding}|{rank_info}|{trend_info}|{avg_3yr_usd}"

    # 2. Check cache first
    cached_result = xai_cache.get(cache_key)
    if cached_result is not None:
        is_reasonable = cached_result.lower() == 'true'
        logging.info(f"XAI Cache HIT for reasonableness. Found '{is_reasonable}' for title '{title}'.")
        return is_reasonable

    # 3. If not in cache, check for permission to make a call
    if not xai_token_manager.request_permission():
        logging.warning(f"XAI daily limit reached. Cannot perform reasonableness check for '{title}'. Defaulting to reasonable.")
        return True

    # 4. If permission granted, proceed with the API call
    # NOTE: We explicitly explain that the "3-Year Average Price" includes off-season lows and that seasonal items
    # (especially Textbooks) can validly have peak prices 200-400% higher than the average.
    # This context is critical to prevent the AI from falsely rejecting valid peak season prices.
    prompt = f"""
    You are an expert Arbitrage Advisor.
    CONTEXT: The "3-Year Average Price" is a simple mean of all sales, including off-season lows.
    For seasonal items (especially Textbooks), the "Peak Season" price can validly be 200-400% higher than the average.

    Given the following book details, is a peak selling price of ${price_usd:.2f} reasonable during {season}?
    Respond with only "Yes" or "No".

    - **Title:** "{title}"
    - **Category:** "{category}"
    - **Identified Peak Season:** "{season}"
    - **Binding:** "{binding}"
    - **Page Count:** "{page_count}"
    - **Sales Rank Info:** "{rank_info}"
    - **3-Year Trend:** "{trend_info}"
    - **3-Year Average Price:** "${avg_3yr_usd}"
    - **Image URL:** "{image_url}"
    """
    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "model": "grok-4-fast-reasoning", "temperature": 0.1, "max_tokens": 10
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    logging.info(f"XAI Reasonableness Request for '{title}' (Cache MISS)")

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post("https://api.x.ai/v1/chat/completions", headers=headers, json=payload)
            response.raise_for_status()

            content = response.json()['choices'][0]['message']['content'].strip().lower()
            is_reasonable = "yes" in content

            logging.info(f"XAI Reasonableness Check for '{title}' at ${price_usd:.2f}: AI responded '{content}'")

            if not is_reasonable:
                logging.warning(f"XAI REJECTED: Title='{title}', Price=${price_usd:.2f}, Category='{category}', Season='{season}', Binding='{binding}', Rank='{rank_info}', Trend='{trend_info}', 3yrAvg='${avg_3yr_usd}'")

            # 5. Cache the successful result as a string
            xai_cache.set(cache_key, str(is_reasonable))
            return is_reasonable

    except (httpx.HTTPStatusError, httpx.RequestError, Exception) as e:
        logging.error(f"An unexpected error occurred during XAI reasonableness check for '{title}': {e}")
        # Default to reasonable on any API error
        return True

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

        history_window_start = datetime.now() - timedelta(days=1095) # Extended to 3 years
        df_rank = df_rank[df_rank['timestamp'] >= history_window_start]

        # --- Find all instances of offer drops (New and Used) ---
        all_offer_drops_list = []
        total_offer_drops_count = 0

        # Process Used offers if they exist
        if used_offer_count_history:
            df_used_offers = pd.DataFrame(np.array(used_offer_count_history).reshape(-1, 2), columns=['timestamp', 'offer_count']).pipe(_convert_ktm_to_datetime)
            df_used_offers = df_used_offers[df_used_offers['timestamp'] >= history_window_start]
            df_used_offers['offer_diff'] = df_used_offers['offer_count'].diff()
            used_drops = df_used_offers[df_used_offers['offer_diff'] < 0].copy()
            if not used_drops.empty:
                used_drops['offer_type'] = 'Used'
                all_offer_drops_list.append(used_drops)
                total_offer_drops_count += len(used_drops)

        # Process New offers if they exist
        if new_offer_count_history:
            df_new_offers = pd.DataFrame(np.array(new_offer_count_history).reshape(-1, 2), columns=['timestamp', 'offer_count']).pipe(_convert_ktm_to_datetime)
            df_new_offers = df_new_offers[df_new_offers['timestamp'] >= history_window_start]
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
        search_window = timedelta(hours=240) # Expanded to 10 days based on "Near Miss" analysis
        df_rank = df_rank.sort_values('timestamp').reset_index(drop=True)
        df_rank['rank_diff'] = df_rank['rank'].diff()
        
        for _, drop in offer_drops.iterrows():
            start_time = drop['timestamp']
            end_time = start_time + search_window
            
            rank_changes_in_window = df_rank[(df_rank['timestamp'] >= start_time) & (df_rank['timestamp'] <= end_time)]
            has_rank_drop = not rank_changes_in_window.empty and (rank_changes_in_window['rank_diff'] < 0).any()

            # Sparse Data Fallback Logic
            if not has_rank_drop:
                # Find the last rank recorded *before* the offer drop
                rank_before_slice = df_rank[df_rank['timestamp'] <= start_time]

                # Find the first rank recorded *after* the offer drop (looking up to 30 days ahead)
                lookahead_limit = start_time + timedelta(days=30)
                rank_after_slice = df_rank[(df_rank['timestamp'] > start_time) & (df_rank['timestamp'] <= lookahead_limit)]

                if not rank_before_slice.empty and not rank_after_slice.empty:
                    last_rank_val = rank_before_slice.iloc[-1]['rank']
                    next_rank_val = rank_after_slice.iloc[0]['rank']
                    next_rank_ts = rank_after_slice.iloc[0]['timestamp']

                    # If the next rank is lower (better) than the last rank before the drop,
                    # implies a sale happened sometime in the gap.
                    if next_rank_val < last_rank_val:
                        gap_days = (next_rank_ts - start_time).total_seconds() / 86400
                        has_rank_drop = True
                        logger.info(f"ASIN {asin}: Sparse Data Fallback - Inferred sale from rank drop {last_rank_val}->{next_rank_val} over {gap_days:.1f} days (Offer Drop at {start_time}).")

            # Near Miss Logging (Only if still False)
            if not has_rank_drop:
                near_miss_window_end = end_time + timedelta(hours=72)
                near_miss_rank_changes = df_rank[(df_rank['timestamp'] > end_time) & (df_rank['timestamp'] <= near_miss_window_end)]
                has_near_miss_rank_drop = not near_miss_rank_changes.empty and (near_miss_rank_changes['rank_diff'] < 0).any()
                if has_near_miss_rank_drop:
                    first_miss_time = near_miss_rank_changes[near_miss_rank_changes['rank_diff'] < 0].iloc[0]['timestamp']
                    hours_missed_by = (first_miss_time - end_time).total_seconds() / 3600
                    logger.info(f"ASIN {asin}: Near Miss - A rank drop occurred {hours_missed_by:.2f} hours after the window for an offer drop at {start_time}.")

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

def calculate_long_term_trend(sale_events):
    """Calculates the long-term price trend slope over the available history."""
    if not sale_events or len(sale_events) < 3:
        return "Insufficient data"

    try:
        df = pd.DataFrame(sale_events)
        # Convert timestamp to float for regression
        df['timestamp_val'] = df['event_timestamp'].apply(lambda x: x.timestamp())
        slope, intercept, r_value, p_value, std_err = st.linregress(df['timestamp_val'], df['inferred_sale_price_cents'])

        # Calculate % change over the period based on the regression line
        start_time = df['timestamp_val'].min()
        end_time = df['timestamp_val'].max()
        start_price = slope * start_time + intercept
        end_price = slope * end_time + intercept

        if start_price <= 0: return "Flat"

        percent_change = ((end_price - start_price) / start_price) * 100

        direction = "FLAT"
        if percent_change > 5: direction = "UP"
        elif percent_change < -5: direction = "DOWN"

        return f"{direction} ({percent_change:.1f}% over 3 years)"
    except Exception as e:
        logging.getLogger(__name__).error(f"Error calculating trend: {e}")
        return "Error"

def calculate_3yr_avg(sale_events):
    """Calculates the average price over the full history (now 3 years)."""
    if not sale_events: return -1
    prices = [s['inferred_sale_price_cents'] for s in sale_events]
    return sum(prices) / len(prices)

def analyze_sales_performance(product, sale_events):
    """
    Analyzes inferred sale events to determine peak/trough seasons and calculate
    the mode of peak season prices, with an XAI verification step. This replaces
    the previous `analyze_seasonality` function.
    """
    logger = logging.getLogger(__name__)
    asin = product.get('asin', 'N/A')
    xai_api_key = os.getenv("XAI_TOKEN") # Corrected from XAI_API_KEY

    MIN_SALES_FOR_ANALYSIS = 1

    # Initialize variables with defaults
    peak_price_mode_cents = -1
    peak_season_str = '-'
    trough_season_str = '-'
    expected_trough_price_cents = -1
    price_source = 'Inferred Sales'

    # --- Check Data Sufficiency ---
    if not sale_events or len(sale_events) < MIN_SALES_FOR_ANALYSIS:
        logger.debug(f"ASIN {asin}: Not enough sale events ({len(sale_events)}) for performance analysis. Attempting fallback to Keepa Stats.")

        stats = product.get('stats', {})
        candidates = []

        # Used (Index 2)
        avg90 = stats.get('avg90', [])
        if len(avg90) > 2 and avg90[2] > 0: candidates.append(avg90[2])

        avg365 = stats.get('avg365', [])
        if len(avg365) > 2 and avg365[2] > 0: candidates.append(avg365[2])

        # Used - Like New (Index 19)
        if len(avg90) > 19 and avg90[19] is not None and avg90[19] > 0: candidates.append(avg90[19])
        if len(avg365) > 19 and avg365[19] is not None and avg365[19] > 0: candidates.append(avg365[19])

        # Used - Very Good (Index 20)
        if len(avg90) > 20 and avg90[20] is not None and avg90[20] > 0: candidates.append(avg90[20])
        if len(avg365) > 20 and avg365[20] is not None and avg365[20] > 0: candidates.append(avg365[20])

        # Used - Good (Index 21) - often cleaner data
        if len(avg90) > 21 and avg90[21] > 0: candidates.append(avg90[21])
        if len(avg365) > 21 and avg365[21] > 0: candidates.append(avg365[21])

        # Used - Acceptable (Index 22)
        if len(avg90) > 22 and avg90[22] is not None and avg90[22] > 0: candidates.append(avg90[22])
        if len(avg365) > 22 and avg365[22] is not None and avg365[22] > 0: candidates.append(avg365[22])

        if candidates:
            peak_price_mode_cents = max(candidates)
            price_source = 'Keepa Stats Fallback'
            logger.info(f"ASIN {asin}: Fallback succeeded using Keepa Stats (Max Used Avg): ${peak_price_mode_cents/100:.2f}")
            # Do NOT return here. Continue to Reasonableness Check.
        else:
            logger.warning(f"ASIN {asin}: Fallback failed. No valid Used price history in stats.")
            # If fallback fails entirely, we return early as -1 price, triggering exclusion.
            return {'peak_price_mode_cents': -1, 'peak_season': '-', 'trough_season': '-', 'price_source': 'None'}

    else:
        # --- Normal Logic (Sufficient Sale Events) ---
        df = pd.DataFrame(sale_events)
        df['event_timestamp'] = pd.to_datetime(df['event_timestamp'])
        df['month'] = df['event_timestamp'].dt.month

        # --- Peak/Trough Season Identification ---
        monthly_stats = df.groupby('month')['inferred_sale_price_cents'].agg(['median', 'count'])

        if len(monthly_stats) < 1:
             return {'peak_price_mode_cents': -1, 'peak_season': '-', 'trough_season': '-'}

        peak_month = monthly_stats['median'].idxmax()
        # If only 1 month, peak and trough are the same
        trough_month = monthly_stats['median'].idxmin()
        peak_season_str = datetime(2000, int(peak_month), 1).strftime('%b')
        trough_season_str = datetime(2000, int(trough_month), 1).strftime('%b')

        # --- "List at" Price Calculation (Mode of Peak Season) ---
        peak_season_prices = df[df['month'] == peak_month]['inferred_sale_price_cents'].tolist()

        # --- Expected Trough Price Calculation (Median of Trough Season) ---
        trough_season_prices = df[df['month'] == trough_month]['inferred_sale_price_cents'].tolist()
        if trough_season_prices:
            expected_trough_price_cents = float(np.median(trough_season_prices))
            logger.info(f"ASIN {asin}: Calculated expected trough price: {expected_trough_price_cents/100:.2f} (Median of trough month {trough_month}).")
        else:
            logger.warning(f"ASIN {asin}: No prices found for trough month {trough_month}.")

        if not peak_season_prices:
            logger.warning(f"ASIN {asin}: No prices found for the determined peak month ({peak_month}).")
            return {'peak_price_mode_cents': -1, 'peak_season': peak_season_str, 'trough_season': trough_season_str}
        else:
            # Normal calculation
            # Calculate the mode. Scipy's mode is robust.
            mode_result = st.mode(peak_season_prices)
            if mode_result.count > 1:
                peak_price_mode_cents = float(mode_result.mode)
                logger.info(f"ASIN {asin}: Calculated peak price mode: {peak_price_mode_cents/100:.2f} (occurred {mode_result.count} times).")
            else:
                peak_price_mode_cents = float(np.median(peak_season_prices))
                logger.info(f"ASIN {asin}: No distinct mode found. Falling back to peak season median price: {peak_price_mode_cents/100:.2f}.")

    # --- Amazon Ceiling Logic ---
    stats = product.get('stats', {})

    # Extract Amazon prices (New)
    amz_current = stats.get('current', [None] * 2)[0] # stats.current[0]
    amz_180_avg = stats.get('avg180', []) # stats.avg180[0]
    amz_180 = amz_180_avg[0] if amz_180_avg else None
    amz_365_avg = stats.get('avg365', []) # stats.avg365[0]
    amz_365 = amz_365_avg[0] if amz_365_avg else None

    valid_amz_prices = []
    if amz_current and amz_current > 0: valid_amz_prices.append(amz_current)
    if amz_180 and amz_180 > 0: valid_amz_prices.append(amz_180)
    if amz_365 and amz_365 > 0: valid_amz_prices.append(amz_365)

    is_capped_by_ceiling = False
    if valid_amz_prices:
        min_amz_price = min(valid_amz_prices)
        ceiling_price_cents = min_amz_price * 0.90 # 90% of lowest Amazon price

        if peak_price_mode_cents > ceiling_price_cents:
            logger.info(f"ASIN {asin}: Calculated List at (${peak_price_mode_cents/100:.2f}) exceeds Amazon ceiling (${ceiling_price_cents/100:.2f}). Capping price.")
            peak_price_mode_cents = ceiling_price_cents
            is_capped_by_ceiling = True
        else:
            logger.info(f"ASIN {asin}: Calculated List at (${peak_price_mode_cents/100:.2f}) is within Amazon ceiling (${ceiling_price_cents/100:.2f}).")
    else:
        logger.debug(f"ASIN {asin}: No valid Amazon prices found for ceiling calculation. Proceeding with un-capped price.")

    # --- XAI Verification Step ---
    title = product.get('title', 'N/A')
    category_tree = product.get('categoryTree', [])
    category = ' > '.join(cat['name'] for cat in category_tree) if category_tree else 'N/A'

    # Additional Context
    binding = product.get('binding', 'N/A')
    page_count = product.get('numberOfPages', 'N/A')
    image_url = product.get('imagesCSV', '').split(',')[0] if product.get('imagesCSV') else 'N/A'
    if image_url != 'N/A':
        image_url = f"https://images-na.ssl-images-amazon.com/images/I/{image_url}"

    # Sales Rank Stats
    stats = product.get('stats', {})
    rank_current = stats.get('current', [None]*4)[3]
    rank_90 = stats.get('avg90', [None]*4)[3]
    rank_info = f"Current Rank: {rank_current}, 90-day Avg Rank: {rank_90}"

    # Monthly Sold (inferred from salesRanks or other heuristic if not direct)
    # Note: Keepa API returns monthlySold directly in some contexts, but often it's calculated.
    # For now, we will pass the rank info as a proxy for velocity.

    # --- Enhanced Logging for Debugging ---
    # Calculate 3yr metrics
    trend_info = calculate_long_term_trend(sale_events)
    avg_3yr_cents = calculate_3yr_avg(sale_events)
    avg_3yr_usd = f"{avg_3yr_cents/100:.2f}" if avg_3yr_cents > 0 else "N/A"

    logger.info(f"ASIN {asin}: Preparing for XAI check. Title='{title}', Category='{category}', Peak Season='{peak_season_str}', Price='${peak_price_mode_cents / 100.0:.2f}', Rank='{rank_info}', Trend='{trend_info}', 3yrAvg='${avg_3yr_usd}'")

    if is_capped_by_ceiling:
        logger.info(f"ASIN {asin}: Price is capped by Amazon Ceiling (Safe). Skipping AI Reasonableness Check.")
        is_reasonable = True
    elif price_source == 'Keepa Stats Fallback':
        logger.info(f"ASIN {asin}: Price Source is 'Keepa Stats Fallback'. Skipping AI Reasonableness Check to prevent false negatives due to insufficient context.")
        is_reasonable = True
    else:
        is_reasonable = _query_xai_for_reasonableness(
            title, category, peak_season_str, peak_price_mode_cents / 100.0, xai_api_key,
            binding=binding, page_count=page_count, image_url=image_url, rank_info=rank_info,
            trend_info=trend_info, avg_3yr_usd=avg_3yr_usd
        )

    if not is_reasonable:
        # If XAI deems the price unreasonable, we invalidate it by setting it to -1.
        # This signals downstream functions to treat it as "N/A" or "Too New".
        logger.warning(f"ASIN {asin}: XAI check FAILED. Price ${peak_price_mode_cents/100:.2f} was deemed unreasonable for '{title}'. Invalidating price.")
        peak_price_mode_cents = -1
    else:
        logger.info(f"ASIN {asin}: XAI check PASSED. Price is considered reasonable.")

    return {
        'peak_price_mode_cents': peak_price_mode_cents,
        'peak_season': peak_season_str,
        'trough_season': trough_season_str,
        'expected_trough_price_cents': expected_trough_price_cents,
        'price_source': price_source,
    }

# --- Memoization cache for analysis results ---
_analysis_cache = {}

def clear_analysis_cache():
    """Clears the memoization cache for sales analysis."""
    global _analysis_cache
    _analysis_cache = {}
    logging.info("Sales analysis memoization cache has been cleared.")

def _get_analysis(product):
    """
    Helper to get or compute sales performance analysis, caching the result.
    Uses the new analyze_sales_performance function.
    """
    asin = product.get('asin')
    if asin and asin in _analysis_cache:
        return _analysis_cache[asin]
    
    sale_events, _ = infer_sale_events(product)
    # The product object is passed to analyze_sales_performance for metadata context.
    analysis = analyze_sales_performance(product, sale_events)
    
    if asin:
        _analysis_cache[asin] = analysis
    return analysis

def get_peak_season(product):
    """Wrapper to get the Peak Season from the new analysis."""
    analysis = _get_analysis(product)
    return {'Peak Season': analysis.get('peak_season', '-')}

def get_list_at_price(product):
    """
    Wrapper to get the 'List at' price, which is the mode of peak season prices.
    Returns None if the price is invalid, signaling for exclusion.
    """
    analysis = _get_analysis(product)
    price_cents = analysis.get('peak_price_mode_cents', -1)
    if price_cents and price_cents > 0:
        return {'List at': f"${price_cents / 100:.2f}"}
    logger = logging.getLogger(__name__)
    asin = product.get('asin', 'N/A')
    logger.info(f"ASIN {asin}: No valid 'List at' price could be determined. This deal will be excluded.")
    return None

def get_trough_season(product):
    """Wrapper to get the Trough Season from the new analysis."""
    analysis = _get_analysis(product)
    return {'Trough Season': analysis.get('trough_season', '-')}

def get_expected_trough_price(product):
    """
    Wrapper to get the 'Expected Trough Price', which is the median of trough season prices.
    Returns None if the price is invalid.
    """
    analysis = _get_analysis(product)
    price_cents = analysis.get('expected_trough_price_cents', -1)
    if price_cents and price_cents > 0:
        return {'Expected Trough Price': f"${price_cents / 100:.2f}"}
    return {'Expected Trough Price': None}

def deal_trust(product):
    """Calculates a confidence score based on how many offer drops correlate with a rank drop."""
    sale_events, total_offer_drops = infer_sale_events(product)
    if total_offer_drops == 0:
        return {'Deal Trust': '-'}
    
    confidence = (len(sale_events) / total_offer_drops) * 100
    return {'Deal Trust': f"{confidence:.0f}%"}

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
