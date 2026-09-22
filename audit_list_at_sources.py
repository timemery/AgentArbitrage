#!/usr/bin/env python3
"""Measure WHERE each visible row's `List at` actually came from. READ ONLY.

Phase 1 of a two-phase investigation. This script MEASURES. It changes no pricing
logic, no `PRICING_LOGIC_VERSION`, and nothing in the database. Nothing here should
be read as a decision to change the pricing code.

WHY THIS EXISTS
---------------
ASIN 1600910513, Prime Pick #1 on 2026-09-22. `deals.db` holds `List_at` 375.66,
`1yr_Avg` 255.23, `Inferred_Sale_Count` 11, `Pricing_Logic_Version` 2 (current),
`Price_Now` 82.97. So it is not a stale-pricing row - it was priced by today's
logic, and today's logic produced $375.66.

`diagnose_inferred_sales.py 1600910513 --stored-price 375.66` showed two confirmed
sales, 2025-10-03 04:04 and 2025-10-06 18:06, BOTH priced $375.66 off `csv[2]`
(Used), with preceding-gaps of 323.4h and 409.4h - i.e. both backward matches
landed on the SAME change-log point, around 2025-09-19. Every other sale on that
ASIN is $152-$300. Amazon today has no used offers at all and two third-party New
offers from $74.99 + $3.99 shipping, with no Amazon offer, so the 90% Amazon
ceiling in `analyze_sales_performance` never engages.

That diagnostic stops exactly where the question starts. Its own words:

    List at  = normal branch (peak-month mode/median). Not recomputed
               here; this diagnostic does not classify seasons.

So it cannot say which sales fed `List at`. This script can, because it calls the
production functions instead of mirroring them.

WHAT IT MEASURES, AND WHAT IT DOES NOT CLAIM
--------------------------------------------
(a) DID THE `List at` VALUE COME FROM A PRICE POINT SHARED BY MORE THAN ONE
    CONFIRMED SALE, and would removing the duplicate change it, and to what.

    The mechanism under test, stated as a hypothesis and checked per row rather
    than assumed: `analyze_sales_performance` takes the MODE of the peak month's
    sale prices and only falls back to the median when no value occurs twice
    (`stable_calculations.py`, "List at Price Calculation"). Two offer drops
    associated to one change-log point produce two sales carrying the identical
    price. In a month where every other price is distinct, that pair is the only
    duplicate, so it wins the frequency vote by being the only candidate - one
    asking price counted twice.

    THIS SCRIPT DOES NOT ASSUME THAT. It records, for every confirmed sale, the
    timestamp of the price point the production `merge_asof` actually matched, and
    reports per row whether the winning value was backed by one shared point, by
    genuinely distinct points, or by the median branch where no duplicate exists
    at all. A row where the mode is backed by two distinct points is NOT the
    artifact and is counted separately.

(b) `List at` AGAINST THE LOWEST CURRENT NEW OFFER FROM ANY SELLER, and how many
    rows a cap at that price would catch. This is the OTHER half of 1600910513:
    the existing Amazon ceiling reads `stats.current[0]`, `avg180[0]`, `avg365[0]`
    - all AMAZON's own price - so it is silent whenever Amazon is not selling,
    which is precisely when a third-party New offer is the real market price.

THE CONCLUSION RULE, inherited from `diagnose_inferred_sales.py`
-----------------------------------------------------------------
Compute the ORDINARY answer before naming an exotic one. That rule exists in that
file because it was broken twice (2026-09-11 `check_stored_price`, 2026-09-16
`recompute` on ASIN 0415009804), and it applies here in a specific way:

*   A row whose `List at` came out of the MEDIAN branch has no duplicate to blame,
    whatever else is odd about it. It is reported as `median`, not as a finding.
*   A mode backed by two DISTINCT price points is ordinary repricing that happened
    to repeat a number. It is reported as `mode-distinct`, not as a finding.
*   Only `mode-shared` - a mode whose winning price is carried by two or more
    sales that matched the SAME point - is the hypothesised artifact, and even
    then the de-duplicated re-run is reported rather than asserted: on some rows
    it changes nothing, and those are counted as `no-change`.

HOW IT AVOIDS RE-IMPLEMENTING THE THING IT IS MEASURING
--------------------------------------------------------
It calls `infer_sale_events` and `analyze_sales_performance` themselves - the same
two calls `_get_analysis` makes - so the peak-month choice, the mode/median branch,
the IQR, the Amazon ceiling and the $1,500 hard ceiling are production's, not a
copy. Two deliberate interventions, both recorded in the output:

1.  `pd.merge_asof` is wrapped, inside `stable_calculations` only and only for the
    duration of the `infer_sale_events` call, by a proxy that copies the price
    frame's own timestamp into a spare column before delegating to the REAL
    `merge_asof`. The matching is entirely pandas'; the wrapper only reads which
    row won. Production reads `['price_cents']` off that frame and ignores extra
    columns, so nothing about the result changes.

2.  `_query_xai_for_reasonableness` is stubbed to return True, so the run spends
    no xAI quota and is deterministic. The count of calls it WOULD have made is
    printed, and every row records whether the check was in play. This measures
    the ARITHMETIC that produces a price, not a fresh model opinion about it -
    and every sampled row already passed that check once, or it would not have a
    stored `List_at`.

CONSTRAINTS, ALL ENFORCED IN CODE
----------------------------------
*   `deals.db` is opened `file:...?mode=ro` (URI read-only). No writes, no upserts.
*   No xAI calls. No cache writes (`_get_analysis`'s memoisation is bypassed, and
    `clear_analysis_cache` is called on exit).
*   Keepa is shared with ingestion at 25/min, so every fetch goes through the same
    `TokenManager` the Smart Ingestor uses, in batches of 5, and the run is
    BOUNDED: `--limit` defaults to 50 and `--limit 0` is refused outright.
*   Tokens consumed are accumulated from Keepa's own `tokensConsumed` and printed.

USAGE
-----
Run from the application root as `www-data` (it needs read access to `deals.db`):

    sudo -u www-data venv/bin/python audit_list_at_sources.py --limit 50

A summary of 25 lines or fewer goes to stdout and nothing else does; progress and
library logging go to stderr. Full per-row detail lands in `Diagnostics/`, which is
gitignored, so the final line of the run prints the `git add -f` needed to get it
off the box.

The runbook is in `Documentation/System_State.md` -> "Auditing where a stored
`List at` came from"; what it is measuring, and why neither finding is an
established defect yet, is in `Documentation/INFERRED_PRICE_LOGIC.md` 4.A.1.

Cost: one heavy /product call per ASIN (`days=365, history=1, offers=20`), the
same parameters `repair_pricing.py` uses, measured at ~6-7 tokens. 50 rows is
roughly 350 tokens, about 14 minutes of refill at 25/min. The real figure is
printed at the end.
"""

