#!/usr/bin/env python3
"""
diagnose_inferred_sales.py

Read-only diagnostic for ONE ASIN. Answers the question the stored row cannot:
where did this deal's inferred sale prices actually come from?

Written for ASIN 1429097078, whose stored `1yr_Avg` and `List_at` are both 699.11
on a book currently listing used at $28.99. Two mechanisms could produce that, and
they have different fixes:

  (i)  A real offer drop with a WRONG PRICE ATTACHED, because the matched price
       point was on the wrong SIDE of the drop. `infer_sale_events` now takes the
       last price point STRICTLY BEFORE the drop, at any distance.

       Distance turned out NOT to be the problem. Measured on real Keepa history
       for the three ASINs below, 2026-09-12, the gap to the PRECEDING point across
       all 7 confirmed sales was 3.0, 5.1, 10.2, 252.1, 389.6, 516.4 and 2281.4
       hours - bimodal, nothing between 10h and 252h, and 0 drops with no prior
       point at all. The series is a change-log, so a long gap means the lowest
       offer had not changed and the distant point is CORRECT. A proposed 240-hour
       tolerance would have discarded 4 of those 7 and was rejected on that
       evidence. The PRECEDING-GAP column below is what that measurement reads off.

  (ia) THE LEFTOVER ASKING PRICE - FIXED, and still the explanation for most
       inflated stored values. `csv[1]` and `csv[2]` hold the LOWEST New / Used
       offer price, not the price of any particular copy. When the cheapest copy
       sells, the series does not record what it sold for - it steps UP to whatever
       the next cheapest listing asks, at essentially the same timestamp as the
       offer-count drop that marks the sale. The old
       `merge_asof(direction='nearest')` had no tolerance and no tie-break, so it
       could land on the point AT or AFTER the drop and store the asking price of a
       copy that did NOT sell.

       This is what the round numbers on the box look like: of 46 deals with
       `1yr_Avg = List_at` and $50+ profit, three carry exactly $499.95 and others
       exactly $1,000.00, $250.00, $200.00 and $150.00. Those are prices a seller
       typed into a listing, not prices anything transacted at. The PRICE STEP-UP
       TEST section reports, sale by sale, what today's code records and what the
       pre-fix nearest-match would have recorded, so a stored value written under
       the old logic can still be accounted for. A fix to the inference repairs no
       existing row - the light path never recomputes `List_at` or `1yr_Avg` and
       the recalculator is API-free.

  (ii) An xAI-rescued "hidden sale". When the algorithmic pass confirms nothing,
       `infer_sale_events` returns the model's events verbatim, BEFORE the IQR
       outlier filter. This diagnostic reports whether the history ever held the
       stored value - but absence is NOT by itself evidence of invention, because
       `1yr. Avg.` is a mean and the sparse `List at` a median, and an average of
       real prices is usually not itself a price anyone listed at. The derived
       values are computed and compared before xAI is named.

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
New-vs-Used price series choice, the backward / no-exact-match / no-tolerance price
association, the NaN and `price <= 0` guards and the symmetrical IQR.
If that function changes, change this too or its output becomes a lie. The shared
pieces (KEEPA_EPOCH, the timestamp conversion) are imported rather than copied.
`tests/test_diagnose_inferred_sales.py`'s `MirrorsProduction` is what makes KEEP IN
SYNC enforceable.

`reconstruct_prefix_value` mirrors the PRE-FIX pipeline for the same reason, and the
only thing that differed pre-fix was the price association - so it replays the
`price <= 0` guard, the IQR and the mean/median branch rules unchanged. If any of
those change, change it too.

THE CONCLUSION RULE: this script must compute the ORDINARY explanation before naming
an exotic one. A stored value today's code does not reproduce is most often just a
row written before the 2026-09-12 association fix. That is cheap and deterministic to
reconstruct, so it is ruled in or out first, and history drift / the xAI rescue /
ceiling clamping are named only if it is ruled out. This rule exists because the rule
has been broken twice - see `check_stored_price` (2026-09-11) and `recompute`
(2026-09-16, ASIN 0415009804).

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
# There is deliberately NO price-association tolerance to mirror - see the note at
# the top of stable_calculations.py and the PRECEDING-GAP column below.
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
              "stable_calculations.py:262-274 that calls xAI and returns its events "
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
        return [], [], []
    df_rank = df_rank[df_rank['timestamp'] >= window_start]
    df_rank = df_rank.sort_values('timestamp').reset_index(drop=True)
    df_rank['rank_diff'] = df_rank['rank'].diff()

    df_used_price = _to_df(csv_data[2] if len(csv_data) > 2 else None, 'price_cents')
    df_new_price = _to_df(csv_data[1] if len(csv_data) > 1 else None, 'price_cents')

    confirm_window = timedelta(hours=CONFIRM_WINDOW_HOURS)
    confirmed = []
    rejected = []
    # Rank-confirmed drops that today's code discards on price, but which the
    # pre-fix nearest-match could still have priced. See `_keep_legacy_only`.
    legacy_only = []

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

        # The production association: the last point STRICTLY BEFORE the drop, at
        # any distance. No tolerance - a long gap means the lowest offer had not
        # changed, so the distant point is the correct answer.
        matched = pd.merge_asof(
            pd.DataFrame([drop]), price_df, on='timestamp',
            direction='backward', allow_exact_matches=False)
        price_cents = matched['price_cents'].iloc[0]

        # The two neighbouring points, reported either way. 'before' is what the
        # association takes; 'after' is the next listing up the stack, which the
        # pre-fix nearest-match could take instead. Every inflated stored value
        # found on the box in the 2026-09-11 diagnostic was an 'after'.
        before_slice = price_df[price_df['timestamp'] < start_time]
        after_slice = price_df[price_df['timestamp'] >= start_time]
        price_before = before_slice.iloc[-1] if not before_slice.empty else None
        price_after = after_slice.iloc[0] if not after_slice.empty else None

        # What the PRE-FIX code would have stored. Kept so a stored value written
        # under the old logic can still be accounted for - a fix to the inference
        # repairs no existing row.
        legacy_deltas = (price_df['timestamp'] - start_time).abs()
        legacy_chosen = price_df.loc[legacy_deltas.idxmin()]
        legacy_nearest_cents = legacy_chosen['price_cents']
        legacy_chose_at_or_after = bool(legacy_chosen['timestamp'] >= start_time)

        # These two guards drop a RANK-CONFIRMED sale because today's association
        # could not attach a price to it. The pre-fix `nearest` match usually
        # could, so such a drop may well have contributed to a stored pre-fix
        # value. Keep its legacy candidate before discarding the sale, or the
        # reconstruction below silently under-counts and can report "no match"
        # for a row that is in fact fully explained.
        def _keep_legacy_only(reason):
            legacy_only.append({
                'event_timestamp': start_time,
                'offer_type': drop['offer_type'],
                'series': series_name,
                'legacy_nearest_cents': legacy_nearest_cents,
                'dropped_today_because': reason,
            })

        if pd.isna(price_cents):
            # The only way the association fails now: the drop precedes every point
            # in the series. It was 0 of 7 on the live sample of 2026-09-12.
            _keep_legacy_only('no price point exists before the drop')
            rejected.append((start_time, drop['offer_type'],
                             'confirmed, but no price point exists before it at all, '
                             'so no price is attached'))
            continue

        if price_cents <= 0:
            _keep_legacy_only('price before the drop was {} (<= 0)'
                              .format(price_cents))
            rejected.append((start_time, drop['offer_type'],
                             'confirmed, but matched price was {} (<= 0), discarded'
                             .format(price_cents)))
            continue

        gap_days = ((start_time - price_before['timestamp']).total_seconds()
                    / 86400.0)

        confirmed.append({
            'event_timestamp': start_time,
            'inferred_sale_price_cents': price_cents,
            'offer_type': drop['offer_type'],
            'series': series_name,
            'how': how,
            'price_point_timestamp': price_before['timestamp'],
            'gap_days': gap_days,
            'price_before_cents': price_before['price_cents'],
            'price_before_timestamp': price_before['timestamp'],
            'price_after_cents': None if price_after is None
                                 else price_after['price_cents'],
            'price_after_timestamp': None if price_after is None
                                     else price_after['timestamp'],
            'legacy_nearest_cents': legacy_nearest_cents,
            'legacy_chose_at_or_after': legacy_chose_at_or_after,
        })

    print("  CONFIRMED SALES: {}".format(len(confirmed)))
    if confirmed:
        print()
        print("  {:<17} {:>10} {:<11} {:>12}  {}".format(
            "sale timestamp", "price", "from", "PRECEDING-GAP", "confirmed by"))
        print("  " + "-" * 76)
        for c in confirmed:
            print("  {:%Y-%m-%d %H:%M} {:>10} {:<11} {:>11}  {}".format(
                c['event_timestamp'], _money(c['inferred_sale_price_cents']),
                c['series'], "{:.1f}h".format(c['gap_days'] * 24.0), c['how']))
        print()
        print("  'PRECEDING-GAP' is how old the attached price point was at the")
        print("  moment of the offer drop. Production takes the last point STRICTLY")
        print("  BEFORE the drop at ANY distance: the series is a change-log, so a")
        print("  large gap means the lowest offer had not changed and the point is")
        print("  correct rather than stale. There is no time threshold - one was")
        print("  proposed and rejected on this exact measurement (see the module")
        print("  docstring). A drop loses its price only when NO point precedes it,")
        print("  and that appears under NOT CONFIRMED.")
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
    return confirmed, rejected, legacy_only



# Ratio at which an after/before jump stops looking like ordinary repricing and
# starts looking like the series stepping up to the next listing in the stack.
STEP_UP_RATIO = 1.5


def _print_step_up_analysis(confirmed):
    """Account for the leftover asking price, sale by sale.

    csv[1] and csv[2] hold the LOWEST New / Used offer price, not the price of any
    particular copy. When the cheapest copy sells, the series does not record what
    it sold for - it steps UP to whatever the next cheapest listing asks, at
    essentially the moment of the offer-count drop that marks the sale.

    The pre-fix `merge_asof(direction='nearest')` had no tolerance and no tie-break,
    so on a drop whose neighbouring price points straddle it by similar distances it
    could land on the AFTER side and record the leftover asking price of a copy that
    did not sell. That inflated List at and 1yr Avg together, which is what the round
    numbers seen on the box are ($1,000.00, $499.95, $250.00, $200.00, $150.00) -
    asking prices someone typed, not prices anything sold at.

    Today's association takes the BEFORE price, so 'recorded' is always 'before'.
    This section therefore serves a different purpose now: it shows WHAT THE OLD
    LOGIC WOULD HAVE STORED for each sale, which is how a stored value on a row
    written before the fix gets explained. A fix to the inference repairs no
    existing row.
    """
    print()
    print("-" * 78)
    print("  PRICE STEP-UP TEST (what the pre-fix nearest-match would have stored)")
    print("-" * 78)
    print("  {:<17} {:>10} {:>10} {:>8}  {:<8} {:<10} {}".format(
        "sale timestamp", "before", "after", "jump", "recorded", "old would", ""))
    print("  " + "-" * 76)

    suspects = 0
    for c in confirmed:
        before = c.get('price_before_cents')
        after = c.get('price_after_cents')
        recorded = c['inferred_sale_price_cents']
        legacy = c.get('legacy_nearest_cents')

        if before and after and before > 0:
            jump = "{:.1f}x".format(after / before)
        else:
            jump = "-"

        if after is not None and recorded == after:
            which = 'after'
        elif before is not None and recorded == before:
            which = 'before'
        else:
            which = 'other'

        # The signature of the old defect: the nearest-match would have taken the
        # at/after point and it is well above the price in force before the drop.
        is_suspect = (
            c.get('legacy_chose_at_or_after')
            and after is not None and legacy is not None and legacy == after
            and before and after and before > 0
            and (after / before) >= STEP_UP_RATIO
        )
        if is_suspect:
            suspects += 1

        print("  {:%Y-%m-%d %H:%M} {:>10} {:>10} {:>8}  {:<8} {:<10} {}".format(
            c['event_timestamp'], _money(before), _money(after), jump,
            which, _money(legacy),
            '<-- STEP-UP SUSPECT' if is_suspect else ''))

    print()
    print("  'before' is the last price point strictly before the offer drop and is")
    print("  what today's code records; 'after' is the first at or after it, from")
    print("  the same series. 'old would' is what merge_asof(direction='nearest')")
    print("  would have stored, i.e. what a row written before the fix carries.")
    print()
    if suspects:
        print("  {} of {} sale(s) match the step-up signature: the old nearest-match"
              .format(suspects, len(confirmed)))
        print("  would have taken the at/after point, and it is >= {}x the price"
              .format(STEP_UP_RATIO))
        print("  immediately before the drop. Today's code records the 'before'")
        print("  column for those. If the STORED value matches 'old would', the row")
        print("  predates the fix and needs a heavy re-fetch to be corrected.")
    else:
        print("  No sale matches the step-up signature. If the stored price is still")
        print("  wrong, the cause is elsewhere - check the PRECEDING-GAP column")
        print("  above, and the NOT CONFIRMED list.")


def sanitise(confirmed):
    """Mirror of the symmetrical IQR rejection."""
    _rule("STAGE 2 - IQR OUTLIER REJECTION")
    if not confirmed:
        print("  No confirmed sales. In production this is the branch at")
        print("  stable_calculations.py:376-388, which calls xAI and returns the")
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


def _derived_candidates(sane_sales):
    """The values the pricing code COMPUTES rather than copies out of the history.

    Neither of these has to appear in the price history, because both are averages
    of prices that do. Checking them is what stops the section below from blaming
    an absent value on xAI.
    """
    if not sane_sales:
        return []
    prices = [float(c['inferred_sale_price_cents']) for c in sane_sales]
    year_ago = datetime.now() - timedelta(days=365)
    in_year = [float(c['inferred_sale_price_cents']) for c in sane_sales
               if c['event_timestamp'] >= year_ago]

    out = []
    if in_year:
        out.append(("1yr Avg: mean of the {} sale(s) inside 365 days"
                    .format(len(in_year)), sum(in_year) / len(in_year)))
    if len(prices) < MIN_SALES_FOR_ANALYSIS:
        out.append(("List at: sparse-branch median of {} sale(s)".format(len(prices)),
                    float(np.median(prices))))
    return out


def check_stored_price(csv_data, stored_price_usd, sane_sales=None):
    """Did the price history EVER hold the stored value, or was it computed?

    CAVEAT, learned the hard way on ASIN 1429097078 (2026-09-11). An earlier version
    of this section concluded that a value absent from the history "points at an
    xAI-invented event". That conclusion was WRONG, and it fired on a real ASIN.

    `1yr. Avg.` is the **mean** of the in-year sale prices and the sparse `List at`
    is their **median**. An average of two real prices is generally not itself a
    price anyone ever listed at: $699.11 is mean($699.99, $698.23), and neither it
    nor anything near it appears in the history. Absence from the history is
    therefore evidence of nothing on its own.

    So the derived values are now computed and compared BEFORE any conclusion is
    drawn, and xAI is named only when the value is neither in the history nor
    derivable from the sales found here.
    """
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
        return

    # Absent from the history. Do NOT jump to xAI: the stored value may be one the
    # pricing code computed from prices that ARE in the history.
    print("  The value is NOT anywhere in the price history.")
    print()
    print("  That alone means nothing, because two stored values are AVERAGES and")
    print("  an average of real prices is usually not itself a real price:")
    candidates = _derived_candidates(sane_sales)
    if not candidates:
        print("    (no sale events found here, so nothing can be derived)")
    matched = None
    for label, cents in candidates:
        hit = abs(cents - target) < 0.5
        print("    {:<52} {}{}".format(label, _money(cents),
                                       '   <-- MATCHES STORED' if hit else ''))
        if hit and matched is None:
            matched = label
    print()
    if matched is not None:
        print("  The stored value is a COMPUTED average, not a recorded price, so")
        print("  its absence from the history is expected and is not evidence of")
        print("  anything. Judge the inputs instead: read the step-up and gap")
        print("  columns above for the individual sales it averages.")
    else:
        print("  Not in the history AND not derivable from the sales found here.")
        print("  Now xAI is worth considering - but check first whether the sale set")
        print("  has changed since the row was written, which would move the average.")


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
        print("  SKIPS the AI reasonableness check (stable_calculations.py:665).")
    else:
        print()
        print("  No valid Amazon price, so no ceiling is applied and the computed")
        print("  price passes through uncapped.")
    return used_now


def reconstruct_prefix_value(confirmed, legacy_only):
    """What the PRE-FIX code would have stored, from the 'old would' prices.

    WHY THIS EXISTS
    ---------------
    Live case, ASIN 0415009804, 2026-09-16, `--stored-price 500.00`. The step-up
    table reported 'old would' $500.00 on sale 1 and $-0.01 on sale 2. Today's code
    recomputes $223.75. The final section nonetheless concluded "Either the history
    moved, or the stored value came from the xAI rescue path".

    That was WRONG, and wrong in the same way as the `check_stored_price` defect
    caught on 2026-09-11: it named an exotic cause without first computing the
    ordinary one. The stored $500.00 is fully explained as a pre-fix row. The
    pre-fix code would have taken the two 'old would' prices, discarded $-0.01 on
    its `price <= 0` guard, and been left with a single sale of $500.00 - which at
    n=1 goes down the sparse branch and stores its median, $500.00. Exactly the
    stored value, with no history drift and no xAI anywhere near it.

    A diagnostic that draws a confident wrong conclusion is worse than one that
    draws none, because it sends the next investigation in the wrong direction.
    That was recorded on 2026-09-11 and it applies here unchanged.

    WHAT THIS REPLAYS
    -----------------
    The pre-fix pipeline, in order, on the `legacy_nearest_cents` of every
    rank-confirmed drop:

      1.  NaN guard, then the `price <= 0` guard. This is the step that removes the
          $-0.01 in the live case.
      2.  The symmetrical IQR (unchanged by the price-association fix).
      3.  The same branch rules the current code uses: sparse `List at` is the
          MEDIAN of all sane sales when there are fewer than 3; `1yr Avg` is the
          MEAN of the sane sales inside 365 days.

    Only the price ASSOCIATION differed pre-fix, so replaying the rest unchanged is
    the correct reconstruction rather than an approximation.

    `legacy_only` carries rank-confirmed drops that TODAY's code discards on price
    but the pre-fix match could still price. They belong here; leaving them out
    would under-count the pre-fix set and could report "no match" for a row that is
    in fact fully explained.
    """
    candidates = []
    for c in confirmed:
        candidates.append((c['event_timestamp'], c.get('legacy_nearest_cents'),
                           None))
    for c in legacy_only:
        candidates.append((c['event_timestamp'], c.get('legacy_nearest_cents'),
                           c.get('dropped_today_because')))
    candidates.sort(key=lambda row: row[0])

    kept, dropped = [], []
    for ts, price, note in candidates:
        if price is None or pd.isna(price):
            dropped.append((ts, price, 'no nearest price point'))
        elif price <= 0:
            dropped.append((ts, price, 'pre-fix `price <= 0` guard'))
        else:
            kept.append({'event_timestamp': ts,
                         'inferred_sale_price_cents': float(price),
                         'today_note': note})

    trimmed = []
    if len(kept) >= 2:
        prices = [k['inferred_sale_price_cents'] for k in kept]
        q1, q3 = np.percentile(prices, 25), np.percentile(prices, 75)
        iqr = q3 - q1
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        sane = [k for k in kept if lo <= k['inferred_sale_price_cents'] <= hi]
        trimmed = [k for k in kept if k not in sane]
    else:
        sane = list(kept)

    prices = [k['inferred_sale_price_cents'] for k in sane]
    year_ago = datetime.now() - timedelta(days=365)
    in_year = [k['inferred_sale_price_cents'] for k in sane
               if k['event_timestamp'] >= year_ago]

    list_at = None
    list_at_branch = None
    if prices:
        if len(prices) < MIN_SALES_FOR_ANALYSIS:
            list_at = float(np.median(prices))
            list_at_branch = 'SPARSE branch, median of {} sale(s)'.format(len(prices))
        else:
            list_at_branch = ('normal branch (peak-month mode/median) - not '
                              'reconstructed, this diagnostic does not classify '
                              'seasons')

    yr_avg = (sum(in_year) / len(in_year)) if in_year else None

    return {'kept': sane, 'dropped': dropped, 'trimmed': trimmed,
            'list_at_cents': list_at, 'list_at_branch': list_at_branch,
            'yr_avg_cents': yr_avg, 'candidate_count': len(candidates)}


def _print_prefix_reconstruction(prefix):
    """Print the reconstruction. Called before any conclusion is drawn."""
    print()
    print("-" * 78)
    print("  WHAT THE PRE-FIX CODE WOULD HAVE PRODUCED (from the 'old would' column)")
    print("-" * 78)
    if not prefix['candidate_count']:
        print("  No rank-confirmed drops, so there is nothing to reconstruct.")
        return
    print("  Candidates (one per rank-confirmed offer drop): {}"
          .format(prefix['candidate_count']))
    for ts, price, why in prefix['dropped']:
        print("    DISCARDED {:%Y-%m-%d} {:>10}  {}".format(ts, _money(price), why))
    for k in prefix['trimmed']:
        print("    IQR-TRIMMED {:%Y-%m-%d} {:>10}".format(
            k['event_timestamp'], _money(k['inferred_sale_price_cents'])))
    print("  Survived to pricing: {}".format(len(prefix['kept'])))
    for k in prefix['kept']:
        extra = ('  (today discards this sale: {})'.format(k['today_note'])
                 if k['today_note'] else '')
        print("    {:%Y-%m-%d} {:>10}{}".format(
            k['event_timestamp'], _money(k['inferred_sale_price_cents']), extra))
    print()
    if prefix['list_at_cents'] is not None:
        print("  Pre-fix List at = {}  ({})".format(
            _money(prefix['list_at_cents']), prefix['list_at_branch']))
    elif prefix['list_at_branch']:
        print("  Pre-fix List at : {}".format(prefix['list_at_branch']))
    else:
        print("  Pre-fix List at = NULL (no sale survived the pre-fix guards)")
    if prefix['yr_avg_cents'] is not None:
        print("  Pre-fix 1yr Avg = {}  (mean of the sale(s) inside 365 days)"
              .format(_money(prefix['yr_avg_cents'])))
    else:
        print("  Pre-fix 1yr Avg = NULL (no sale inside 365 days)")


def recompute(sane, used_now, stored_price_usd, confirmed=None, legacy_only=None):
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

    if stored_price_usd is None:
        return

    stored_cents = int(round(stored_price_usd * 100))

    if peak is not None:
        match = "MATCHES" if abs(peak - stored_cents) < 1 else "DIFFERS FROM"
        print()
        print("  Recomputed List at {} the stored {}."
              .format(match, _money(stored_cents)))
        if match.startswith("MATCHES"):
            return
    else:
        print()
        print("  List at was not recomputed on this branch, so the stored {} is"
              .format(_money(stored_cents)))
        print("  compared against the pre-fix reconstruction only.")

    # ------------------------------------------------------------------
    # BEFORE naming history drift or xAI, compute the ORDINARY explanation.
    #
    # A stored value that today's code does not reproduce is most often just a
    # row written before the 2026-09-12 price-association fix. Reconstructing
    # that is cheap and it is deterministic, so it must be ruled in or out first.
    #
    # This is the second time this section has drawn a conclusion it had not
    # earned. On 2026-09-11 `check_stored_price` blamed xAI for a value that was
    # simply the mean of two real prices. On 2026-09-16, on ASIN 0415009804, this
    # block blamed "history moved, or the xAI rescue" for a stored $500.00 that
    # was exactly what the pre-fix code would have produced. Same error, same fix:
    # compute the boring cause before naming the exotic one.
    # ------------------------------------------------------------------
    prefix = reconstruct_prefix_value(confirmed or [], legacy_only or [])
    _print_prefix_reconstruction(prefix)

    prefix_matches = []
    if (prefix['list_at_cents'] is not None
            and abs(prefix['list_at_cents'] - stored_cents) < 1):
        prefix_matches.append('List at')
    if (prefix['yr_avg_cents'] is not None
            and abs(prefix['yr_avg_cents'] - stored_cents) < 1):
        prefix_matches.append('1yr Avg')

    print()
    if prefix_matches:
        print("  CONCLUSION: THIS ROW PREDATES THE PRICE-ASSOCIATION FIX.")
        print("  The stored {} is exactly what the pre-fix code would have"
              .format(_money(stored_cents)))
        print("  produced for {} from this same history."
              .format(' and '.join(prefix_matches)))
        print("  The history did not move and xAI is not implicated - the row")
        print("  was simply written before 2026-09-12.")
        print()
        print("  ACTION: this row needs a HEAVY RE-FETCH to pick up the corrected")
        print("  association. Nothing repairs it in place: the light path never")
        print("  recomputes List_at or 1yr_Avg, and recalculator.py is API-free.")
    else:
        print("  The stored value matches NEITHER today's recomputation NOR the")
        print("  pre-fix reconstruction above. Only now are the remaining")
        print("  explanations worth considering:")
        print("    * the history moved since the row was written (Keepa revises")
        print("      and backfills; a re-run of this diagnostic days apart can")
        print("      legitimately differ);")
        print("    * the row came from the xAI rescue path, which returned")
        print("      model-asserted events verbatim, before the IQR filter, for")
        print("      any row written while that path existed;")
        print("    * the value was clamped by the Amazon ceiling or the $1,500")
        print("      hard ceiling - see the AMAZON CEILING section above.")
        print("  None of these is established by this run. Check the derived")
        print("  candidates in STORED PRICE above before settling on one.")


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
    legacy_only = []
    if total_drops:
        confirmed, _, legacy_only = confirm_sales(offer_drops, csv_data,
                                                  window_start)

    sane = sanitise(confirmed)

    if total_drops:
        trust = (len(sane) / total_drops) * 100
        print()
        print("  Deal Trust would be {} / {} = {:.0f}%"
              .format(len(sane), total_drops, trust))

    check_stored_price(csv_data, args.stored_price, sane)
    used_now = amazon_stats(product)
    recompute(sane, used_now, args.stored_price,
              confirmed=confirmed, legacy_only=legacy_only)

    _rule("TOKENS")
    print("  Consumed by this run: {}".format(consumed))
    print("  Left on the account:  {}".format(left))
    print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
