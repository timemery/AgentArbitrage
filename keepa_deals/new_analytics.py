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

    # Basic data check
    if 'csv' not in product or not isinstance(product['csv'], list) or len(product['csv']) < 13:
        # NOTE: Even if CSV is missing/bad, we might still have Stats for fallback.
        # But existing logic enforced this. Let's relax it slightly if we want pure fallback.
        # However, `infer_sale_events` needs CSV.
        pass

    sale_events, _ = infer_sale_events(product)

    mean_price_cents = -1

    # Try using inferred sales first
    if sale_events:
        try:
            df = pd.DataFrame(sale_events)
            df['event_timestamp'] = pd.to_datetime(df['event_timestamp'])
            one_year_ago = datetime.now() - timedelta(days=365)
            df_last_year = df[df['event_timestamp'] >= one_year_ago]

            if len(df_last_year) >= 1:
                mean_price_cents = df_last_year['inferred_sale_price_cents'].mean()
                logger.info(f"ASIN {asin}: Calculated {COLUMN_NAME} from {len(df_last_year)} inferred sales: ${mean_price_cents/100:.2f}")
            else:
                logger.info(f"ASIN {asin}: Found {len(sale_events)} total sales, but 0 in last 365 days.")
        except Exception as e:
            logger.error(f"ASIN {asin}: Error calculating {COLUMN_NAME} from sales: {e}", exc_info=True)

    # Fallback if inferred sales failed (or no sales in last year)
    if mean_price_cents == -1:
        logger.info(f"ASIN {asin}: Insufficient inferred sales for {COLUMN_NAME}. Attempting fallback to Keepa Stats.")
        stats = product.get('stats', {})
        candidates = []

        # Used (Index 2)
        avg365 = stats.get('avg365', [])
        if len(avg365) > 2 and avg365[2] > 0: candidates.append(avg365[2])

        # Used - Good (Index 21)
        if len(avg365) > 21 and avg365[21] > 0: candidates.append(avg365[21])

        # Used - Like New (Index 19)
        if len(avg365) > 19 and avg365[19] > 0: candidates.append(avg365[19])

        if candidates:
            # Use the Max (Optimistic)
            mean_price_cents = max(candidates)
            logger.info(f"ASIN {asin}: Fallback succeeded for {COLUMN_NAME} using Keepa Stats: ${mean_price_cents/100:.2f}")
        else:
            logger.warning(f"ASIN {asin}: Fallback failed for {COLUMN_NAME}. No valid price history in Stats.")
            return None

    # Final check to ensure we don't return negative
    if mean_price_cents <= 0:
        return None

    return {COLUMN_NAME: mean_price_cents / 100.0}

def get_percent_discount(avg_price, now_price, logger=None):
    """
    Calculates the percentage discount of the current 'Price Now' compared to the '1yr. Avg.'
    """
    COLUMN_NAME = "% Down"
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

def get_offer_count_trend(product, logger=None):
    """
    Calculates the trend for Used Offer Count.
    Returns: "Count ↘", "Count ↗", "Count ⇨", or "-"
    """
    if not logger:
        logger = logging.getLogger(__name__)

    try:
        stats = product.get('stats', {})

        # Current Used Offer Count logic (mirrors used_offer_count_current in stable_products.py)
        offer_count_fba_new = stats.get('offerCountFBA')
        offer_count_fbm_new = stats.get('offerCountFBM')
        total_offer_count = stats.get('totalOfferCount')

        if total_offer_count is None or not isinstance(total_offer_count, int) or total_offer_count < 0:
            return {'Offers': '-'}

        val_fba_new = offer_count_fba_new if isinstance(offer_count_fba_new, int) and offer_count_fba_new >= 0 else 0
        val_fbm_new = offer_count_fbm_new if isinstance(offer_count_fbm_new, int) and offer_count_fbm_new >= 0 else 0
        current_new_total = val_fba_new + val_fbm_new

        current_used_count = total_offer_count - current_new_total
        if current_used_count < 0: current_used_count = 0

        # 30-day Avg Used Offer Count logic (mirrors used_offer_count_30_days_avg in stable_products.py)
        avg30_array = stats.get('avg30', [])
        avg_used_count = -1
        if avg30_array and len(avg30_array) > 12:
            avg_used_count = avg30_array[12]

        if avg_used_count == -1 or avg_used_count is None:
             return {'Offers': str(current_used_count)}

        arrow = "⇨"
        if current_used_count > avg_used_count:
            arrow = "↗" # Rising (Bad)
        elif current_used_count < avg_used_count:
            arrow = "↘" # Falling (Good)

        return {'Offers': f"{current_used_count} {arrow}"}

    except Exception as e:
        logger.error(f"Error calculating Offer Count Trend: {e}", exc_info=True)
        return {'Offers': '-'}

def get_offer_count_trend_180(product, logger=None):
    """
    Calculates the trend for Used Offer Count (180 days).
    Compares 90-day avg to 180-day avg.
    Returns: "Count ↘", "Count ↗", "Count ⇨", or "-"
    """
    if not logger:
        logger = logging.getLogger(__name__)

    try:
        stats = product.get('stats', {})

        # 180-day Avg Used Offer Count (index 12)
        avg180_array = stats.get('avg180', [])
        avg180_count = -1
        if avg180_array and len(avg180_array) > 12:
            avg180_count = avg180_array[12]

        if avg180_count == -1 or avg180_count is None:
             return {'Offers 180': '-'}

        # 90-day Avg Used Offer Count (index 12)
        avg90_array = stats.get('avg90', [])
        avg90_count = -1
        if avg90_array and len(avg90_array) > 12:
            avg90_count = avg90_array[12]

        # If we can't get 90-day avg, we can't determine trend
        if avg90_count == -1 or avg90_count is None:
            return {'Offers 180': str(avg180_count)}

        arrow = "⇨"
        if avg90_count > avg180_count:
            arrow = "↗" # Rising
        elif avg90_count < avg180_count:
            arrow = "↘" # Falling

        return {'Offers 180': f"{avg180_count} {arrow}"}

    except Exception as e:
        logger.error(f"Error calculating Offer Count Trend 180: {e}", exc_info=True)
        return {'Offers 180': '-'}

def get_offer_count_trend_365(product, logger=None):
    """
    Calculates the trend for Used Offer Count (365 days).
    Compares 180-day avg to 365-day avg.
    Returns: "Count ↘", "Count ↗", "Count ⇨", or "-"
    """
    if not logger:
        logger = logging.getLogger(__name__)

    try:
        stats = product.get('stats', {})

        # 365-day Avg Used Offer Count (index 12)
        avg365_array = stats.get('avg365', [])
        avg365_count = -1
        if avg365_array and len(avg365_array) > 12:
            avg365_count = avg365_array[12]

        if avg365_count == -1 or avg365_count is None:
             return {'Offers 365': '-'}

        # 180-day Avg Used Offer Count (index 12)
        avg180_array = stats.get('avg180', [])
        avg180_count = -1
        if avg180_array and len(avg180_array) > 12:
            avg180_count = avg180_array[12]

        if avg180_count == -1 or avg180_count is None:
            return {'Offers 365': str(avg365_count)}

        arrow = "⇨"
        if avg180_count > avg365_count:
            arrow = "↗" # Rising
        elif avg180_count < avg365_count:
            arrow = "↘" # Falling

        return {'Offers 365': f"{avg365_count} {arrow}"}

    except Exception as e:
        logger.error(f"Error calculating Offer Count Trend 365: {e}", exc_info=True)
        return {'Offers 365': '-'}
# Refreshed