import argparse
import json
import logging
import os
import sqlite3
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(REPO_ROOT, 'deals.db')
DEFAULT_OUT_DIR = os.path.join(REPO_ROOT, 'Diagnostics')

DEFAULT_LIMIT = 50
DEFAULT_BATCH_SIZE = 5
# Same reservation repair_pricing.py uses, and for the same reason: the measured
# cost is ~7 and the reservation is transient (token_manager.py:324 reserves,
# :545 overwrites with Keepa's authoritative figure), so 10 keeps a 5-ASIN batch
# at BURST_THRESHOLD rather than well under it.
DEFAULT_RESERVE_PER_ASIN = 10
MAX_CONSECUTIVE_RECHARGE_WAITS = 3

# Spare column the merge_asof proxy uses to carry the price frame's own timestamp
# through the merge. Production selects ['price_cents'] and never sees it.
SOURCE_TS_COLUMN = '_audit_source_timestamp'

# Keepa condition code for New. `seller_info.get_used_product_info` treats
# {2, 3, 4, 5} as Used; 1 is New.
KEEPA_CONDITION_NEW = 1

# The `price_source` string `analyze_sales_performance` sets on the Sparse Sales
# Rescue branch. Branching on what production REPORTS, rather than on a mirrored
# copy of its `MIN_SALES_FOR_ANALYSIS`, is deliberate: that threshold is a local
# inside the function and cannot be imported, and a mirror of it here would be a
# third copy free to drift (`diagnose_inferred_sales.py` already keeps one).
# Pinned by tests/test_audit_list_at_sources.py::ReadsProductionsOwnAnswers.
SPARSE_PRICE_SOURCE = 'Inferred Sales (Sparse)'

# How many rows the stdout summary lists. The rest are in the detail file.
WORST_N = 10

# Classifications for how `List at` was reached. Ordinary first - see THE
# CONCLUSION RULE above.
CLASS_MEDIAN = 'median'
CLASS_MODE_DISTINCT = 'mode-distinct'
CLASS_MODE_SHARED = 'mode-shared'
CLASS_SPARSE = 'sparse-median'
CLASS_UNKNOWN = 'unclassified'


# --------------------------------------------------------------------------
# Instrumentation
# --------------------------------------------------------------------------

