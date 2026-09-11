#!/usr/bin/env python3
"""
diagnose_inferred_sales.py

Read-only diagnostic for ONE ASIN. Answers the question the stored row cannot:
where did this deal's inferred sale prices actually come from?

Written for ASIN 1429097078, whose stored `1yr_Avg` and `List_at` are both 699.11
on a book currently listing used at $28.99. Two mechanisms could produce that, and
they have different fixes:

  (i)  A real offer drop with a WRONG PRICE ATTACHED, because the matched price
       point is far away in time. `infer_sale_events` associates a price using
       `pandas.merge_asof(direction='nearest')` with NO tolerance, so the price can
       come from a history point arbitrarily distant, and from the New series
       rather than the Used one when a New offer drop was the trigger. The time gap
       and the source series columns distinguish this case.

  (ia) THE LEFTOVER ASKING PRICE. The same defect with a near-zero time gap, and
       the more likely one. `csv[1]` and `csv[2]` hold the LOWEST New / Used offer
       price, not the price of any particular copy. When the cheapest copy sells,
       the series does not record what it sold for - it steps UP to whatever the
       next cheapest listing asks, at essentially the same timestamp as the
       offer-count drop that marks the sale. `direction='nearest'` has no tolerance
       and no tie-break, so it can land on the point AT or AFTER the drop and store
       the asking price of a copy that did NOT sell. The true sale price is then
       the point immediately BEFORE the drop.

       This is what the round numbers on the box look like: of 46 deals with
       `1yr_Avg = List_at` and $50+ profit, three carry exactly $499.95 and others
       exactly $1,000.00, $250.00, $200.00 and $150.00. Those are prices a seller
       typed into a listing, not prices anything transacted at. The PRICE STEP-UP
       TEST section tests this sale by sale.

  (ii) An xAI-rescued "hidden sale". When the algorithmic pass confirms nothing,
       `infer_sale_events` returns the model's events verbatim, BEFORE the IQR
       outlier filter. If the price history never held the stored value, the number
       was invented. This diagnostic prints whether the history ever held it.

WHAT IT WILL NOT DO
-------------------
  * It does not call xAI. This is the reason it re-implements the correlation loop
    instead of calling `infer_sale_events` directly: that function calls
    `infer_sales_with_xai` on both of its zero-sale branches, which would spend xAI
    budget and, worse, would hide case (i) behind case (ii)'s output.
  * It does not write any cache. `XaiCache` and `XaiTokenManager` only read on
    construction, so importing `stable_calculations` is safe; nothing here calls a
    method that persists.
  * It does not open, read or write deals.db. The stored price to compare against is
    passed in with --stored-price rather than looked up.

KEEP IN SYNC: the correlation loop below mirrors `infer_sale_events`
(`keepa_deals/stable_calculations.py`) - the 3-year window, the 240-hour
confirmation window, the 30-day sparse lookahead, the 72-hour near-miss window, the
New-vs-Used price series choice, the `price <= 0` guard and the symmetrical IQR.
If that function changes, change this too or its output becomes a lie. The shared
pieces (KEEPA_EPOCH, the timestamp conversion) are imported rather than copied.

USAGE
-----
Run from the application root, with KEEPA_API_KEY available (it is read from .env
via python-dotenv, same as the worker).

    sudo -u www-data venv/bin/python diagnose_inferred_sales.py 1429097078 \
        --stored-price 699.11

DIAGNOSIS ONLY. Nothing here changes the pricing code, and nothing here should be
read as a decision to change it.

Cost: one /product call for one ASIN with the heavy path's exact parameters
(days=365, history=1, offers=20) - the Smart Ingestor budgets ~20 tokens for this.
The real figure is printed at the end of the run.
"""

import argparse
import os
import sys
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from keepa_deals.keepa_api import fetch_product_batch
# Imported, not copied, so the epoch and the conversion cannot drift from production.
# AGENTS.md 1: the Keepa epoch is 2011-01-01. Never 2000-01-01.
from keepa_deals.stable_calculations import KEEPA_EPOCH, _convert_ktm_to_datetime

