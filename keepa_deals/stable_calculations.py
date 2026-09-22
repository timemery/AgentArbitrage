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

# `infer_sales_with_xai` is deliberately NOT imported here any more. The xAI sales
# rescue was removed from this module on 2026-09-16; see the note above
# `infer_sale_events` for the reasoning and AGENTS.md 7.1. Re-adding this import is
# how the rescue comes back by accident - it is pinned absent by
# tests/test_xai_rescue_excluded.py.

# Initialize cache and token manager at the module level
xai_cache = XaiCache()
xai_token_manager = XaiTokenManager()

# Keepa epoch is minutes from 2011-01-01
KEEPA_EPOCH = datetime(2011, 1, 1)

# THERE IS DELIBERATELY NO TIME THRESHOLD ON THE PRICE ASSOCIATION.
#
# A tolerance was proposed and then rejected on evidence, 2026-09-12 (owner decision).
# Measured on real Keepa history for the three ASINs of the 2026-09-11 diagnostic, the
# gap between an offer drop and the price point immediately PRECEDING it, across all 7
# confirmed sales, was:
#
#     3.0, 5.1, 10.2, 252.1, 389.6, 516.4, 2281.4 hours    (median 252.1h, max 95.1d)
#
# Bimodal, with nothing at all between 10h and 252h, and 0 of the 7 drops had no prior
# price point. A 240-hour threshold would have cut the distribution at its median and
# discarded the majority of real sales.
#
# The reason is that `csv[1]` / `csv[2]` are CHANGE-LOGS of the lowest New / Used offer
# price. A long gap means the lowest offer simply had not changed, which makes the
# distant point CORRECT rather than stale. Gap length does not measure staleness, so a
# time threshold is the wrong instrument. Do not add one.
#
# OPEN ITEM, not built here: if a stale-price guard is ever wanted, it needs continuity
# of the price series across the gap (evidence that the series was live and the value
# genuinely held, rather than absent), not gap length.

# Passthrough column carrying a matched price point's own timestamp through the
# `merge_asof` in `infer_sale_events`. Read back into each sale's `price_point`.
PRICE_POINT_TS = 'price_point_timestamp'


def _distinct_price_points(sale_events):
    """One price per DISTINCT change-log point, in first-seen order.

    `infer_sale_events` takes the last price point strictly before an offer drop at
    any distance (PR #340), so two drops with no price change between them are
    both priced by the SAME point. That association is correct, but it is one
    asking price counted twice, and in a month where every other price is distinct
    that pair used to win the mode uncontested (Dev_Logs 2026-09-22, 4 of 50 rows).

    Identity is the matched point's `(series, timestamp)`, never price equality:
    two separate points that happen to hold the same price are ordinary repricing
    and each counts. A sale with no recorded `price_point` (a hand-built event)
    counts as its own point, so a missing identity can never merge two sales.
    """
    seen = set()
    prices = []
    for index, sale in enumerate(sale_events):
        point = sale.get('price_point')
        key = point if isinstance(point, tuple) else ('unrecorded', index)
        if key in seen:
            continue
        seen.add(key)
        prices.append(sale['inferred_sale_price_cents'])
    return prices


# --- The peak-window New cap (Pricing Logic Version 3) -----------------------
#
# `List at` may not exceed the median, across the peak-season windows that fed
# it, of the lowest New offer in each window, plus this allowance. Owner decision
# 2026-09-22, sized on the audit: 15 of 50 worst-case rows capped, median $155.82.
#
# NEVER today's New price. The product buys at the trough and sells at the peak,
# so the New offer on screen now is the BUY side; capping a peak price with it
# compares two different points in the season. A row with no New price in any of
# its windows is left UNCAPPED and says so - there is no fallback.
PEAK_NEW_CAP_ALLOWANCE_CENTS = 399

# Outcomes recorded on every analysis as `peak_new_cap`.
NEW_CAP_APPLIED = 'applied'
NEW_CAP_NOT_NEEDED = 'not needed'
NEW_CAP_UNAVAILABLE = 'unavailable: no New price in the peak window'


