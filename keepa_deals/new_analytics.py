# keepa_deals/new_analytics.py
# New module for additional analytical columns to prevent circular dependencies.

import logging
import time
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from .stable_calculations import infer_sale_events
# Keepa epoch is minutes from 2011-01-01
KEEPA_EPOCH = datetime(2011, 1, 1)

def format_time_ago(minutes_ago):
    """Converts minutes into a human-readable 'time ago' string."""
    if minutes_ago is None or minutes_ago < 0:
        return "-"
    if minutes_ago < 1:
        return "just now"
    if minutes_ago < 60:
        return f"{int(minutes_ago)} minutes ago"
    hours_ago = minutes_ago / 60
    if hours_ago < 24:
        return f"{int(hours_ago)} hours ago"
    days_ago = hours_ago / 24
    if days_ago < 7:
        return f"{int(days_ago)} days ago"
    weeks_ago = days_ago / 7
    if weeks_ago < 4:
        return f"{int(weeks_ago)} weeks ago"
    months_ago = days_ago / 30
    if months_ago < 12:
        return f"{int(months_ago)} months ago"
    years_ago = days_ago / 365
    return f"{int(years_ago)} years ago"

def get_1yr_avg_sale_price(product, logger=None):
    """
    Displays the median inferred sale price over the last 365 days.
    Returns 'Too New' if there are not enough sale events.
    """
    COLUMN_NAME = "1yr. Avg."
    if not logger:
        logger = logging.getLogger(__name__)
    asin = product.get('asin', 'N/A')
    logger.debug(f"ASIN {asin}: Running get_1yr_avg_sale_price.")

    # Defensive check for required data
    if 'csv' not in product or not isinstance(product['csv'], list) or len(product['csv']) < 13:
        logger.warning(f"ASIN {asin}: Product data is missing 'csv' field or 'csv' is incomplete. Cannot calculate {COLUMN_NAME}.")
        return {COLUMN_NAME: "Too New"}

    sale_events, _ = infer_sale_events(product)

    if not sale_events:
        logger.debug(f"ASIN {asin}: No sale events found for {COLUMN_NAME} calculation.")
        return {COLUMN_NAME: "Too New"}

    try:
        df = pd.DataFrame(sale_events)
        df['event_timestamp'] = pd.to_datetime(df['event_timestamp'])
        logger.debug(f"ASIN {asin}: Created DataFrame with {len(df)} sale events.")

        # Filter for sales in the last 365 days
        one_year_ago = datetime.now() - timedelta(days=365)
        df_last_year = df[df['event_timestamp'] >= one_year_ago]
        logger.debug(f"ASIN {asin}: Found {len(df_last_year)} sale events in the last year.")

        if len(df_last_year) < 3:
            logger.info(f"ASIN {asin}: Insufficient sale events in the last year ({len(df_last_year)}) to calculate a meaningful average.")
            return {COLUMN_NAME: "Too New"}

        # Calculate and log both the median and mean price
        median_price_cents = df_last_year['inferred_sale_price_cents'].median()
        mean_price_cents = df_last_year['inferred_sale_price_cents'].mean()

        logger.info(f"ASIN {asin}: 1yr Avg Price (Median): {median_price_cents/100:.2f}, (Mean): {mean_price_cents/100:.2f}")

        # Use the mean for the official value as requested.
        final_price_cents = mean_price_cents

        if pd.isna(final_price_cents) or final_price_cents <= 0:
            logger.warning(f"ASIN {asin}: Final price calculation resulted in an invalid value: {final_price_cents}")
            return {COLUMN_NAME: "Too New"}

        result_value = f"${final_price_cents / 100:.2f}"
        logger.debug(f"ASIN {asin}: Calculated {COLUMN_NAME} (median) sale price: {result_value}")
        return {COLUMN_NAME: result_value}

    except Exception as e:
        logger.error(f"ASIN {asin}: Error calculating {COLUMN_NAME}: {e}", exc_info=True)
        return {COLUMN_NAME: "Error"}

