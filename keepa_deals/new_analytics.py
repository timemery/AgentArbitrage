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
    """
    COLUMN_NAME = "1yr. Avg."
    if not logger:
        logger = logging.getLogger(__name__)
    asin = product.get('asin', 'N/A')
    logger.debug(f"ASIN {asin}: Running get_1yr_avg_sale_price.")

    # Defensive check for required data
    if 'csv' not in product or not isinstance(product['csv'], list) or len(product['csv']) < 13:
        logger.warning(f"ASIN {asin}: Product data is missing 'csv' field or 'csv' is incomplete. Cannot calculate {COLUMN_NAME}.")
        return {COLUMN_NAME: "-"}

    sale_events, _ = infer_sale_events(product)

    if not sale_events:
        logger.debug(f"ASIN {asin}: No sale events found for {COLUMN_NAME} calculation.")
        return {COLUMN_NAME: "-"}

    try:
        df = pd.DataFrame(sale_events)
        df['event_timestamp'] = pd.to_datetime(df['event_timestamp'])
        logger.debug(f"ASIN {asin}: Created DataFrame with {len(df)} sale events.")

        # Filter for sales in the last 365 days
        one_year_ago = datetime.now() - timedelta(days=365)
        df_last_year = df[df['event_timestamp'] >= one_year_ago]
        logger.debug(f"ASIN {asin}: Found {len(df_last_year)} sale events in the last year.")

        if len(df_last_year) < 3:
            logger.info(f"ASIN {asin}: Insufficient sale events in the last year ({len(df_last_year)}) to calculate a meaningful median.")
            return {COLUMN_NAME: "-"}

        # Calculate the median price
        median_price_cents = df_last_year['inferred_sale_price_cents'].median()
        logger.debug(f"ASIN {asin}: Median price (cents) calculated: {median_price_cents}")


        if pd.isna(median_price_cents) or median_price_cents <= 0:
            logger.warning(f"ASIN {asin}: Median price calculation resulted in an invalid value: {median_price_cents}")
            return {COLUMN_NAME: "-"}

        result_value = f"${median_price_cents / 100:.2f}"
        logger.debug(f"ASIN {asin}: Calculated {COLUMN_NAME} (median) sale price: {result_value}")
        return {COLUMN_NAME: result_value}

    except Exception as e:
        logger.error(f"ASIN {asin}: Error calculating {COLUMN_NAME}: {e}", exc_info=True)
        return {COLUMN_NAME: "-"}

def get_percent_discount(product, best_price_str, logger=None):
    """
    Displays the percentage discount of the current 'Best Price' compared to the '1yr. Avg.' sale price.
    """
    if not logger:
        logger = logging.getLogger(__name__)
    asin = product.get('asin', 'N/A')
    logger.debug(f"ASIN {asin}: Running get_percent_discount with best_price_str: '{best_price_str}'.")

    # Get the 1yr average price
    avg_price_dict = get_1yr_avg_sale_price(product, logger)
    avg_price_str = avg_price_dict.get("1yr. Avg.", "-")
    logger.debug(f"ASIN {asin}: get_1yr_avg_sale_price returned: {avg_price_str}")

    if avg_price_str == "-":
        logger.debug(f"ASIN {asin}: 1yr. Avg. price is unavailable, cannot calculate discount.")
        return {"% ⇩": "-"}

    if not best_price_str or best_price_str == "-":
        logger.debug(f"ASIN {asin}: Best Price is unavailable, cannot calculate discount.")
        return {"% ⇩": "-"}

    try:
        # Convert string prices to floats
        avg_price = float(avg_price_str.replace("$", ""))
        best_price = float(best_price_str.replace("$", ""))
        logger.debug(f"ASIN {asin}: Parsed avg_price: {avg_price}, best_price: {best_price}")


        if avg_price <= 0:
            logger.warning(f"ASIN {asin}: 1yr. Avg. price is zero or less, cannot calculate discount.")
            return {"% ⇩": "-"}

        # Calculate discount
        discount = ((avg_price - best_price) / avg_price) * 100
        result_value = f"{discount:.0f}%"

        logger.debug(f"ASIN {asin}: Discount calculated: {discount:.2f}% (Avg: {avg_price}, Best: {best_price}). Returning: {result_value}")
        return {"% ⇩": result_value}

    except (ValueError, TypeError) as e:
        logger.error(f"ASIN {asin}: Error calculating discount: {e}", exc_info=True)
        return {"% ⇩": "-"}

def get_trend(product, logger=None):
    """
    Indicates the price trend over the last 30 days using linear regression.
    """
    if not logger:
        logger = logging.getLogger(__name__)
    asin = product.get('asin', 'N/A')
    logger.debug(f"ASIN {asin}: Running get_trend.")

    csv_data = product.get('csv', [])

    # Using USED price history (index 2) for trend analysis
    if not csv_data or len(csv_data) < 3 or not csv_data[2] or len(csv_data[2]) < 4:
        logger.debug(f"ASIN {asin}: Insufficient CSV data for trend analysis. csv_data length: {len(csv_data) if csv_data else 0}")
        return {"Trend": "-"}

    try:
        price_history = csv_data[2] # USED price
        df = pd.DataFrame(np.array(price_history).reshape(-1, 2), columns=['timestamp', 'price'])
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='m', origin=KEEPA_EPOCH)
        logger.debug(f"ASIN {asin}: Created DataFrame for trend analysis with {len(df)} data points.")

        # Filter for the last 30 days
        thirty_days_ago = datetime.now() - timedelta(days=30)
        df_last_30_days = df[df['datetime'] >= thirty_days_ago].copy()
        logger.debug(f"ASIN {asin}: Found {len(df_last_30_days)} data points in the last 30 days.")

        if len(df_last_30_days) < 2:
            logger.info(f"ASIN {asin}: Not enough data points in the last 30 days to determine a trend.")
            return {"Trend": "-"}

        # Perform linear regression
        # Convert datetime to a numerical format (e.g., seconds since the first timestamp in the window)
        df_last_30_days['time_elapsed'] = (df_last_30_days['datetime'] - df_last_30_days['datetime'].iloc[0]).dt.total_seconds()

        # Drop rows where price is -1 (no data)
        df_last_30_days = df_last_30_days[df_last_30_days['price'] > 0]
        logger.debug(f"ASIN {asin}: Found {len(df_last_30_days)} valid data points (>0) in the last 30 days.")

        if len(df_last_30_days) < 2:
            logger.info(f"ASIN {asin}: Not enough valid data points (>0) in the last 30 days to determine a trend.")
            return {"Trend": "-"}

        x = df_last_30_days['time_elapsed']
        y = df_last_30_days['price']

        # Using numpy's polyfit for linear regression (degree=1)
        slope, _ = np.polyfit(x, y, 1)

        # Determine trend based on the slope
        if slope > 0.01:  # Threshold to avoid noise being classified as a trend
            trend_symbol = "⇧"
        elif slope < -0.01:
            trend_symbol = "⇩"
        else:
            trend_symbol = "-"

        logger.debug(f"ASIN {asin}: Trend analysis slope: {slope}. Symbol: {trend_symbol}")
        return {"Trend": trend_symbol}

    except Exception as e:
        logger.error(f"ASIN {asin}: Error calculating trend: {e}", exc_info=True)
        return {"Trend": "-"}