def peak_window_new_floor(product, contributing_sales):
    """Lowest New offer price while the peak-season sales that set `List at` happened.

    Moved here from `audit_list_at_sources.py` (which now calls this) so the cap
    and the measurement it was sized on are one function.

    THE WINDOWS are the calendar months (year, month) that contain the sales that
    fed `List at` - plural, because a three-year history can hold the same peak
    month in two or three different years, and each is its own window with its
    own New price.

    READING A CHANGE-LOG, NOT A SAMPLE. `csv[1]` records a point only when the
    lowest New price CHANGES, so a window can contain zero points while a price
    was in force throughout it. The price in force during a window is therefore
    the last point before the window opens, carried forward, PLUS every point
    inside it - the same reasoning as having no time threshold on the price
    association (INFERRED_PRICE_LOGIC.md 2b.1). `carried` records when a floor
    came from such a point.

    BASIS: `csv[1]` is Keepa's NEW index, an item price with no shipping.
    """
    blank = {'floor_cents': None, 'median_window_floor_cents': None,
             'windows': [], 'window_count': 0, 'carried': False, 'points': 0}
    if not contributing_sales:
        return blank

    csv_data = product.get('csv') or []
    history = csv_data[1] if len(csv_data) > 1 and isinstance(csv_data[1], list) \
        and len(csv_data[1]) > 1 else None
    if not history:
        return blank

    frame = pd.DataFrame(np.array(history).reshape(-1, 2),
                         columns=['timestamp', 'price_cents'])
    frame = _convert_ktm_to_datetime(frame)
    frame = frame[frame['price_cents'] > 0].sort_values('timestamp')
    if frame.empty:
        return blank

    periods = sorted({(pd.to_datetime(sale['event_timestamp']).year,
                       pd.to_datetime(sale['event_timestamp']).month)
                      for sale in contributing_sales})

    windows, floors, carried_any, points_seen = [], [], False, 0
    for year, month in periods:
        start = datetime(year, month, 1)
        end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)

        inside = frame[(frame['timestamp'] >= start) & (frame['timestamp'] < end)]
        prior = frame[frame['timestamp'] < start]

        candidates = list(inside['price_cents'])
        points_seen += len(candidates)
        carried = None
        if not prior.empty:
            carried = float(prior.iloc[-1]['price_cents'])
            candidates.append(carried)

        if not candidates:
            windows.append({'year': year, 'month': month, 'floor_cents': None,
                            'points_inside': 0, 'carried_cents': None})
            continue

        floor = float(min(candidates))
        if carried is not None and floor == carried and len(inside) == 0:
            carried_any = True
        floors.append(floor)
        windows.append({'year': year, 'month': month, 'floor_cents': floor,
                        'points_inside': len(inside), 'carried_cents': carried})

    if not floors:
        return dict(blank, windows=windows, window_count=len(windows))

    ordered = sorted(floors)
    return {
        'floor_cents': ordered[0],
        'median_window_floor_cents': float(np.median(ordered)),
        'windows': windows,
        'window_count': len(windows),
        'carried': carried_any,
        'points': points_seen,
    }