def get_percent_discount(avg_price_str, best_price_str, logger=None):
    """
    Displays the percentage discount of the current 'Best Price' compared to the '1yr. Avg.' sale price.
    This function now takes the pre-calculated string values to be more efficient.
    """
    COLUMN_NAME = "% Down"
    if not logger:
        logger = logging.getLogger(__name__)
    logger.debug(f"Running get_percent_discount with avg_price_str: '{avg_price_str}', best_price_str: '{best_price_str}'.")

    if not avg_price_str or avg_price_str == "-":
        logger.debug("1yr. Avg. price is unavailable, cannot calculate discount.")
        return {COLUMN_NAME: "-"}

    if avg_price_str in ["Too New", "Error"]:
        logger.debug(f"Propagating '{avg_price_str}' status for % Down column.")
        return {COLUMN_NAME: avg_price_str}

    if not best_price_str or best_price_str == "-":
        logger.debug("Best Price is unavailable, cannot calculate discount.")
        return {COLUMN_NAME: "-"}

    try:
        # Convert string prices to floats
        avg_price = float(avg_price_str.replace("$", "").replace(",", ""))
        best_price = float(best_price_str.replace("$", "").replace(",", ""))
        logger.debug(f"Parsed avg_price: {avg_price}, best_price: {best_price}")

        if avg_price <= 0:
            logger.warning(f"1yr. Avg. price is zero or less ({avg_price}), cannot calculate discount.")
            return {COLUMN_NAME: "-"}

        if best_price > avg_price:
            logger.debug(f"Best price ({best_price}) is higher than the average price ({avg_price}). Discount is 0%.")
            return {COLUMN_NAME: "0%"}

        # Calculate discount
        discount = ((avg_price - best_price) / avg_price) * 100
        result_value = f"{discount:.0f}%"

        logger.debug(f"Discount calculated: {discount:.2f}% (Avg: {avg_price}, Best: {best_price}). Returning: {result_value}")
        return {COLUMN_NAME: result_value}

    except (ValueError, TypeError) as e:
        logger.error(f"Error calculating discount with inputs '{avg_price_str}' and '{best_price_str}': {e}", exc_info=True)
        return {COLUMN_NAME: "-"}

from itertools import groupby

def get_trend(product, logger=None):
    """
    Indicates the price trend based on a dynamic sample of recent unique price changes.
    The sample size is determined by the 365-day average sales rank.
    It analyzes both NEW and USED price histories combined.
    """
    if not logger:
        logger = logging.getLogger(__name__)
    asin = product.get('asin', 'N/A')
    logger.debug(f"ASIN {asin}: Running get_trend with dynamic sampling.")

    # --- Determine Dynamic Sample Size ---
    stats = product.get('stats', {})
    SALES_RANK_INDEX = 0  # Assuming sales rank is at index 0
    avg_365_rank_raw = stats.get('avg365', [])

    avg_rank = -1
    if len(avg_365_rank_raw) > SALES_RANK_INDEX and avg_365_rank_raw[SALES_RANK_INDEX] is not None:
        avg_rank = avg_365_rank_raw[SALES_RANK_INDEX]

    sample_size = 3  # Default for low velocity
    if avg_rank > 0:
        if avg_rank < 100000:
            sample_size = 10  # High velocity
        elif avg_rank < 500000:
            sample_size = 5   # Medium velocity
    logger.debug(f"ASIN {asin}: Using dynamic sample size of {sample_size} based on 365-day avg rank of {avg_rank}.")

    # --- Combine and Process Price Histories ---
    csv_data = product.get('csv', [])
    combined_history = []

    # NEW price history (index 1)
    if csv_data and len(csv_data) > 1 and csv_data[1] and len(csv_data[1]) >= 2:
        combined_history.extend(csv_data[1])
    # USED price history (index 2)
    if csv_data and len(csv_data) > 2 and csv_data[2] and len(csv_data[2]) >= 2:
        combined_history.extend(csv_data[2])

    if not combined_history:
        logger.debug(f"ASIN {asin}: No NEW or USED price data available.")
        return {"Trend": "⇨"} # Flat if no data

    # Create pairs of (timestamp, price) and sort by timestamp
    price_points = sorted([(combined_history[i], combined_history[i+1]) for i in range(0, len(combined_history), 2) if combined_history[i+1] > 0])

    # Get unique consecutive prices
    unique_prices = [k for k, g in groupby([p[1] for p in price_points])]
    logger.debug(f"ASIN {asin}: Found {len(unique_prices)} unique consecutive prices from combined history.")

    if len(unique_prices) < 2:
        logger.info(f"ASIN {asin}: Not enough unique price points ({len(unique_prices)}) to determine a trend.")
        return {"Trend": "⇨"} # Flat if not enough data

    # --- Analyze Trend from Dynamic Sample ---
    analysis_window = unique_prices[-sample_size:]
    logger.debug(f"ASIN {asin}: Analyzing last {len(analysis_window)} prices: {analysis_window}")

    if len(analysis_window) < 2:
        return {"Trend": "⇨"}

    first_price = analysis_window[0]
    last_price = analysis_window[-1]

    trend_symbol = "⇨" # Default to flat
    if last_price > first_price:
        trend_symbol = "⇧"
    elif last_price < first_price:
        trend_symbol = "⇩"

    logger.debug(f"ASIN {asin}: Final trend determined. First: {first_price}, Last: {last_price}, Symbol: {trend_symbol}")
    return {"Trend": trend_symbol}