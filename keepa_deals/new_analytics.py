# keepa_deals/new_analytics.py
# New module for additional analytical columns to prevent circular dependencies.

import logging
from datetime import datetime, timedelta
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
    Returns None if there are not enough sale events.
    """
    COLUMN_NAME = "1yr. Avg."
    if not logger:
        logger = logging.getLogger(__name__)
    asin = product.get('asin', 'N/A')

    if 'csv' not in product or not isinstance(product['csv'], list) or len(product['csv']) < 13:
        logger.warning(f"ASIN {asin}: Incomplete data for {COLUMN_NAME}.")
        return None

    sale_events, _ = infer_sale_events(product)
    if not sale_events:
        return None

    try:
        df = pd.DataFrame(sale_events)
        df['event_timestamp'] = pd.to_datetime(df['event_timestamp'])
        one_year_ago = datetime.now() - timedelta(days=365)
        df_last_year = df[df['event_timestamp'] >= one_year_ago]

        if len(df_last_year) < 3:
            logger.info(f"ASIN {asin}: Insufficient sale events ({len(df_last_year)}) for a meaningful average.")
            return None

        mean_price_cents = df_last_year['inferred_sale_price_cents'].mean()
        return {COLUMN_NAME: mean_price_cents / 100.0}

    except Exception as e:
        logger.error(f"ASIN {asin}: Error calculating {COLUMN_NAME}: {e}", exc_info=True)
        return None

def get_percent_discount(avg_price, now_price, logger=None):
    """
    Calculates the percentage discount of the current 'Price Now' compared to the '1yr. Avg.'
    """
    COLUMN_NAME = "Percent Down"
    if not logger:
        logger = logging.getLogger(__name__)

    if avg_price is None or now_price is None or avg_price <= 0:
        return None

    try:
        if now_price > avg_price:
            return {COLUMN_NAME: 0.0}

        discount = ((avg_price - now_price) / avg_price) * 100
        return {COLUMN_NAME: discount}

    except (ValueError, TypeError) as e:
        logger.error(f"Error calculating discount with inputs '{avg_price}' and '{now_price}': {e}", exc_info=True)
        return None

from itertools import groupby

def get_trend(product, logger=None):
    """
    Indicates the price trend based on a dynamic sample of recent unique price changes.
    Returns an arrow string: ⇧ (up), ⇩ (down), ⇨ (flat).
    """
    COLUMN_NAME = "Trend"
    if not logger:
        logger = logging.getLogger(__name__)
    asin = product.get('asin', 'N/A')

    stats = product.get('stats', {})
    avg_365_rank_raw = stats.get('avg365', [])
    avg_rank = -1
    if len(avg_365_rank_raw) > 0 and avg_365_rank_raw[0] is not None:
        avg_rank = avg_365_rank_raw[0]

    sample_size = 3
    if avg_rank > 0:
        if avg_rank < 100000: sample_size = 10
        elif avg_rank < 500000: sample_size = 5

    csv_data = product.get('csv', [])
    combined_history = []
    if csv_data and len(csv_data) > 1 and csv_data[1]: combined_history.extend(csv_data[1])
    if csv_data and len(csv_data) > 2 and csv_data[2]: combined_history.extend(csv_data[2])

    if not combined_history:
        return {COLUMN_NAME: "⇨"}

    price_points = sorted([(combined_history[i], combined_history[i+1]) for i in range(0, len(combined_history), 2) if combined_history[i+1] > 0])
    unique_prices = [k for k, g in groupby([p[1] for p in price_points])]

    if len(unique_prices) < 2:
        return {COLUMN_NAME: "⇨"}

    analysis_window = unique_prices[-sample_size:]
    if len(analysis_window) < 2:
        return {COLUMN_NAME: "⇨"}

    first_price = analysis_window[0]
    last_price = analysis_window[-1]

    if first_price == 0:
        return {COLUMN_NAME: "⇨"}

    trend_percent = ((last_price - first_price) / first_price) * 100

    if trend_percent > 0:
        return {COLUMN_NAME: "⇧"}
    elif trend_percent < 0:
        return {COLUMN_NAME: "⇩"}
    else:
        return {COLUMN_NAME: "⇨"}

def analyze_sales_rank_trends(product):
    """
    Analyzes the 30-day and 90-day sales rank trends.
    """
    stats = product.get('stats', {})
    current_rank = stats.get('current', [-1]*4)[3]
    avg30 = stats.get('avg30', [-1]*4)[3]
    avg90 = stats.get('avg90', [-1]*4)[3]

    if current_rank == -1 or avg30 == -1 or avg90 == -1:
        return {"Sales Rank Trend %": 0}

    # Compare current rank to 30-day average
    thirty_day_trend = ((current_rank - avg30) / avg30) * 100 if avg30 > 0 else 0

    # Simple average of the two trends for a single metric
    # A more sophisticated model could be used here.
    return {"Sales Rank Trend %": thirty_day_trend}