def _query_xai_for_reasonableness(title, category, season, price_usd, api_key, binding="N/A", page_count="N/A", image_url="N/A", rank_info="N/A", trend_info="N/A", avg_3yr_usd="N/A"):
    """
    Queries the XAI API to act as a reasonableness check for a calculated price,
    now with caching and token management.

    Returns True (reasonable), False (rejected) or None - UNVERIFIABLE: no API
    key, the daily cap was reached, or the call failed. None FAILS CLOSED (Trello
    #144, Pricing Logic Version 3): the caller invalidates the price and the row is
    left stale for the repair sweep to retry. It used to return True on all three
    paths, so a missing key or an xAI outage passed every price unchecked and
    stamped it current.
    """
    if not api_key:
        logging.warning("XAI_TOKEN not provided. Cannot perform reasonableness check for '%s'. Price is UNVERIFIABLE - failing closed.", title)
        return None

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
        logging.warning(f"XAI daily limit reached. Cannot perform reasonableness check for '{title}'. Price is UNVERIFIABLE - failing closed.")
        return None

    # 4. If permission granted, proceed with the API call
    # NOTE: We explicitly explain that the "3-Year Average Price" includes off-season lows and that seasonal items
    # (especially Textbooks) can validly have peak prices 200-400% higher than the average.
    # This context is critical to prevent the AI from falsely rejecting valid peak season prices.
    prompt = f"""
    You are an expert Arbitrage Advisor.
    CONTEXT: The "3-Year Average Price" is a simple mean of all sales, including off-season lows.
    For seasonal items (especially Textbooks), the "Peak Season" price can validly be 200-400% higher than the average.
    However, any used book price over $500 should face intense scrutiny and is highly likely unreasonable unless it is a known textbook or rare collectible, and prices over $1,000 are almost always unreasonable.

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
        # UNVERIFIABLE, not reasonable: fail closed (Trello #144). Not cached, so
        # the next attempt asks again.
        return None

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

# --- THE XAI SALES RESCUE WAS REMOVED HERE (2026-09-16) -----------------------
#
# Until this date `infer_sale_events` called `infer_sales_with_xai` on BOTH of its
# zero-sale branches: "no offer drop anywhere" and "offer drops that all failed
# correlation". A model-asserted sale was then returned VERBATIM, and the deal
# proceeded to pricing as though a real sale had been observed.
#
# Why it had to go (owner decision, 2026-09-16, Trello #141):
#
#   1. It is not a true inferred sale. AGENTS.md 7.1 permits `List at` and
#      `1yr. Avg.` to rest ONLY on an offer drop correlated with a rank drop. A
#      rescued price is a number a language model produced; nothing checks that it
#      ever appeared in the Keepa history at all.
#   2. It returned BEFORE the IQR filter below, and before the `price <= 0` and NaN
#      guards in the correlation loop. Its only price check was a truthiness test
#      (`if date_str and price`), which admits a negative price.
#   3. The price-association fix of 2026-09-12 (PR #340) never applied to it. A
#      rescued price is not read from `csv[1]`/`csv[2]`, so it cannot be associated
#      correctly or incorrectly - it is simply asserted.
#   4. In production, 2026-08-28 to 2026-09-08, every single rescue returned
#      exactly ONE sale. At n=1 the Sparse Sales Rescue takes the median of one
#      number, so `List at` and `1yr. Avg.` became the same single model-asserted
#      figure - and because a rescued event always fell inside 365 days, such rows
#      always cleared the dashboard's data-completeness filter. Rescued deals were
#      precisely the ones subscribers saw.
#   5. On the second branch it corrupted `Deal Trust`. Returning one model event
#      over `total_offer_drops_count` read as 1/N - a positive confidence score
#      derived from offer drops that had just failed to correlate with anything.
#
# What happens instead: zero inferred sales is now a final answer on both branches.
# `analyze_sales_performance` returns `peak_price_mode_cents = -1` and
# `inferred_sale_count = 0`, `get_1yr_avg_sale_price` returns None, and the deal is
# PERSISTED with NULL `List_at` and NULL `1yr_Avg` (AGENTS.md 7.8 - it is not
# rejected, which would re-create the 20-token re-fetch loop). `/api/deals` filters
# it out of the dashboard. `Inferred_Sale_Count` reads 0, meaning "computed, none
# found", which is a different answer from NULL ("never computed").
#
# `keepa_deals/xai_sales_inference.py` still exists and still works; nothing in the
# live pipeline calls it. Do not re-wire it here.
# ------------------------------------------------------------------------------

def infer_sale_events(product):
    """
    Analyzes historical product data to infer sale events using a search-window logic.
    A sale is inferred when a drop in used or new offer count is followed by a drop
    in sales rank within a defined time window.

    Zero confirmed sales is a FINAL answer on both zero-sale branches. There is no
    xAI rescue - see the note directly above this function.
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
            # No offer drop anywhere in the 3-year window. Zero inferred sales is the
            # final answer. The xAI rescue that used to run here was removed on
            # 2026-09-16 - see the note above this function.
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

                # --- Price association ---
                # Take the last price point STRICTLY BEFORE the offer drop: the price
                # in force at the moment the copy sold. csv[1] / csv[2] hold the
                # LOWEST New / Used offer price, not any one copy's price, so the
                # point AT or AFTER a drop is the next cheapest listing's asking
                # price - a copy that did not sell. `direction='nearest'` had no
                # tolerance and no tie-break and recorded exactly that on 5 of 7
                # live sales (2026-09-11: $124.85 stored as $1,000.00, $49.95 as
                # $499.95, $328.19 as $625.59).
                #
                # `allow_exact_matches=False` matters as much as the direction, and
                # the box measurement showed it doing the real work: 4 of the 7 live
                # sales had a price point sharing the EXACT minute of the offer drop.
                # Keepa stamps the offer-count drop and the price step-up together,
                # so a zero-distance match is the common case, not the edge.
                #
                # There is NO `tolerance` here, on purpose. See the note at the top of
                # this module: the series is a change-log, so a months-old point means
                # the price had not changed and is the correct answer. A 240-hour
                # threshold would have discarded 4 of those same 7 real sales.
                #
                # The matched point's own timestamp is carried through the merge
                # (PRICE_POINT_TS) so each sale records WHICH change-log point priced
                # it. Two offer drops with no price change between them match the
                # same point; that is correct association, but it is one asking
                # price, and the peak-season mode must count it once. See
                # `_distinct_price_points`.
                matched = pd.merge_asof(
                    pd.DataFrame([drop]),
                    price_df_to_use.assign(**{PRICE_POINT_TS: price_df_to_use['timestamp']}),
                    on='timestamp',
                    direction='backward',
                    allow_exact_matches=False,
                )
                price_at_sale_time = matched['price_cents'].iloc[0]
                price_point_ts = matched[PRICE_POINT_TS].iloc[0]

                # NaN is what a backward match returns when the drop precedes every
                # price point in the series, and `NaN <= 0` is False, so the guard
                # below cannot catch it on its own. A NaN reaching confirmed_sales
                # would poison the IQR bounds, the mean and the mode for the whole
                # ASIN. This is the only case in which a confirmed drop loses its
                # price; it was 0 of 7 on the live sample.
                if pd.isna(price_at_sale_time):
                    logger.debug(
                        f"ASIN {asin}: Ignoring inferred sale at {start_time} because "
                        f"no {drop['offer_type']} price point exists before it."
                    )
                    continue

                if price_at_sale_time <= 0:
                    logger.debug(f"ASIN {asin}: Ignoring inferred sale at {start_time} because its associated price was invalid ({price_at_sale_time}).")
                    continue
                
                confirmed_sales.append({
                    'event_timestamp': start_time,
                    'inferred_sale_price_cents': price_at_sale_time,
                    # Identity of the change-log point that priced this sale:
                    # (series, point timestamp). The series is the frame actually
                    # used, which is Used when a New drop has no New history.
                    'price_point': (
                        'New' if price_df_to_use is df_new_price else 'Used',
                        price_point_ts,
                    ),
                })
        
        if not confirmed_sales:
            # Offer drops existed and NONE of them correlated with a rank drop. Zero
            # inferred sales is the final answer. The xAI rescue that used to run here
            # was removed on 2026-09-16 - see the note above this function.
            #
            # `total_offer_drops_count` is returned unchanged, so those drops still
            # count in the `Deal Trust` denominator and the column reads a truthful
            # 0%. The rescue used to return its own event over this same denominator,
            # which read 1/N - a positive confidence score built from drops that had
            # just failed correlation.
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

    # Increased from 1 to 3 to route "fragile" deals (1-2 sales) to the Sparse
    # Sales Rescue below, which uses the median of those TRUE inferred sales and
    # skips the XAI check to prevent false negatives on thin context.
    # (The original comment here described the avg365 "Silver Standard" fallback,
    # which was deleted from this module in March 2026 and no longer exists.)
    MIN_SALES_FOR_ANALYSIS = 3

    # The sane inferred-sale count for this product, as this function sees it.
    # Always post-IQR: there is one path now. (This used to add "raw on the
    # XAI-rescue path, which returns before sanitisation" - that path was removed
    # on 2026-09-16, see the note above `infer_sale_events`.) Returned on EVERY
    # branch so the caller can persist it, including the zero-sale rejection -
    # 0 is a real reading and must be distinguishable from a NULL, which means
    # "never computed".
    inferred_sale_count = len(sale_events) if sale_events else 0

    # Initialize variables with defaults
    peak_price_mode_cents = -1
    peak_season_str = '-'
    trough_season_str = '-'
    expected_trough_price_cents = -1
    price_source = 'Inferred Sales'
    # The calendar month the price was set in (None on the Sparse branch, which
    # has no peak month), and the sales that fed the price. Both are read by the
    # peak-window New cap and the Amazon ceiling below.
    peak_month = None
    contributing_sales = list(sale_events or [])

    # --- Check Data Sufficiency ---
    if not sale_events or len(sale_events) < MIN_SALES_FOR_ANALYSIS:
        logger.debug(f"ASIN {asin}: Not enough sale events ({len(sale_events)}) for robust performance analysis.")

        # --- KEEPA STATS FALLBACK REMOVED (MARCH 2026) ---
        # PREVIOUS LOGIC: The system used to fall back to calculating the minimum of Keepa's
        # 90-day and 365-day average prices for standard Used conditions (the "Silver Standard")
        # when it found fewer than 3 inferred sales.
        #
        # REASON FOR REMOVAL: The user observed that this fallback logic—while safely preventing
        # astronomical profits via min()—still essentially relied on *listing prices* rather than
        # *true inferred sale prices*. This tactic, originally designed to increase the volume of
        # deals found, compromised the core promise of only providing "true deals."
        #
        # NEW POLICY: We now STRICTLY rely on inferred sale prices (derived from offer drops
        # correlating with rank drops) to calculate profits. We only provide true deals that
        # can be relied on by subscribers.
        #
        # Note: If there are 1 or 2 inferred sales, we still utilize them via "Sparse Sales Rescue",
        # because those ARE true inferred sales, just limited in quantity.
        # See Documentation/INFERRED_PRICE_LOGIC.md for historical details.
        # -------------------------------------------------

        if sale_events:
            # Sparse Sales Rescue (1-2 sales): We have valid inferred sales, so we use them.
            prices = [s['inferred_sale_price_cents'] for s in sale_events]
            peak_price_mode_cents = float(np.median(prices))  # Use Median for safety on small sample
            price_source = 'Inferred Sales (Sparse)'
            logger.info(f"ASIN {asin}: Found {len(sale_events)} sparse inferred sales. Rescued using Median: ${peak_price_mode_cents/100:.2f}")
        else:
            logger.warning(f"ASIN {asin}: No inferred sales found. Deal rejected to maintain strict inferred-only policy.")
            # If no sales exist, we return early as -1 price, triggering exclusion.
            return {'peak_price_mode_cents': -1, 'peak_season': '-', 'trough_season': '-',
                    'price_source': 'None', 'inferred_sale_count': inferred_sale_count}

    else:
        # --- Normal Logic (Sufficient Sale Events) ---
        df = pd.DataFrame(sale_events)
        df['event_timestamp'] = pd.to_datetime(df['event_timestamp'])
        df['month'] = df['event_timestamp'].dt.month

        # --- Peak/Trough Season Identification ---
        monthly_stats = df.groupby('month')['inferred_sale_price_cents'].agg(['median', 'count'])

        if len(monthly_stats) < 1:
             return {'peak_price_mode_cents': -1, 'peak_season': '-', 'trough_season': '-',
                     'inferred_sale_count': inferred_sale_count}

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
            return {'peak_price_mode_cents': -1, 'peak_season': peak_season_str,
                    'trough_season': trough_season_str,
                    'inferred_sale_count': inferred_sale_count}
        else:
            # Normal calculation, over DISTINCT price points, not sale events: a
            # change-log point that priced two sales is one asking price and
            # counts once in both the mode and the median fallback. See
            # `_distinct_price_points`.
            peak_month = int(peak_month)
            peak_point_prices = _distinct_price_points(
                [sale for sale in sale_events
                 if pd.to_datetime(sale['event_timestamp']).month == peak_month])
            peak_sales = [sale for sale in sale_events
                          if pd.to_datetime(sale['event_timestamp']).month == peak_month]
            mode_result = st.mode(peak_point_prices)
            if mode_result.count > 1:
                peak_price_mode_cents = float(mode_result.mode)
                contributing_sales = [sale for sale in peak_sales
                                      if float(sale['inferred_sale_price_cents'])
                                      == peak_price_mode_cents]
                logger.info(f"ASIN {asin}: Calculated peak price mode: {peak_price_mode_cents/100:.2f} (held by {mode_result.count} distinct price points).")
            else:
                peak_price_mode_cents = float(np.median(peak_point_prices))
                contributing_sales = peak_sales
                logger.info(f"ASIN {asin}: No distinct mode found. Falling back to peak season median price: {peak_price_mode_cents/100:.2f}.")

    # --- Peak-window New cap (Pricing Logic Version 3) ---
    # See PEAK_NEW_CAP_ALLOWANCE_CENTS. Measured in the peak-season windows that fed
    # the price, never today: today's New offer is the buy side.
    new_floor = peak_window_new_floor(product, contributing_sales)
    peak_new_cap_cents = None
    if new_floor['median_window_floor_cents'] is None:
        peak_new_cap = NEW_CAP_UNAVAILABLE
        logger.info(f"ASIN {asin}: Peak-window New cap unavailable (no New price in the peak window). List at left uncapped.")
    else:
        peak_new_cap_cents = new_floor['median_window_floor_cents'] + PEAK_NEW_CAP_ALLOWANCE_CENTS
        if peak_price_mode_cents > peak_new_cap_cents:
            logger.info(f"ASIN {asin}: List at ${peak_price_mode_cents/100:.2f} exceeds the peak-window New cap ${peak_new_cap_cents/100:.2f}. Capping.")
            peak_price_mode_cents = peak_new_cap_cents
            peak_new_cap = NEW_CAP_APPLIED
        else:
            peak_new_cap = NEW_CAP_NOT_NEEDED

    # --- Amazon Ceiling Logic ---
    stats = product.get('stats', {})

    # Extract Amazon prices (New)
    amz_current = stats.get('current', [None] * 2)[0] # stats.current[0]
    amz_180_avg = stats.get('avg180', []) # stats.avg180[0]
    amz_180 = amz_180_avg[0] if amz_180_avg else None
    amz_365_avg = stats.get('avg365', []) # stats.avg365[0]
    amz_365 = amz_365_avg[0] if amz_365_avg else None

    # The CURRENT reading is a single price taken today. It bounds a peak-season
    # price only when today IS the peak month; otherwise it is a trough-time
    # price, the buy side (Pricing Logic Version 3). Both trailing averages stay:
    # they are the only Amazon rail for books Amazon stocks intermittently, and
    # they clip downward. The Sparse branch has no peak month, so it never uses
    # the current reading.
    current_in_peak = peak_month is not None and datetime.now().month == peak_month

    valid_amz_prices = []
    if current_in_peak and amz_current and amz_current > 0: valid_amz_prices.append(amz_current)
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

    # --- Suspiciously High Fallback Check ---
    is_suspiciously_high = False

    # HARD CEILING SAFETY CHECK: Any calculated price > $1500 is automatically rejected without AI check
    # to prevent astronomical fake profits (e.g. $4000) from polluting the dashboard.
    is_absurdly_high = False
    if peak_price_mode_cents > 150000:  # > $1500.00
        is_absurdly_high = True
        logger.warning(f"ASIN {asin}: Calculated List Price ${peak_price_mode_cents/100:.2f} exceeds absolute hard ceiling of $1500. Rejecting automatically.")
        peak_price_mode_cents = -1

    # We now apply the 3x ratio check to ALL price sources, not just fallbacks.
    # Inferred Sales with sparse points can also mathematically skew and require AI scrutiny.
    current_used_cents = -1
    current_stats = stats.get('current', [])
    # Index 2 is Used
    if len(current_stats) > 2 and current_stats[2] is not None:
        current_used_cents = current_stats[2]

    if current_used_cents > 0 and not is_absurdly_high:
        ratio = peak_price_mode_cents / current_used_cents
        if ratio > 3.0: # Threshold: >300% markup implies a likely outlier/mismatch
            is_suspiciously_high = True
            logger.warning(f"ASIN {asin}: Calculated List price ${peak_price_mode_cents/100:.2f} is suspiciously high (>3x current used ${current_used_cents/100:.2f}, Ratio: {ratio:.1f}x). Forcing AI Reasonableness Check.")

    if is_absurdly_high:
        logger.info(f"ASIN {asin}: Price is absurdly high. Skipping AI Reasonableness Check and rejecting.")
        is_reasonable = False
    elif is_capped_by_ceiling:
        logger.info(f"ASIN {asin}: Price is capped by Amazon Ceiling (Safe). Skipping AI Reasonableness Check.")
        is_reasonable = True
    elif price_source == 'Inferred Sales (Sparse)' and not is_suspiciously_high:
        # The 'Keepa Stats Fallback' half of this condition was removed on
        # 2026-09-11 (audit B-6): get_1yr_avg_sale_price no longer produces that
        # source, and analyze_sales_performance never set it. Only the sparse
        # half remains, and it is unchanged - 1-2 inferred sales are TRUE sales
        # with thin context, which is why the check is skipped for them
        # (AGENTS.md 7.8, Sparse Sales Rescue).
        logger.info(f"ASIN {asin}: Price Source is '{price_source}'. Skipping AI Reasonableness Check to prevent false negatives due to insufficient context.")
        is_reasonable = True
    else:
        is_reasonable = _query_xai_for_reasonableness(
            title, category, peak_season_str, peak_price_mode_cents / 100.0, xai_api_key,
            binding=binding, page_count=page_count, image_url=image_url, rank_info=rank_info,
            trend_info=trend_info, avg_3yr_usd=avg_3yr_usd
        )

    price_unverified = is_reasonable is None
    if price_unverified:
        # FAIL CLOSED (Trello #144). The check could not run - daily cap or an xAI
        # error - so the price is neither accepted nor rejected: it is withheld.
        # `price_unverified` tells `_process_single_deal` not to stamp the current
        # Pricing Logic Version, so the repair sweep retries the row.
        logger.warning(f"ASIN {asin}: XAI check UNVERIFIABLE. Price ${peak_price_mode_cents/100:.2f} withheld for '{title}'; row left stale for a retry.")
        peak_price_mode_cents = -1
    elif not is_reasonable:
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
        'inferred_sale_count': inferred_sale_count,
        'peak_new_cap': peak_new_cap,
        'peak_new_cap_cents': peak_new_cap_cents,
        'price_unverified': price_unverified,
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
        return {'List at': round(price_cents / 100.0, 2)}
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
        return {'Expected Trough Price': round(price_cents / 100.0, 2)}
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