class _MergeAsofRecorder:
    """Stands in for `pandas` inside `stable_calculations` for one call.

    Everything except `merge_asof` is delegated untouched, and `merge_asof`
    delegates too - it only adds a passthrough column to the RIGHT frame first so
    the matched row's own timestamp survives the merge, then reads it back.

    Why a proxy object rather than patching `pandas.merge_asof` globally: the real
    pandas module is shared with every other import in the process, and this needs
    to be true of exactly one module for exactly one call.
    """

    def __init__(self, real_pandas):
        self._pd = real_pandas
        # event timestamp (the offer drop) -> matched price point timestamp
        self.matches = {}

    def __getattr__(self, name):
        return getattr(self._pd, name)

    def merge_asof(self, left, right, *args, **kwargs):
        instrument = (kwargs.get('on') == 'timestamp'
                      and hasattr(right, 'columns')
                      and 'price_cents' in right.columns)
        if instrument:
            right = right.copy()
            right[SOURCE_TS_COLUMN] = right['timestamp']

        merged = self._pd.merge_asof(left, right, *args, **kwargs)

        if instrument and len(merged) == 1:
            source_ts = merged[SOURCE_TS_COLUMN].iloc[0]
            if not self._pd.isna(source_ts):
                self.matches[merged['timestamp'].iloc[0]] = source_ts
        return merged


def infer_sales_recording_sources(product):
    """Production `infer_sale_events`, plus the price point each sale matched.

    Returns `(sane_sales, total_offer_drops, sources)` where `sources` maps a
    sale's `event_timestamp` to the timestamp of the price point the production
    backward match landed on. `event_timestamp` IS the left frame's key
    (`start_time = drop['timestamp']` in `stable_calculations`), so the mapping is
    exact rather than inferred from equal prices - two genuinely separate points
    that happen to hold the same price are NOT conflated.
    """
    from keepa_deals import stable_calculations

    real_pandas = stable_calculations.pd
    recorder = _MergeAsofRecorder(real_pandas)
    stable_calculations.pd = recorder
    try:
        sane_sales, total_drops = stable_calculations.infer_sale_events(product)
    finally:
        stable_calculations.pd = real_pandas

    sources = {}
    for sale in sane_sales:
        matched = recorder.matches.get(sale['event_timestamp'])
        if matched is not None:
            sources[sale['event_timestamp']] = matched
    return sane_sales, total_drops, sources


class _XaiStub:
    """Stands in for the reasonableness check. Counts, never calls."""

    def __init__(self):
        self.calls = 0

    def __call__(self, *args, **kwargs):
        self.calls += 1
        return True


def analyse_without_xai(product, sale_events):
    """Production `analyze_sales_performance` with the AI check stubbed to True.

    Returns `(analysis, would_have_called_xai)`. The stub is what keeps this
    script off the shared daily quota and deterministic; the caller records the
    flag so a reader can tell which rows had a live check in production.
    """
    from keepa_deals import stable_calculations

    real_check = stable_calculations._query_xai_for_reasonableness
    stub = _XaiStub()
    stable_calculations._query_xai_for_reasonableness = stub
    try:
        analysis = stable_calculations.analyze_sales_performance(product, sale_events)
    finally:
        stable_calculations._query_xai_for_reasonableness = real_check
    return analysis, stub.calls > 0


# --------------------------------------------------------------------------
# Reading the production result back
# --------------------------------------------------------------------------

def peak_month_number(peak_season):
    """'Oct' -> 10. `analyze_sales_performance` formats it with '%b'."""
    if not peak_season or peak_season == '-':
        return None
    try:
        return datetime.strptime(peak_season, '%b').month
    except ValueError:
        return None


