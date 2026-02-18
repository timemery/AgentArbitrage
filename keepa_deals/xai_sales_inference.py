import logging
import pandas as pd
import numpy as np
import os
import json
import httpx
from datetime import datetime, timedelta
from .xai_token_manager import XaiTokenManager
from .xai_cache import XaiCache

# Initialize token manager
xai_token_manager = XaiTokenManager()
# Initialize cache (though we might not use it heavily yet)
xai_cache = XaiCache()

logger = logging.getLogger(__name__)

# Keepa epoch is minutes from 2011-01-01
KEEPA_EPOCH = datetime(2011, 1, 1)

def _convert_ktm_to_datetime(df):
    """Converts a DataFrame's timestamp column from Keepa Time Minutes to datetime objects."""
    # Coerce to numeric, turning any non-numeric strings into NaN (which becomes NaT)
    numeric_timestamps = pd.to_numeric(df['timestamp'], errors='coerce')
    df['timestamp'] = pd.to_datetime(numeric_timestamps, unit='m', origin=KEEPA_EPOCH).astype('datetime64[ns]')
    return df

def format_history_for_xai(product, days=100):
    """
    Extracts relevant history (Rank, Used Price, Used Offer Count) for the last n days
    and formats it as a compact time-series text for the LLM.
    Ensures initial state (at start of window) is captured.
    """
    asin = product.get('asin')
    csv_data = product.get('csv', [])

    if not isinstance(csv_data, list) or len(csv_data) < 13:
        return None

    # Extract history arrays
    rank_history = csv_data[3]
    used_price_history = csv_data[2]
    used_offer_count_history = csv_data[12] # Used offer count

    if not rank_history or not used_price_history:
        return None

    # Convert to DataFrames
    def to_df(hist, col_name):
        if not hist or len(hist) < 2: return None
        # Keepa history is [time, val, time, val...]. Reshape to (N, 2)
        try:
            arr = np.array(hist)
            # Ensure even length
            if len(arr) % 2 != 0:
                arr = arr[:-1]
            df = pd.DataFrame(arr.reshape(-1, 2), columns=['timestamp', col_name])
            return _convert_ktm_to_datetime(df)
        except Exception as e:
            logger.warning(f"Error converting history to DF for {asin}: {e}")
            return None

    df_rank = to_df(rank_history, 'Rank')
    df_price = to_df(used_price_history, 'Price')
    df_offers = to_df(used_offer_count_history, 'Offers')

    if df_rank is None or df_price is None:
        return None

    start_date = datetime.now() - timedelta(days=days)

    # Filter timestamps for the target window, but KEEP the source DFs full
    # so merge_asof can find the 'previous' value from before the window (Initial State).

    ts_rank = df_rank[df_rank['timestamp'] >= start_date]['timestamp']
    ts_price = df_price[df_price['timestamp'] >= start_date]['timestamp']

    timestamps_list = [ts_rank, ts_price]

    if df_offers is not None:
        ts_offers = df_offers[df_offers['timestamp'] >= start_date]['timestamp']
        timestamps_list.append(ts_offers)

    # Ensure start_date is compatible (datetime64[ns])
    start_date_ts = pd.Timestamp(start_date)

    if not timestamps_list or all(ts.empty for ts in timestamps_list):
        # No data in the window? Maybe just one initial state?
        # Create at least one point at start_date
        timestamps = pd.Series([start_date_ts])
    else:
        timestamps = pd.concat(timestamps_list).sort_values().drop_duplicates().reset_index(drop=True)
        # Ensure start_date is included to capture initial state if not present
        if timestamps.iloc[0] > start_date_ts:
            timestamps = pd.concat([pd.Series([start_date_ts]), timestamps]).sort_values().reset_index(drop=True)

    df_merged = pd.DataFrame({'timestamp': timestamps})

    # Merge AsOf to get the state at each timestamp
    # direction='backward' finds the last known value at or before the timestamp
    try:
        df_merged = pd.merge_asof(df_merged, df_rank, on='timestamp', direction='backward')
        df_merged = pd.merge_asof(df_merged, df_price, on='timestamp', direction='backward')
        if df_offers is not None:
            df_merged = pd.merge_asof(df_merged, df_offers, on='timestamp', direction='backward')
        else:
            df_merged['Offers'] = 'N/A'
    except Exception as e:
        logger.error(f"Error during merge_asof for {asin}: {e}")
        return None

    # Drop rows where critical data is NaN (e.g. before history started)
    df_merged = df_merged.dropna(subset=['Rank', 'Price'])

    if df_merged.empty:
        return None

    lines = []
    lines.append("Time | Rank | Used Price | Offers")
    lines.append("---|---|---|---")

    last_row_vals = None
    count = 0

    for _, row in df_merged.iterrows():
        ts_str = row['timestamp'].strftime('%Y-%m-%d %H:%M')
        rank = int(row['Rank']) if not pd.isna(row['Rank']) else '-'
        price = f"${row['Price']/100:.2f}" if not pd.isna(row['Price']) else '-'
        offers = int(row['Offers']) if not pd.isna(row['Offers']) and row['Offers'] != 'N/A' else '-'

        current_vals = (rank, price, offers)

        # Output if values changed, or if it's the first row (Initial State)
        if current_vals != last_row_vals:
            lines.append(f"{ts_str} | {rank} | {price} | {offers}")
            last_row_vals = current_vals
            count += 1
            if count > 150: # Token limit safety
                lines.append("... (truncated) ...")
                break

    return "\n".join(lines)