# Mirrors of the production constants. Named here so the printout can state them.
HISTORY_WINDOW_DAYS = 1095      # stable_calculations.py: timedelta(days=1095)
CONFIRM_WINDOW_HOURS = 240      # stable_calculations.py: timedelta(hours=240)
SPARSE_LOOKAHEAD_DAYS = 30      # stable_calculations.py: timedelta(days=30)
NEAR_MISS_HOURS = 72            # stable_calculations.py: timedelta(hours=72)
MIN_SALES_FOR_ANALYSIS = 3      # stable_calculations.py: MIN_SALES_FOR_ANALYSIS


def _rule(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


def _money(cents):
    if cents is None:
        return "-"
    try:
        return "${:,.2f}".format(float(cents) / 100.0)
    except (TypeError, ValueError):
        return str(cents)


def _to_df(hist, col_name):
    """Keepa history is a flat [time, value, time, value, ...] array."""
    if not hist or not isinstance(hist, list) or len(hist) < 2:
        return None
    arr = np.array(hist)
    if len(arr) % 2 != 0:
        arr = arr[:-1]
    df = pd.DataFrame(arr.reshape(-1, 2), columns=['timestamp', col_name])
    return _convert_ktm_to_datetime(df)


def fetch(asin, api_key):
    """One /product call, with the heavy path's exact parameters."""
    _rule("FETCH")
    print("  Calling fetch_product_batch(api_key, ['{}'], days=365, history=1, "
          "offers=20)".format(asin))
    print("  This is the same call smart_ingestor.py:550 makes on the heavy path.")
    resp, api_info, tokens_consumed, tokens_left = fetch_product_batch(
        api_key, [asin], days=365, history=1, offers=20
    )
    if api_info and api_info.get('error_status_code'):
        print("  FAILED: Keepa returned {}".format(api_info['error_status_code']))
        return None, tokens_consumed, tokens_left
    if not resp or not resp.get('products'):
        print("  FAILED: Keepa returned no products for {}.".format(asin))
        return None, tokens_consumed, tokens_left
    product = resp['products'][0]
    print("  OK. Title: {}".format(product.get('title', 'N/A')))
    print("  Tokens consumed by this call: {}".format(tokens_consumed))
    print("  Tokens left on the account:   {}".format(tokens_left))
    return product, tokens_consumed, tokens_left


def describe_history(product):
    _rule("HISTORY AVAILABILITY")
    csv_data = product.get('csv') or []
    if not isinstance(csv_data, list) or len(csv_data) < 13:
        print("  csv is missing or shorter than 13 entries ({}). infer_sale_events "
              "returns ([], 0) for this product and every price is NULL."
              .format(len(csv_data) if isinstance(csv_data, list) else type(csv_data)))
        return None
    labels = {1: 'csv[1]  New price', 2: 'csv[2]  Used price',
              3: 'csv[3]  Sales rank', 11: 'csv[11] New offer count',
              12: 'csv[12] Used offer count'}
    for idx in sorted(labels):
        series = csv_data[idx] if len(csv_data) > idx else None
        n = len(series) // 2 if isinstance(series, list) else 0
        print("  {:<28} {:>6} points".format(labels[idx], n))
    print()
    print("  Keepa epoch in use: {} (AGENTS.md 1)".format(KEEPA_EPOCH.date()))
    return csv_data


def find_offer_drops(csv_data, window_start):
    """Mirror of the offer-drop detection in infer_sale_events."""
    _rule("STAGE 1a - OFFER DROPS (the sale triggers)")
    print("  Window: last {} days, from {:%Y-%m-%d}."
          .format(HISTORY_WINDOW_DAYS, window_start))
    frames = []
    total = 0
    for idx, kind in ((12, 'Used'), (11, 'New')):
        hist = csv_data[idx] if len(csv_data) > idx else None
        df = _to_df(hist, 'offer_count')
        if df is None:
            print("  {:<5} csv[{}]: no usable history.".format(kind, idx))
            continue
        df = df[df['timestamp'] >= window_start].copy()
        df['offer_diff'] = df['offer_count'].diff()
        drops = df[df['offer_diff'] < 0].copy()
        print("  {:<5} csv[{}]: {} points in window, {} negative steps."
              .format(kind, idx, len(df), len(drops)))
        if not drops.empty:
            drops['offer_type'] = kind
            frames.append(drops)
            total += len(drops)
    if not frames:
        print()
        print("  ZERO offer drops. In production this is the branch at "
              "stable_calculations.py:236-243 that calls xAI and returns its events "
              "with total_offer_drops = 0, which also makes Deal Trust '-'.")
        return pd.DataFrame(), 0
    merged = pd.concat(frames).sort_values('timestamp').reset_index(drop=True)
    print()
    print("  TOTAL offer drops (the Deal Trust denominator): {}".format(total))
    return merged, total


def confirm_sales(offer_drops, csv_data, window_start):
    """Mirror of the rank-drop confirmation and the price association."""
    _rule("STAGE 1b - RANK CONFIRMATION AND PRICE ASSOCIATION")
    df_rank = _to_df(csv_data[3] if len(csv_data) > 3 else None, 'rank')
    if df_rank is None:
        print("  No rank history. No sale can be confirmed.")
        return [], []
    df_rank = df_rank[df_rank['timestamp'] >= window_start]
    df_rank = df_rank.sort_values('timestamp').reset_index(drop=True)
    df_rank['rank_diff'] = df_rank['rank'].diff()

    df_used_price = _to_df(csv_data[2] if len(csv_data) > 2 else None, 'price_cents')
    df_new_price = _to_df(csv_data[1] if len(csv_data) > 1 else None, 'price_cents')

    confirm_window = timedelta(hours=CONFIRM_WINDOW_HOURS)
    confirmed = []
    rejected = []

    print("  Confirmation window {}h, sparse lookahead {}d, near-miss {}h."
          .format(CONFIRM_WINDOW_HOURS, SPARSE_LOOKAHEAD_DAYS, NEAR_MISS_HOURS))
    print()

    for _, drop in offer_drops.iterrows():
        start_time = drop['timestamp']
        end_time = start_time + confirm_window
        how = None

        in_window = df_rank[(df_rank['timestamp'] >= start_time)
                            & (df_rank['timestamp'] <= end_time)]
        if not in_window.empty and (in_window['rank_diff'] < 0).any():
            how = 'direct rank drop within {}h'.format(CONFIRM_WINDOW_HOURS)

        if how is None:
            before = df_rank[df_rank['timestamp'] <= start_time]
            after = df_rank[(df_rank['timestamp'] > start_time)
                            & (df_rank['timestamp']
                               <= start_time + timedelta(days=SPARSE_LOOKAHEAD_DAYS))]
            if not before.empty and not after.empty:
                last_rank = before.iloc[-1]['rank']
                next_rank = after.iloc[0]['rank']
                if next_rank < last_rank:
                    gap_days = (after.iloc[0]['timestamp'] - start_time).days
                    how = ('SPARSE LOOKAHEAD: rank {:,.0f} -> {:,.0f} over {} days'
                           .format(last_rank, next_rank, gap_days))

        if how is None:
            nm = df_rank[(df_rank['timestamp'] > end_time)
                         & (df_rank['timestamp']
                            <= end_time + timedelta(hours=NEAR_MISS_HOURS))]
            reason = 'no rank drop'
            if not nm.empty and (nm['rank_diff'] < 0).any():
                miss = nm[nm['rank_diff'] < 0].iloc[0]['timestamp']
                reason = ('near miss, rank dropped {:.1f}h after the window'
                          .format((miss - end_time).total_seconds() / 3600))
            rejected.append((start_time, drop['offer_type'], reason))
            continue

        # --- Price association. This is where case (i) is visible. ---
        use_new = (drop['offer_type'] == 'New' and df_new_price is not None)
        price_df = df_new_price if use_new else df_used_price
        series_name = 'csv[1] New' if use_new else 'csv[2] Used'
        if price_df is None:
            rejected.append((start_time, drop['offer_type'],
                             'confirmed, but no price series available'))
            continue

        matched = pd.merge_asof(pd.DataFrame([drop]), price_df,
                                on='timestamp', direction='nearest')
        price_cents = matched['price_cents'].iloc[0]

        # merge_asof reports only the value, so re-find the point it chose in order
        # to report WHICH point and HOW FAR AWAY it was. direction='nearest' with no
        # tolerance means this can be any distance at all.
        deltas = (price_df['timestamp'] - start_time).abs()
        chosen = price_df.loc[deltas.idxmin()]
        gap_days = abs((chosen['timestamp'] - start_time).total_seconds()) / 86400.0

        # --- The step-up test. ---
        # csv[1] and csv[2] are the LOWEST New / Used offer price, not a per-copy
        # price. So when the cheapest copy sells, the series does not record what
        # that copy sold for - it steps UP to whatever the next cheapest listing
        # asks, at essentially the same timestamp as the offer-count drop that
        # marks the sale. direction='nearest' has no tie-break and no tolerance, so
        # it can land on the point AT or AFTER the drop: the leftover asking price
        # of a copy that did NOT sell.
        #
        # Signature: merge_asof chose the at/after side, the recorded price equals
        # the after price, and after >> before. The true sale price in that case is
        # the BEFORE price.
        before_slice = price_df[price_df['timestamp'] < start_time]
        after_slice = price_df[price_df['timestamp'] >= start_time]
        price_before = before_slice.iloc[-1] if not before_slice.empty else None
        price_after = after_slice.iloc[0] if not after_slice.empty else None
        chose_at_or_after = bool(chosen['timestamp'] >= start_time)

        if price_cents <= 0:
            rejected.append((start_time, drop['offer_type'],
                             'confirmed, but matched price was {} (<= 0), discarded'
                             .format(price_cents)))
            continue

        confirmed.append({
            'event_timestamp': start_time,
            'inferred_sale_price_cents': price_cents,
            'offer_type': drop['offer_type'],
            'series': series_name,
            'how': how,
            'price_point_timestamp': chosen['timestamp'],
            'gap_days': gap_days,
            'price_before_cents': None if price_before is None
                                  else price_before['price_cents'],
            'price_before_timestamp': None if price_before is None
                                      else price_before['timestamp'],
            'price_after_cents': None if price_after is None
                                 else price_after['price_cents'],
            'price_after_timestamp': None if price_after is None
                                     else price_after['timestamp'],
            'chose_at_or_after': chose_at_or_after,
        })

    print("  CONFIRMED SALES: {}".format(len(confirmed)))
    if confirmed:
        print()
        print("  {:<17} {:>10} {:<11} {:>9}  {}".format(
            "sale timestamp", "price", "from", "gap (d)", "confirmed by"))
        print("  " + "-" * 74)
        for c in confirmed:
            flag = '  <-- SUSPECT' if c['gap_days'] >= 7 else ''
            print("  {:%Y-%m-%d %H:%M} {:>10} {:<11} {:>9.1f}  {}{}".format(
                c['event_timestamp'], _money(c['inferred_sale_price_cents']),
                c['series'], c['gap_days'], c['how'], flag))
        print()
        print("  'gap (d)' is the distance between the offer drop and the price point")
        print("  merge_asof(direction='nearest') attached to it. There is no")
        print("  tolerance in production, so a large gap here means the price is not")
        print("  contemporaneous with the sale - that is mechanism (i).")
    if rejected:
        print()
        print("  NOT CONFIRMED: {}".format(len(rejected)))
        for ts, kind, reason in rejected[:40]:
            print("    {:%Y-%m-%d %H:%M}  {:<5} {}".format(ts, kind, reason))
        if len(rejected) > 40:
            print("    ... and {} more".format(len(rejected) - 40))
    else:
        print()
        print("  Every offer drop was confirmed.")
    if confirmed:
        _print_step_up_analysis(confirmed)
    return confirmed, rejected



# Ratio at which an after/before jump stops looking like ordinary repricing and
# starts looking like the series stepping up to the next listing in the stack.
STEP_UP_RATIO = 1.5


def _print_step_up_analysis(confirmed):
    """Test the leftover-asking-price hypothesis, sale by sale.

    csv[1] and csv[2] hold the LOWEST New / Used offer price, not the price of any
    particular copy. When the cheapest copy sells, the series does not record what
    it sold for - it steps UP to whatever the next cheapest listing asks, at
    essentially the moment of the offer-count drop that marks the sale.

    `merge_asof(direction='nearest')` has no tolerance and no tie-break rule, so on
    a drop whose neighbouring price points straddle it by similar distances it can
    land on the AFTER side and record the leftover asking price of a copy that did
    not sell. That inflates List at and 1yr Avg together, which is consistent with
    the round numbers seen on the box ($1,000.00, $499.95, $250.00, $200.00,
    $150.00) - those are asking prices someone typed, not prices anything sold at.

    In that case the true sale price is the BEFORE price.
    """
    print()
    print("-" * 78)
    print("  PRICE STEP-UP TEST (which side of the drop did merge_asof land on?)")
    print("-" * 78)
    print("  {:<17} {:>10} {:>10} {:>8}  {:<9} {:<8} {}".format(
        "sale timestamp", "before", "after", "jump", "picked", "recorded", ""))
    print("  " + "-" * 74)

    suspects = 0
    for c in confirmed:
        before = c.get('price_before_cents')
        after = c.get('price_after_cents')
        recorded = c['inferred_sale_price_cents']

        if before and after and before > 0:
            jump = "{:.1f}x".format(after / before)
        else:
            jump = "-"

        picked = 'at/after' if c.get('chose_at_or_after') else 'before'
        if after is not None and recorded == after:
            which = 'after'
        elif before is not None and recorded == before:
            which = 'before'
        else:
            which = 'other'

        is_suspect = (
            c.get('chose_at_or_after')
            and which == 'after'
            and before and after and before > 0
            and (after / before) >= STEP_UP_RATIO
        )
        if is_suspect:
            suspects += 1

        print("  {:%Y-%m-%d %H:%M} {:>10} {:>10} {:>8}  {:<9} {:<8} {}".format(
            c['event_timestamp'], _money(before), _money(after), jump,
            picked, which, '<-- STEP-UP SUSPECT' if is_suspect else ''))

    print()
    print("  'before' is the last price point strictly before the offer drop;")
    print("  'after' is the first at or after it, both from the same series")
    print("  merge_asof read. 'picked' is the side merge_asof landed on and")
    print("  'recorded' is which of the two it stored.")
    print()
    if suspects:
        print("  {} of {} sale(s) match the step-up signature: merge_asof took the"
              .format(suspects, len(confirmed)))
        print("  at/after point, stored it, and it is >= {}x the price immediately"
              .format(STEP_UP_RATIO))
        print("  before the drop. For those, the price the copy actually sold at is")
        print("  the 'before' column, and the stored value is the next listing's")
        print("  asking price.")
    else:
        print("  No sale matches the step-up signature. If the stored price is still")
        print("  wrong, the cause is elsewhere - check the gap column above for a")
        print("  price point that is simply far away in time.")


def sanitise(confirmed):
    """Mirror of the symmetrical IQR rejection."""
    _rule("STAGE 2 - IQR OUTLIER REJECTION")
    if not confirmed:
        print("  No confirmed sales. In production this is the branch at")
        print("  stable_calculations.py:315-322, which calls xAI and returns the")
        print("  model's events WITHOUT running this filter at all. If the stored")
        print("  price is not in the history (see below), that is mechanism (ii).")
        return []
    prices = [c['inferred_sale_price_cents'] for c in confirmed]
    q1, q3 = np.percentile(prices, 25), np.percentile(prices, 75)
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    print("  Q1 {}   Q3 {}   IQR {}".format(_money(q1), _money(q3), _money(iqr)))
    print("  Keep range: {} to {}".format(_money(lo), _money(hi)))
    sane = [c for c in confirmed if lo <= c['inferred_sale_price_cents'] <= hi]
    dropped = [c for c in confirmed if c not in sane]
    print("  Kept {} of {} sale events.".format(len(sane), len(confirmed)))
    for c in dropped:
        print("    TRIMMED {:%Y-%m-%d} {}".format(
            c['event_timestamp'], _money(c['inferred_sale_price_cents'])))
    if len(confirmed) <= 3:
        print()
        print("  NOTE: at n<=3 the IQR cannot trim anything meaningful, so this")
        print("  filter is not protecting the result.")
    return sane


def check_stored_price(csv_data, stored_price_usd):
    """Did the price history EVER hold the stored value? Separates (i) from (ii)."""
    _rule("DOES THE HISTORY EVER HOLD THE STORED PRICE?")
    if stored_price_usd is None:
        print("  No --stored-price given, skipping.")
        return
    target = int(round(stored_price_usd * 100))
    print("  Looking for exactly {} ({} cents) in the full price history."
          .format(_money(target), target))
    found_any = False
    for idx, label in ((2, 'csv[2] Used'), (1, 'csv[1] New')):
        df = _to_df(csv_data[idx] if len(csv_data) > idx else None, 'price_cents')
        if df is None:
            print("  {:<12}: no history.".format(label))
            continue
        hits = df[df['price_cents'] == target]
        if hits.empty:
            print("  {:<12}: NOT PRESENT in {} points.".format(label, len(df)))
            continue
        found_any = True
        print("  {:<12}: {} occurrences, first {:%Y-%m-%d}, last {:%Y-%m-%d}."
              .format(label, len(hits), hits.iloc[0]['timestamp'],
                      hits.iloc[-1]['timestamp']))
    print()
    if found_any:
        print("  The value IS a real historical listing price. The question is")
        print("  whether it was attached to a real sale - read the gap column above.")
    else:
        print("  The value is NOT anywhere in the price history. No merge_asof match")
        print("  could have produced it, which points at an xAI-invented event.")


def amazon_stats(product):
    _rule("AMAZON STATS AND THE CEILING")
    stats = product.get('stats') or {}
    cur = stats.get('current') or []
    a180 = stats.get('avg180') or []
    a365 = stats.get('avg365') or []

    def at(arr, i):
        return arr[i] if len(arr) > i and arr[i] is not None and arr[i] > 0 else None

    amz_now, amz_180, amz_365 = at(cur, 0), at(a180, 0), at(a365, 0)
    used_now = at(cur, 2)
    rank_now = cur[3] if len(cur) > 3 else None

    print("  Amazon current   stats.current[0] : {}".format(_money(amz_now)))
    print("  Amazon 180d avg  stats.avg180[0]  : {}".format(_money(amz_180)))
    print("  Amazon 365d avg  stats.avg365[0]  : {}".format(_money(amz_365)))
    print("  Used current     stats.current[2] : {}".format(_money(used_now)))
    print("  Sales rank       stats.current[3] : {}".format(rank_now))

    valid = [p for p in (amz_now, amz_180, amz_365) if p]
    if valid:
        ceiling = min(valid) * 0.90
        print()
        print("  Amazon ceiling = 90% of {} = {}"
              .format(_money(min(valid)), _money(ceiling)))
        print("  Any computed List at above that is clamped to it, and clamping also")
        print("  SKIPS the AI reasonableness check (stable_calculations.py:588).")
    else:
        print()
        print("  No valid Amazon price, so no ceiling is applied and the computed")
        print("  price passes through uncapped.")
    return used_now


def recompute(sane, used_now, stored_price_usd):
    """What the current code would store, minus the AI check (which is not called)."""
    _rule("WHAT THE CURRENT CODE WOULD PRODUCE")
    if not sane:
        print("  0 sane sales -> List at NULL, 1yr Avg NULL (after B-6, there is no")
        print("  fallback). The deal is persisted and stays off the dashboard.")
        return
    prices = [c['inferred_sale_price_cents'] for c in sane]
    print("  Sane sale count: {}".format(len(prices)))

    year_ago = datetime.now() - timedelta(days=365)
    in_year = [c['inferred_sale_price_cents'] for c in sane
               if c['event_timestamp'] >= year_ago]
    if in_year:
        print("  1yr Avg  = mean of {} sales inside 365 days = {}"
              .format(len(in_year), _money(sum(in_year) / len(in_year))))
    else:
        print("  1yr Avg  = None ({} sales, none inside 365 days). After B-6 there "
              "is no fallback.".format(len(prices)))

    if len(prices) < MIN_SALES_FOR_ANALYSIS:
        peak = float(np.median(prices))
        print("  List at  = SPARSE branch, median of {} sales = {}"
              .format(len(prices), _money(peak)))
        print("             Source 'Inferred Sales (Sparse)', which skips the AI")
        print("             check UNLESS the 3x rule fires.")
    else:
        peak = None
        print("  List at  = normal branch (peak-month mode/median). Not recomputed")
        print("             here; this diagnostic does not classify seasons.")

    if peak is not None and used_now:
        ratio = peak / used_now
        print("  3x check : {} / {} = {:.1f}x {}".format(
            _money(peak), _money(used_now), ratio,
            "-> AI check FORCED" if ratio > 3.0 else "-> under threshold"))

    if stored_price_usd is not None and peak is not None:
        stored_cents = int(round(stored_price_usd * 100))
        match = "MATCHES" if abs(peak - stored_cents) < 1 else "DIFFERS FROM"
        print()
        print("  Recomputed List at {} the stored {}."
              .format(match, _money(stored_cents)))
        if match.startswith("DIFFERS"):
            print("  The stored value did not come from today's history through")
            print("  today's code. Either the history moved, or the stored value")
            print("  came from the xAI rescue path.")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Read-only, single-ASIN trace of the inferred-sale pipeline. "
                    "Does not call xAI, write any cache, or touch deals.db."
    )
    parser.add_argument('asin', help='The ASIN to trace, e.g. 1429097078')
    parser.add_argument('--stored-price', type=float, default=None,
                        help='The value stored in deals.db (dollars, e.g. 699.11). '
                             'Passed in rather than read, so this stays DB-free.')
    args = parser.parse_args(argv)

    load_dotenv()
    api_key = os.getenv('KEEPA_API_KEY')
    if not api_key:
        print("KEEPA_API_KEY is not set. Run this from the application root so "
              ".env is found, or export the key.")
        return 1

    print("Diagnostic for ASIN {}".format(args.asin))
    print("Read-only: no xAI call, no cache write, no deals.db access.")

    product, consumed, left = fetch(args.asin, api_key)
    if product is None:
        return 1

    csv_data = describe_history(product)
    if csv_data is None:
        return 1

    window_start = datetime.now() - timedelta(days=HISTORY_WINDOW_DAYS)
    offer_drops, total_drops = find_offer_drops(csv_data, window_start)

    confirmed = []
    if total_drops:
        confirmed, _ = confirm_sales(offer_drops, csv_data, window_start)

    sane = sanitise(confirmed)

    if total_drops:
        trust = (len(sane) / total_drops) * 100
        print()
        print("  Deal Trust would be {} / {} = {:.0f}%"
              .format(len(sane), total_drops, trust))

    check_stored_price(csv_data, args.stored_price)
    used_now = amazon_stats(product)
    recompute(sane, used_now, args.stored_price)

    _rule("TOKENS")
    print("  Consumed by this run: {}".format(consumed))
    print("  Left on the account:  {}".format(left))
    print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