def classify_list_at(sale_events, analysis, sources):
    """Which sales fed `List at`, by which branch, and on how many price points.

    This reads the production result back rather than deciding anything: the
    branch is identified from the peak month `analyze_sales_performance` returned
    and the sale list it was given, and the reconstruction is then CHECKED against
    the value production produced. `branch_matches_production` is False whenever
    the two disagree - the Amazon ceiling clamped the price, the $1,500 hard
    ceiling rejected it, or the AI check invalidated it - and callers must not
    read a duplicate finding off a row where it is False.
    """
    import numpy as np
    from keepa_deals import stable_calculations
    st = stable_calculations.st

    out = {
        'classification': CLASS_UNKNOWN,
        'branch_price_cents': None,
        'contributing': [],
        'mode_count': 0,
        'distinct_source_points': 0,
        'shared_point_sales': 0,
        'peak_month': peak_month_number(analysis.get('peak_season')),
        'branch_matches_production': False,
    }

    final_cents = analysis.get('peak_price_mode_cents', -1)
    if not sale_events or not final_cents or final_cents <= 0:
        # No sales, or the price was rejected outright ($1,500 hard ceiling, an
        # empty peak month, or - in production, not here - a failed AI check).
        # There is no surviving value to attribute to anything.
        return out

    if analysis.get('price_source') == SPARSE_PRICE_SOURCE:
        # Sparse Sales Rescue: median of every sane sale. A median is computed,
        # not copied, so there is no "winning price point" to share.
        prices = [s['inferred_sale_price_cents'] for s in sale_events]
        out['classification'] = CLASS_SPARSE
        out['branch_price_cents'] = float(np.median(prices))
        out['contributing'] = list(sale_events)
    else:
        month = out['peak_month']
        if month is None:
            return out
        peak_sales = [s for s in sale_events
                      if s['event_timestamp'].month == month]
        if not peak_sales:
            return out
        prices = [s['inferred_sale_price_cents'] for s in peak_sales]
        mode_result = st.mode(prices)
        if mode_result.count > 1:
            winner = float(mode_result.mode)
            out['classification'] = CLASS_MODE_DISTINCT
            out['branch_price_cents'] = winner
            out['mode_count'] = int(mode_result.count)
            out['contributing'] = [s for s in peak_sales
                                   if float(s['inferred_sale_price_cents']) == winner]
        else:
            out['classification'] = CLASS_MEDIAN
            out['branch_price_cents'] = float(np.median(prices))
            out['contributing'] = list(peak_sales)

    # How many DISTINCT price points back the contributing sales. A sale whose
    # source point was not recorded counts as its own point, so an unrecorded
    # match can never manufacture a "shared" finding.
    points = []
    for index, sale in enumerate(out['contributing']):
        matched = sources.get(sale['event_timestamp'])
        points.append(matched if matched is not None else ('unrecorded', index))
    out['distinct_source_points'] = len(set(points))
    out['shared_point_sales'] = len(points) - len(set(points))

    if out['classification'] == CLASS_MODE_DISTINCT and out['shared_point_sales'] > 0:
        out['classification'] = CLASS_MODE_SHARED

    branch = out['branch_price_cents']
    out['branch_matches_production'] = (
        branch is not None and final_cents is not None and final_cents > 0
        and abs(branch - final_cents) < 1.0)
    return out


def dedupe_by_source_point(sale_events, sources):
    """One sale per matched price point, keeping the earliest.

    This is the measurement's counterfactual, not a proposed rule: if two offer
    drops were both priced off one change-log point, how would the production
    functions score the row had that point contributed once? A sale with no
    recorded source point is always kept.
    """
    seen = set()
    kept = []
    for sale in sorted(sale_events, key=lambda s: s['event_timestamp']):
        matched = sources.get(sale['event_timestamp'])
        if matched is None:
            kept.append(sale)
            continue
        if matched in seen:
            continue
        seen.add(matched)
        kept.append(sale)
    return kept


# --------------------------------------------------------------------------
# The lowest current New offer
# --------------------------------------------------------------------------

def lowest_new_offer(product, default_shipping_cents):
    """Cheapest LIVE New offer from any seller, landed (item + shipping).

    Shipping follows `seller_info.get_used_product_info`'s convention rather than
    a new one: an unknown shipping cost (-1) is 0 for FBA and the configured
    `estimated_shipping_per_book` for MFN. Rows where that estimate was used are
    flagged, because AGENTS.md 7.8 rejects MFN offers with unknown shipping
    outright elsewhere in the system and a cap built on an estimate would inherit
    that argument.

    `stats.current[1]` - Keepa's own lowest New price, item only - is returned
    alongside as an independent cross-check. It is NOT used as a substitute: it
    carries no shipping and no seller identity.
    """
    from keepa_deals.stable_calculations import KEEPA_EPOCH

    stats = product.get('stats') or {}
    current = stats.get('current') or []
    stats_new_cents = current[1] if len(current) > 1 and current[1] and current[1] > 0 else None

    now_keepa_minutes = int((datetime.now() - KEEPA_EPOCH).total_seconds() / 60)
    freshness_cutoff = now_keepa_minutes - (365 * 24 * 60)

    best = None
    offers = product.get('offers') or []
    for offer in offers:
        try:
            condition = offer.get('condition')
            condition = condition.get('value') if isinstance(condition, dict) else condition
            if condition != KEEPA_CONDITION_NEW:
                continue

            offer_csv = offer.get('offerCSV') or []
            if len(offer_csv) < 3:
                continue
            timestamp, item_cents, shipping_raw = offer_csv[-3], offer_csv[-2], offer_csv[-1]
            if timestamp < freshness_cutoff or not item_cents or item_cents <= 0:
                continue

            is_fba = bool(offer.get('isFBA', False))
            shipping_estimated = False
            if shipping_raw == -1:
                shipping_cents = 0 if is_fba else default_shipping_cents
                shipping_estimated = True
            else:
                shipping_cents = shipping_raw

            landed = item_cents + shipping_cents
            candidate = {
                'item_cents': item_cents,
                'shipping_cents': shipping_cents,
                'landed_cents': landed,
                'is_fba': is_fba,
                'shipping_estimated': shipping_estimated,
                'seller_id': offer.get('sellerId'),
            }
            if best is None or landed < best['landed_cents']:
                best = candidate
        except (AttributeError, KeyError, TypeError, IndexError):
            continue

    return {'best_new_offer': best,
            'new_offer_count': sum(
                1 for o in offers
                if (o.get('condition', {}).get('value')
                    if isinstance(o.get('condition'), dict) else o.get('condition'))
                == KEEPA_CONDITION_NEW),
            'stats_new_cents': stats_new_cents}