def query_xai_sales_inference(history_text, product):
    """
    Queries XAI to identify sales in the provided history.
    """
    api_key = os.getenv("XAI_TOKEN")
    if not api_key:
        logger.warning("No XAI_TOKEN found.")
        return None

    title = product.get('title', 'Unknown')
    cat_tree = product.get('categoryTree', [])
    category = cat_tree[-1]['name'] if cat_tree else 'Unknown'

    if not xai_token_manager.request_permission():
        logger.warning(f"XAI daily limit reached. Cannot perform sales inference for '{title}'.")
        return None

    # Double braces {{ }} to escape JSON structure in f-string
    prompt = f"""
    You are an expert Amazon Arbitrage Analyst.
    Your goal is to identify "Inferred Sales" from the following historical data for the product: "{title}" ({category}).

    Logic for a sale:
    - Typically, a drop in "Offers" (Used Offer Count) suggests a unit was sold.
    - However, offers can also be removed by sellers.
    - A corresponding drop (improvement) in "Rank" (Sales Rank gets smaller) shortly after an offer drop is a strong confirmation of a sale.
    - Sometimes Rank drops without an offer drop (if stock depth > 1).
    - Sometimes Offers drop without a rank drop (delisted).
    - Sometimes Rank drops and recovers between data points (sparse data).

    Task:
    Analyze the provided time-series data. Identify the most likely "Sold Price" for any VALID sales you detect in this period.
    Ignore price drops that look like repricing wars unless accompanied by a sale signal.

    Return a JSON object with:
    1. "sales_found": count of confirmed sales.
    2. "events": list of objects, each with {{"date": "YYYY-MM-DD", "price": float (number only)}}.
    3. "estimated_market_price": your best estimate of the current true market value for a Used copy based on these sales.
    4. "confidence": "High", "Medium", or "Low".
    5. "reasoning": brief explanation.

    Data (Last ~100 days):
    {history_text}
    """

    payload = {
        "messages": [{"role": "user", "content": prompt}],
        "model": "grok-4-fast-reasoning",
        "temperature": 0.2,
        "max_tokens": 500
    }
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        with httpx.Client(timeout=60.0) as client:
            response = client.post("https://api.x.ai/v1/chat/completions", headers=headers, json=payload)
            response.raise_for_status()
            content = response.json()['choices'][0]['message']['content']

            # Parse JSON
            try:
                # Sometimes LLMs wrap JSON in markdown blocks ```json ... ```
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].strip()

                result = json.loads(content)
                return result
            except json.JSONDecodeError:
                logger.error(f"Failed to parse XAI response as JSON: {content}")
                return None

    except Exception as e:
        logger.error(f"XAI Error during sales inference: {e}")
        return None

def infer_sales_with_xai(product):
    """
    Wrapper to call XAI inference if eligible.
    Returns a list of sale events (dicts) or None.
    """
    # Check Eligibility
    stats = product.get('stats', {})
    current_rank = stats.get('current', [None]*4)[3]

    # 1. Skip if Rank is extremely high (Dead Inventory) to save tokens
    # Cutoff: 2,000,000
    if current_rank and current_rank > 2000000:
        return None

    history_text = format_history_for_xai(product, days=100)
    if not history_text:
        return None

    result = query_xai_sales_inference(history_text, product)

    if result and result.get('confidence') in ['High', 'Medium']:
        events = result.get('events', [])
        confirmed_sales = []
        for event in events:
            try:
                # Convert date string to datetime
                date_str = event.get('date')
                price = event.get('price')

                if date_str and price:
                    # Append time (noon) to be safe
                    dt = datetime.strptime(date_str, '%Y-%m-%d') + timedelta(hours=12)
                    price_cents = int(float(price) * 100)

                    confirmed_sales.append({
                        'event_timestamp': dt,
                        'inferred_sale_price_cents': price_cents
                    })
            except Exception as e:
                logger.warning(f"Error parsing XAI event {event}: {e}")

        if confirmed_sales:
            logger.info(f"XAI Rescued {len(confirmed_sales)} sales for ASIN {product.get('asin')}")
            return confirmed_sales

    return None