# --------------------------------------------------------------------------
# Sampling
# --------------------------------------------------------------------------

def build_sample_sql():
    """Visible rows by `List_at` DESC.

    `VISIBLE_PREDICATE` is imported from `repair_pricing.py`, not restated. It is
    the dashboard's own data-completeness rule plus `Profit > 0`, and a second
    copy here would drift from the sweep's idea of what a subscriber can see.
    Importing is read-only; nothing in that module is changed by this one.
    """
    from repair_pricing import VISIBLE_PREDICATE
    return """
        SELECT "ASIN",
               "List_at"               AS list_at,
               "1yr_Avg"               AS avg_1yr,
               "Price_Now"             AS price_now,
               "Inferred_Sale_Count"   AS stored_sale_count,
               "Pricing_Logic_Version" AS pricing_version,
               "Title"                 AS title
        FROM deals
        WHERE {visible}
        ORDER BY "List_at" DESC, "ASIN" ASC
        LIMIT ?
    """.format(visible=VISIBLE_PREDICATE.strip())


def fetch_sample(db_path, limit, asins=()):
    """Read the sample. Read-only URI connection; this script never writes."""
    uri = 'file:{}?mode=ro'.format(db_path)
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    try:
        if asins:
            placeholders = ','.join('?' * len(asins))
            sql = ('SELECT "ASIN", "List_at" AS list_at, "1yr_Avg" AS avg_1yr, '
                   '"Price_Now" AS price_now, "Inferred_Sale_Count" AS stored_sale_count, '
                   '"Pricing_Logic_Version" AS pricing_version, "Title" AS title '
                   'FROM deals WHERE "ASIN" IN ({})'.format(placeholders))
            rows = con.execute(sql, tuple(asins)).fetchall()
        else:
            rows = con.execute(build_sample_sql(), (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


# --------------------------------------------------------------------------
# Per-row audit
# --------------------------------------------------------------------------

def audit_row(stored, product, default_shipping_cents):
    """Everything this script has to say about one ASIN."""
    from keepa_deals.stable_calculations import clear_analysis_cache

    result = dict(stored)
    result['error'] = None

    sane_sales, total_drops, sources = infer_sales_recording_sources(product)
    analysis, xai_in_play = analyse_without_xai(product, sane_sales)
    clear_analysis_cache()

    recomputed_cents = analysis.get('peak_price_mode_cents', -1)
    result['sane_sale_count'] = len(sane_sales)
    result['total_offer_drops'] = total_drops
    result['peak_season'] = analysis.get('peak_season')
    result['price_source'] = analysis.get('price_source')
    result['xai_check_in_play'] = xai_in_play
    result['recomputed_list_at'] = (round(recomputed_cents / 100.0, 2)
                                    if recomputed_cents and recomputed_cents > 0 else None)

    detail = classify_list_at(sane_sales, analysis, sources)
    result.update({
        'classification': detail['classification'],
        'branch_list_at': (round(detail['branch_price_cents'] / 100.0, 2)
                           if detail['branch_price_cents'] else None),
        'branch_matches_production': detail['branch_matches_production'],
        'contributing_sales': len(detail['contributing']),
        'mode_count': detail['mode_count'],
        'distinct_source_points': detail['distinct_source_points'],
        'shared_point_sales': detail['shared_point_sales'],
    })

    # (a) The counterfactual. Only run it where there is a duplicate to remove.
    result['dedup_list_at'] = None
    result['dedup_changes_list_at'] = False
    result['dedup_sale_count'] = result['sane_sale_count']
    result['dedup_peak_season'] = None
    deduped = dedupe_by_source_point(sane_sales, sources)
    if len(deduped) < len(sane_sales):
        dedup_analysis, _ = analyse_without_xai(product, deduped)
        clear_analysis_cache()
        dedup_cents = dedup_analysis.get('peak_price_mode_cents', -1)
        result['dedup_sale_count'] = len(deduped)
        result['dedup_list_at'] = (round(dedup_cents / 100.0, 2)
                                   if dedup_cents and dedup_cents > 0 else None)
        result['dedup_peak_season'] = dedup_analysis.get('peak_season')
        result['dedup_changes_list_at'] = (
            result['dedup_list_at'] != result['recomputed_list_at'])

    # (b) The lowest live New offer.
    offers = lowest_new_offer(product, default_shipping_cents)
    best = offers['best_new_offer']
    result['new_offer_count'] = offers['new_offer_count']
    result['stats_new_price'] = (round(offers['stats_new_cents'] / 100.0, 2)
                                 if offers['stats_new_cents'] else None)
    result['new_landed'] = round(best['landed_cents'] / 100.0, 2) if best else None
    result['new_item'] = round(best['item_cents'] / 100.0, 2) if best else None
    result['new_shipping'] = round(best['shipping_cents'] / 100.0, 2) if best else None
    result['new_shipping_estimated'] = best['shipping_estimated'] if best else None
    result['new_is_fba'] = best['is_fba'] if best else None

    stored_list_at = _as_float(stored.get('list_at'))
    result['overstatement'] = (round(stored_list_at - result['new_landed'], 2)
                               if stored_list_at is not None and result['new_landed']
                               and stored_list_at > result['new_landed'] else None)
    return result


def _progress(message):
    """Progress and pointers go to stderr; stdout is the summary alone."""
    print(message, file=sys.stderr)


def _as_float(value):
    try:
        return float(str(value).replace('$', '').replace(',', ''))
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

def summarise(rows, tokens, limit, sampled):
    """The stdout summary. 25 lines maximum, by contract - see the tests."""
    ok = [r for r in rows if not r.get('error')]
    failed = len(rows) - len(ok)

    mode_rows = [r for r in ok if r['classification'] in (CLASS_MODE_SHARED,
                                                          CLASS_MODE_DISTINCT)]
    shared = [r for r in ok if r['classification'] == CLASS_MODE_SHARED]
    trustworthy_shared = [r for r in shared if r['branch_matches_production']]
    changed = [r for r in ok if r['dedup_changes_list_at']]
    with_offer = [r for r in ok if r['new_landed']]
    over = [r for r in ok if r['overstatement']]

    # The budget is 25 lines: 11 fixed + WORST_N listed rows + the table header.
    # Blank spacer lines are deliberately absent - they cost as much as a finding.
    dedup_note = ''
    if changed:
        deltas = sorted(r['recomputed_list_at'] - (r['dedup_list_at'] or 0)
                        for r in changed if r['recomputed_list_at'])
        if deltas:
            dedup_note = ', median drop ${:.2f}'.format(deltas[len(deltas) // 2])

    over_note = ''
    if over:
        amounts = sorted(r['overstatement'] for r in over)
        over_note = ', median ${:.2f}, total ${:.2f}'.format(
            amounts[len(amounts) // 2], sum(amounts))

    lines = [
        'LIST AT SOURCE AUDIT  {}  |  {} rows, {} Keepa tokens'.format(
            datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%SZ'), len(rows), tokens),
        '  sample: {} (limit {}); processed {}, failed {}'.format(
            sampled, limit, len(ok), failed),
        '(a) WHAT SET List at',
        '  median / sparse branch (no duplicate possible) .. {}'.format(
            sum(1 for r in ok if r['classification'] in (CLASS_MEDIAN, CLASS_SPARSE))),
        '  mode, backed by DISTINCT price points ........... {}'.format(
            len(mode_rows) - len(shared)),
        '  mode, backed by ONE SHARED point ................ {}   <- the hypothesis'.format(
            len(shared)),
        '    ...of those, reconstruction == production ..... {}'.format(
            len(trustworthy_shared)),
        '  unclassified (price rejected, or no sales) ...... {}'.format(
            sum(1 for r in ok if r['classification'] == CLASS_UNKNOWN)),
        '  de-duplicating CHANGES List at on ............... {} row(s){}'.format(
            len(changed), dedup_note),
        '(b) LOWEST CURRENT NEW OFFER, ANY SELLER',
        '  rows with a live New offer ...................... {} of {}'.format(
            len(with_offer), len(ok)),
        '  List at ABOVE it, so a cap would catch .......... {}{}'.format(
            len(over), over_note),
    ]

    worst = sorted(over, key=lambda r: r['overstatement'], reverse=True)[:WORST_N]
    if worst:
        lines.append('  WORST {} BY OVERSTATEMENT  ASIN        List_at   newLnd     over  how'
                     .format(len(worst)))
        for r in worst:
            lines.append('    {:<10}  {:>8}  {:>7}  {:>7}  {}'.format(
                r['ASIN'], _fmt(r.get('list_at')), _fmt(r['new_landed']),
                _fmt(r['overstatement']), r['classification']))
    return lines


def _fmt(value):
    number = _as_float(value)
    return '-' if number is None else '{:.2f}'.format(number)


DETAIL_COLUMNS = [
    ('ASIN', 'ASIN'), ('list_at', 'stored List_at'),
    ('recomputed_list_at', 'recomputed List_at'), ('classification', 'how'),
    ('branch_matches_production', 'branch==prod'), ('peak_season', 'peak'),
    ('sane_sale_count', 'sane sales'), ('contributing_sales', 'fed List_at'),
    ('mode_count', 'mode count'), ('distinct_source_points', 'distinct points'),
    ('shared_point_sales', 'shared dups'), ('dedup_sale_count', 'sales after dedup'),
    ('dedup_list_at', 'List_at after dedup'), ('dedup_peak_season', 'peak after dedup'),
    ('dedup_changes_list_at', 'dedup changed'),
    ('new_item', 'New item'), ('new_shipping', 'New ship'),
    ('new_landed', 'New landed'), ('new_shipping_estimated', 'ship estimated'),
    ('new_is_fba', 'New FBA'), ('new_offer_count', 'New offers'),
    ('stats_new_price', 'stats.current[1]'), ('overstatement', 'List_at - New landed'),
    ('avg_1yr', 'stored 1yr_Avg'), ('price_now', 'stored Price_Now'),
    ('stored_sale_count', 'stored sale count'), ('pricing_version', 'version'),
    ('total_offer_drops', 'offer drops'), ('price_source', 'price source'),
    ('xai_check_in_play', 'AI check in play'), ('error', 'error'),
]


def write_detail(rows, out_path, summary_lines, tokens, argv_note):
    """Per-row detail, as Markdown so it reads in the vault mirror."""
    with open(out_path, 'w', encoding='utf-8') as fh:
        fh.write('# `List at` source audit\n\n')
        fh.write('Generated {} by `audit_list_at_sources.py`. Read-only: no database\n'
                 'writes, no xAI calls, no cache writes.\n\n'
                 .format(datetime.now(timezone.utc).isoformat()))
        fh.write('Command: `{}`\n\n'.format(argv_note))
        fh.write('Keepa tokens consumed: **{}**\n\n'.format(tokens))
        fh.write('The AI reasonableness check was stubbed to `True` for every row, so\n'
                 '`recomputed List_at` is the ARITHMETIC the pricing code produces. The\n'
                 '`AI check in play` column says which rows reach that check in production.\n\n')
        fh.write('## Summary\n\n```\n')
        fh.write('\n'.join(summary_lines))
        fh.write('\n```\n\n## Every row\n\n')
        fh.write('| ' + ' | '.join(label for _, label in DETAIL_COLUMNS) + ' |\n')
        fh.write('| ' + ' | '.join('---' for _ in DETAIL_COLUMNS) + ' |\n')
        for row in rows:
            cells = []
            for key, _ in DETAIL_COLUMNS:
                value = row.get(key)
                cells.append('' if value is None else str(value))
            fh.write('| ' + ' | '.join(cells) + ' |\n')
        fh.write('\n## Raw\n\n```json\n')
        fh.write(json.dumps(rows, indent=2, default=str))
        fh.write('\n```\n')


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Measure where each visible row\'s List at came from. Read only.')
    parser.add_argument('--limit', type=int, default=DEFAULT_LIMIT,
                        help='How many visible rows to sample, by List_at DESC. '
                             'Default {}. An unbounded run is refused.'.format(DEFAULT_LIMIT))
    parser.add_argument('--asin', action='append', default=[],
                        help='Audit these ASINs instead of sampling. Repeatable.')
    parser.add_argument('--db', default=DEFAULT_DB_PATH)
    parser.add_argument('--out-dir', default=DEFAULT_OUT_DIR)
    parser.add_argument('--batch-size', type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument('--reserve-per-asin', type=int, default=DEFAULT_RESERVE_PER_ASIN)
    args = parser.parse_args(argv)

    if not args.asin and args.limit <= 0:
        parser.error(
            'Refusing an unbounded run. Keepa is shared with ingestion at 25/min and '
            'each row costs a heavy ~7-token fetch, so --limit must be a positive '
            'number of rows (default {}).'.format(DEFAULT_LIMIT))
    if args.batch_size <= 0:
        parser.error('--batch-size must be positive.')

    # stdout carries the summary and nothing else, so it can be read or pasted
    # whole. The pricing modules log a WARNING per suspicious price and an INFO per
    # sale event; all of it, and this script's own progress, goes to stderr.
    logging.basicConfig(level=logging.ERROR, stream=sys.stderr,
                        format='%(levelname)s %(name)s: %(message)s')

    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv('KEEPA_API_KEY')
    if not api_key:
        print('KEEPA_API_KEY is not set. Run from the application root so .env is found.')
        return 2

    if not os.path.exists(args.db):
        print('Database not found: {}'.format(args.db))
        return 2

    stored_rows = fetch_sample(args.db, args.limit, tuple(args.asin))
    if not stored_rows:
        print('No rows matched. Nothing to audit, and no tokens spent.')
        return 0

    from keepa_deals.business_calculations import load_settings
    from keepa_deals.keepa_api import fetch_product_batch
    from keepa_deals.token_manager import TokenManager, TokenRechargeError
    from repair_pricing import recharge_wait_seconds, sleep_through_recharge

    default_shipping_cents = int(
        round(load_settings().get('estimated_shipping_per_book', 0.0) * 100))

    token_manager = TokenManager(api_key)
    if not token_manager.should_skip_sync():
        token_manager.sync_tokens()

    sampled = ('{} named ASIN(s)'.format(len(args.asin)) if args.asin
               else 'visible rows by List_at DESC')
    _progress('Auditing {} row(s) ({}). Heavy fetch, ~7 tokens each.'.format(
        len(stored_rows), sampled))

    results, tokens_total, consecutive_waits = [], 0, 0
    index = 0
    while index < len(stored_rows):
        batch = stored_rows[index:index + args.batch_size]
        asins = [row['ASIN'] for row in batch]
        try:
            token_manager.request_permission_for_call(args.reserve_per_asin * len(asins))
            response, _, consumed, tokens_left = fetch_product_batch(
                api_key, asins, days=365, history=1, offers=20)
        except TokenRechargeError as exc:
            consecutive_waits += 1
            if consecutive_waits > MAX_CONSECUTIVE_RECHARGE_WAITS:
                _progress('  Keepa has not recovered after {} waits. Stopping with {} of '
                          '{} rows done; re-run to continue.'.format(
                          MAX_CONSECUTIVE_RECHARGE_WAITS, len(results), len(stored_rows)))
                break
            wait = recharge_wait_seconds(exc)
            _progress('  Keepa recharge needed ({}). Waiting {}s, then retrying the same '
                      'batch of {}.'.format(exc, wait, len(asins)))
            sleep_through_recharge(wait)
            continue

        consecutive_waits = 0
        tokens_total += consumed or 0
        if tokens_left is not None:
            token_manager.update_after_call(tokens_left)

        products = {p['asin']: p for p in (response or {}).get('products', [])}
        for row in batch:
            product = products.get(row['ASIN'])
            if not product:
                failed = dict(row)
                failed['error'] = 'Keepa returned no product'
                results.append(failed)
                continue
            try:
                results.append(audit_row(row, product, default_shipping_cents))
            except Exception as exc:  # noqa: BLE001 - one bad row must not end the run
                failed = dict(row)
                failed['error'] = '{}: {}'.format(type(exc).__name__, exc)
                results.append(failed)
        index += args.batch_size
        _progress('  {} / {} rows, {} tokens so far.'.format(
            len(results), len(stored_rows), tokens_total))

    summary_lines = summarise(results, tokens_total, args.limit, sampled)

    if not os.path.isdir(args.out_dir):
        os.makedirs(args.out_dir)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out_path = os.path.join(args.out_dir, 'list_at_audit_{}.md'.format(stamp))
    write_detail(results, out_path, summary_lines, tokens_total, ' '.join(sys.argv))

    print('\n'.join(summary_lines))
    _progress('')
    _progress('Detail: {}'.format(out_path))
    relative = os.path.relpath(out_path, REPO_ROOT)
    if not relative.startswith('..'):
        _progress('Diagnostics/ is gitignored, so to get it off the box:')
        _progress('  git add -f {} && git commit -m "List at audit {}" && git push'
                  .format(relative, stamp))
    return 0


if __name__ == '__main__':
    sys.exit(main())
