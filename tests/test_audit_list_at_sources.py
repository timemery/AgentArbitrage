"""`audit_list_at_sources.py` must measure production, not a copy of it.

WHY THIS FILE EXISTS
--------------------
The script exists to answer one question about ASIN 1600910513 and rows like it:
did `List at` come out of a price point that more than one confirmed sale was
associated with? A measurement that re-implements the thing it measures answers a
different question, so the tests here are mostly about FIDELITY:

*   the `merge_asof` proxy must not change what `infer_sale_events` returns;
*   the sale-to-price-point mapping must be by the point's own timestamp, so two
    genuinely separate points holding the same price are NOT reported as shared;
*   the branch classification must read what `analyze_sales_performance` reports
    rather than a mirrored copy of its thresholds;
*   the run must stay read-only, bounded, and off xAI.

THE CONCLUSION RULE, which two of these tests exist to enforce: compute the
ordinary answer before naming the exotic one. `TwoDistinctPointsAreNotAShare` and
`TheMedianBranchIsNeverAFinding` are the guards that stop the script reporting an
artifact where none exists - the failure mode `diagnose_inferred_sales.py` records
having shipped twice (2026-09-11, 2026-09-16).

The headline fixture reproduces the SHAPE measured on 1600910513: eleven sane
sales across four months, the peak month holding one duplicated high price and
several distinct lower ones, and the duplicate carried by a single change-log
point that two offer drops both matched backwards.
"""

import logging
import os
import sqlite3
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import audit_list_at_sources as audit  # noqa: E402
from keepa_deals.stable_calculations import KEEPA_EPOCH, infer_sale_events  # noqa: E402

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

MINUTES_PER_DAY = 24 * 60
MINUTES_PER_HOUR = 60

# The duplicated high price, and the distinct prices around it. Chosen so the
# symmetrical IQR in `infer_sale_events` keeps every one of them - a rejected
# outlier would make the fixture measure the IQR rather than the mode.
DUP_CENTS = 37566
PEAK_OTHER = (30000, 28000)
OTHER_MONTHS = ((20000, 21000), (15200, 16000), (17000, 18000, 19000))

# Current Used price, so the 3x rule forces the AI check exactly as it does live
# (375.66 / 82.97 = 4.5x). The check is stubbed; this only exercises the flag.
CURRENT_USED_CENTS = 8297


def _ktm(moment):
    return int((moment - KEEPA_EPOCH).total_seconds() // 60)


def _flat(points):
    """[(datetime, value), ...] -> Keepa's flat [time, value, time, value, ...]."""
    out = []
    for moment, value in sorted(points, key=lambda p: p[0]):
        out.extend([_ktm(moment), int(value)])
    return out


def _month_anchor(days_back):
    """The 10th of the month containing `now - days_back`, at midnight.

    Anchoring inside a month rather than on a raw offset keeps every drop in the
    fixture in ONE calendar month however the suite is run: `.dt.month` is what
    `analyze_sales_performance` groups on, and a fixture that straddled a month
    boundary on some days of the year would be flaky rather than wrong.
    """
    moment = datetime.now() - timedelta(days=days_back)
    return datetime(moment.year, moment.month, 10)


def _months_before(anchor, count):
    """The 10th of the month `count` whole months before `anchor`."""
    index = anchor.year * 12 + (anchor.month - 1) - count
    return datetime(index // 12, index % 12 + 1, 10)


def build_history(share_the_point=True, asin='AUDITFIXT', new_price_points=None,
                  amazon=None):
    """Eleven confirmed sales, the peak month holding a duplicated price.

    `share_the_point=True` places ONE price point before the last two drops, so
    both backward matches land on it - the 1600910513 shape. `False` places two
    separate points holding the SAME price, which is ordinary repricing and must
    be classified differently.
    """
    # Peak month is the most recent one; 60-day spacing guarantees four distinct
    # calendar months whenever this runs.
    # Whole calendar months apart, not day offsets: since Pricing Logic Version
    # 3 production pools the peak month with its neighbours, and 60-day offsets
    # land in ADJACENT months on some dates (e.g. Jul 1 -> Aug 30), which would
    # pull an off-peak month into the peak season. Two months is never adjacent.
    peak = _month_anchor(45)
    months = [peak] + [_months_before(peak, n) for n in (2, 4, 6)]
    peak_month, *other_months = months

    # (drop time, the price the point before it holds)
    schedule = []
    for index, price in enumerate(OTHER_MONTHS):
        anchor = other_months[index]
        for offset, value in enumerate(price):
            schedule.append((anchor + timedelta(days=offset * 2), value))
    # The peak month, oldest drop first: two distinct prices then the duplicate pair.
    schedule.append((peak_month + timedelta(days=0), PEAK_OTHER[1]))
    schedule.append((peak_month + timedelta(days=2), PEAK_OTHER[0]))
    dup_first = peak_month + timedelta(days=4)
    dup_second = peak_month + timedelta(days=6)
    schedule.append((dup_first, DUP_CENTS))
    schedule.append((dup_second, DUP_CENTS))
    schedule.sort(key=lambda item: item[0])

    # One price point one day before each drop, so the backward match is exact and
    # unambiguous. The duplicate pair is the exception: with share_the_point, the
    # second drop has NO point of its own, so it reaches back to the first's.
    price_points = []
    for drop_time, price in schedule:
        if share_the_point and drop_time == dup_second:
            continue
        price_points.append((drop_time - timedelta(days=1), price))

    # A rank point either side of every drop, so each one is confirmed inside the
    # 240-hour window by a negative rank_diff.
    rank_points = []
    for drop_time, _ in schedule:
        rank_points.append((drop_time - timedelta(hours=1), 100000))
        rank_points.append((drop_time + timedelta(hours=1), 50000))

    # A used-offer count that steps down by one at each drop, and nowhere else, so
    # the fixture produces exactly len(schedule) offer drops.
    offer_points = [(schedule[0][0] - timedelta(days=2), 20 + len(schedule))]
    for index, (drop_time, _) in enumerate(schedule):
        offer_points.append((drop_time, 20 + len(schedule) - index - 1))

    csv_data = [None] * 13
    if new_price_points:
        csv_data[1] = _flat(new_price_points)
    csv_data[2] = _flat(price_points)
    csv_data[3] = _flat(rank_points)
    csv_data[12] = _flat(offer_points)

    # Amazon absent on every index by default, exactly like 1600910513, so the 90%
    # ceiling cannot quietly move the number these tests assert on. `amazon` is a
    # {'current'|'avg180'|'avg365': cents} dict for the tests that DO want it to.
    amazon = amazon or {}
    stats = {
        'current': [amazon.get('current', -1), -1, CURRENT_USED_CENTS, 500000] + [-1] * 19,
        'avg90': [-1] * 23,
        'avg180': [amazon.get('avg180', -1)] + [-1] * 22,
        'avg365': [amazon.get('avg365', -1)] + [-1] * 22,
    }

    return {'asin': asin, 'title': 'List at source fixture', 'csv': csv_data,
            'stats': stats, 'offers': []}


def peak_month_anchor():
    """The month `build_history` uses for the peak. Tests place New prices in it."""
    return _month_anchor(45)


class _Silent(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)


# --------------------------------------------------------------------------
# Fidelity: the instrumentation must not change the thing it observes
# --------------------------------------------------------------------------

class TheProxyDoesNotChangeTheResult(_Silent):

    def test_instrumented_inference_matches_the_production_call(self):
        product = build_history()
        expected, expected_drops = infer_sale_events(product)
        actual, actual_drops, _ = audit.infer_sales_recording_sources(product)

        self.assertEqual(actual_drops, expected_drops)
        self.assertEqual([(s['event_timestamp'], s['inferred_sale_price_cents'])
                          for s in actual],
                         [(s['event_timestamp'], s['inferred_sale_price_cents'])
                          for s in expected])

    def test_pandas_is_restored_afterwards(self):
        from keepa_deals import stable_calculations
        import pandas
        audit.infer_sales_recording_sources(build_history())
        self.assertIs(stable_calculations.pd, pandas)

    def test_every_sale_gets_a_recorded_source_point(self):
        product = build_history()
        sales, _, sources = audit.infer_sales_recording_sources(product)
        self.assertEqual(len(sales), 11)
        self.assertEqual(len(sources), len(sales))


# --------------------------------------------------------------------------
# (a) The duplicate finding, and the two ways it must NOT fire
# --------------------------------------------------------------------------

class ASharedPointIsReportedAndCanBeRemoved(_Silent):

    def setUp(self):
        super().setUp()
        self.product = build_history(share_the_point=True)
        self.sales, _, self.sources = audit.infer_sales_recording_sources(self.product)
        self.analysis, _ = audit.analyse_without_xai(self.product, self.sales)

    def test_two_drops_share_one_price_point(self):
        """The mechanism, before any conclusion about what it did."""
        distinct = len(set(self.sources.values()))
        self.assertEqual(len(self.sources), 11)
        self.assertEqual(distinct, 10, 'exactly one point should back two sales')

    # Pricing Logic Version 3: production scores DISTINCT price points, so the
    # shared point is counted once and can no longer win the mode. These three
    # tests pinned the defect (List at == the duplicated price) until then; they
    # now pin its absence, through the audit's own reconstruction.

    def test_the_duplicated_price_no_longer_sets_list_at(self):
        # Distinct peak points [280, 300, 375.66]: no repeat, median $300.
        self.assertEqual(self.analysis['peak_price_mode_cents'], float(PEAK_OTHER[0]))

    def test_it_is_classified_as_median_and_the_share_is_still_reported(self):
        detail = audit.classify_list_at(self.sales, self.analysis, self.sources)
        self.assertEqual(detail['classification'], audit.CLASS_MEDIAN)
        self.assertEqual(detail['mode_count'], 0)
        self.assertEqual(len(detail['contributing']), 4)
        self.assertEqual(detail['distinct_source_points'], 3)
        self.assertEqual(detail['shared_point_sales'], 1)
        self.assertTrue(detail['branch_matches_production'],
                        'the reconstruction must agree with the production value')

    def test_removing_the_duplicate_no_longer_changes_list_at(self):
        """The counterfactual is now a no-op: production already counts it once."""
        deduped = audit.dedupe_by_source_point(self.sales, self.sources)
        self.assertEqual(len(deduped), 10)

        after, _ = audit.analyse_without_xai(self.product, deduped)
        self.assertEqual(after['peak_price_mode_cents'],
                         self.analysis['peak_price_mode_cents'])

    def test_the_kept_sale_is_the_earliest_of_the_pair(self):
        deduped = audit.dedupe_by_source_point(self.sales, self.sources)
        dupes = [s for s in deduped if s['inferred_sale_price_cents'] == DUP_CENTS]
        self.assertEqual(len(dupes), 1)
        originals = sorted(s['event_timestamp'] for s in self.sales
                           if s['inferred_sale_price_cents'] == DUP_CENTS)
        self.assertEqual(dupes[0]['event_timestamp'], originals[0])


class TwoDistinctPointsAreNotAShare(_Silent):
    """THE CONCLUSION RULE. Same price twice is not the same point twice."""

    def test_repeated_price_from_separate_points_is_mode_distinct(self):
        product = build_history(share_the_point=False)
        sales, _, sources = audit.infer_sales_recording_sources(product)
        analysis, _ = audit.analyse_without_xai(product, sales)

        self.assertEqual(len(set(sources.values())), 11,
                         'this fixture has a point per sale, by construction')
        self.assertEqual(analysis['peak_price_mode_cents'], float(DUP_CENTS),
                         'List at is still the duplicated price...')

        detail = audit.classify_list_at(sales, analysis, sources)
        self.assertEqual(detail['classification'], audit.CLASS_MODE_DISTINCT,
                         '...but nothing was shared, so this is not the artifact')
        self.assertEqual(detail['shared_point_sales'], 0)

    def test_dedup_is_a_no_op_when_nothing_is_shared(self):
        product = build_history(share_the_point=False)
        sales, _, sources = audit.infer_sales_recording_sources(product)
        self.assertEqual(len(audit.dedupe_by_source_point(sales, sources)), len(sales))


class TheMedianBranchIsNeverAFinding(_Silent):
    """A `List at` no duplicate could have produced must not be reported as one."""

    def test_a_peak_month_with_no_repeat_classifies_as_median(self):
        product = build_history(share_the_point=False)
        sales, _, sources = audit.infer_sales_recording_sources(product)
        # Drop one of the duplicated pair, leaving every peak price distinct.
        trimmed, seen = [], False
        for sale in sales:
            if sale['inferred_sale_price_cents'] == DUP_CENTS and not seen:
                seen = True
                continue
            trimmed.append(sale)

        analysis, _ = audit.analyse_without_xai(product, trimmed)
        detail = audit.classify_list_at(trimmed, analysis, sources)
        self.assertEqual(detail['classification'], audit.CLASS_MEDIAN)
        self.assertEqual(detail['mode_count'], 0)
        self.assertEqual(detail['shared_point_sales'], 0)

    def test_an_unrecorded_source_point_cannot_manufacture_a_share(self):
        """Two sales with no recorded point are two unknowns, not one point."""
        product = build_history(share_the_point=True)
        sales, _, _ = audit.infer_sales_recording_sources(product)
        analysis, _ = audit.analyse_without_xai(product, sales)
        detail = audit.classify_list_at(sales, analysis, sources={})
        self.assertEqual(detail['shared_point_sales'], 0)
        # The branch itself reads production's own `price_point`, so it still
        # counts the shared point once and lands on the median.
        self.assertEqual(detail['classification'], audit.CLASS_MEDIAN)


# --------------------------------------------------------------------------
# (b) The lowest current New offer
# --------------------------------------------------------------------------

def _offer(condition, item_cents, shipping_cents, is_fba=False, seller='S1', age_days=1):
    moment = _ktm(datetime.now() - timedelta(days=age_days))
    return {'condition': condition, 'isFBA': is_fba, 'sellerId': seller,
            'offerCSV': [moment, item_cents, shipping_cents]}


class ThePeakWindowNewFloor(_Silent):
    """The bound must be contemporaneous with the sales that set `List at`.

    Today's New offer is the BUY side - what the item costs now, months out of
    season. It bounds what an arbitrageur pays, not what the item can be listed at
    when its season comes round, so it is reported for comparison and never used
    as the floor.
    """

    def _product(self, points):
        csv_data = [None] * 13
        csv_data[1] = _flat(points)
        return {'asin': 'FLOORTEST', 'csv': csv_data, 'stats': {}}

    def _sale(self, moment, cents=DUP_CENTS):
        return {'event_timestamp': moment, 'inferred_sale_price_cents': cents}

    def test_it_takes_the_lowest_new_price_inside_the_window(self):
        month = peak_month_anchor()
        product = self._product([
            (month - timedelta(days=200), 30000),   # long before: not the floor
            (month + timedelta(days=3), 9000),      # inside the window
            (month + timedelta(days=5), 12000),     # inside, but higher
        ])
        floor = audit.peak_window_new_floor(product, [self._sale(month + timedelta(days=4))])
        self.assertEqual(floor['floor_cents'], 9000)
        self.assertEqual(floor['window_count'], 1)
        self.assertFalse(floor['carried'])

    def test_a_window_with_no_points_uses_the_price_carried_into_it(self):
        """`csv[1]` is a change-log: no point in the window means no price CHANGE.

        Same reasoning INFERRED_PRICE_LOGIC.md 2b.1 gives for having no time
        threshold on the price association - a long gap means the price held.
        """
        month = peak_month_anchor()
        product = self._product([(month - timedelta(days=300), 9000)])
        floor = audit.peak_window_new_floor(product, [self._sale(month + timedelta(days=4))])
        self.assertEqual(floor['floor_cents'], 9000)
        self.assertTrue(floor['carried'])
        self.assertEqual(floor['peak_new_points'] if 'peak_new_points' in floor
                         else floor['points'], 0)

    def test_prices_after_the_window_are_ignored(self):
        month = peak_month_anchor()
        product = self._product([
            (month + timedelta(days=3), 30000),
            (month + timedelta(days=45), 1000),   # a later month, far cheaper
        ])
        floor = audit.peak_window_new_floor(product, [self._sale(month + timedelta(days=4))])
        self.assertEqual(floor['floor_cents'], 30000)

    def test_several_years_of_the_same_month_are_several_windows(self):
        month = peak_month_anchor()
        older = datetime(month.year - 1, month.month, 10)
        product = self._product([
            (older + timedelta(days=2), 20000),
            (month + timedelta(days=2), 9000),
        ])
        floor = audit.peak_window_new_floor(
            product, [self._sale(older + timedelta(days=4)),
                      self._sale(month + timedelta(days=4))])
        self.assertEqual(floor['window_count'], 2)
        self.assertEqual(floor['floor_cents'], 9000, 'the floor is the lowest window')
        self.assertEqual(floor['median_window_floor_cents'], 14500.0)

    def test_no_new_history_is_reported_as_no_floor(self):
        product = {'asin': 'X', 'csv': [None] * 13, 'stats': {}}
        floor = audit.peak_window_new_floor(product, [self._sale(datetime.now())])
        self.assertIsNone(floor['floor_cents'])

    def test_no_contributing_sales_is_reported_as_no_floor(self):
        month = peak_month_anchor()
        product = self._product([(month + timedelta(days=3), 9000)])
        self.assertIsNone(audit.peak_window_new_floor(product, [])['floor_cents'])

    def test_non_positive_prices_are_skipped(self):
        month = peak_month_anchor()
        product = self._product([(month + timedelta(days=2), -1),
                                 (month + timedelta(days=3), 9000)])
        self.assertEqual(
            audit.peak_window_new_floor(
                product, [self._sale(month + timedelta(days=4))])['floor_cents'], 9000)


class TheAmazonCeiling(_Silent):
    """Which Amazon figure caps a peak price, and whether it is a peak-season one."""

    def _product(self, current=-1, avg180=-1, avg365=-1):
        return {'asin': 'CEILTEST', 'stats': {
            'current': [current] + [-1] * 22,
            'avg180': [avg180] + [-1] * 22,
            'avg365': [avg365] + [-1] * 22}}

    def test_it_takes_the_minimum_of_the_three(self):
        ceiling = audit.amazon_ceiling(self._product(current=20000, avg180=15000,
                                                     avg365=18000))
        self.assertEqual(ceiling['basis'], 'avg180')
        self.assertEqual(ceiling['amazon_cents'], 15000)
        self.assertEqual(ceiling['ceiling_cents'], 13500.0)

    def test_todays_price_is_flagged_as_todays(self):
        ceiling = audit.amazon_ceiling(self._product(current=10000, avg365=20000))
        self.assertTrue(ceiling['is_todays_price'])
        self.assertFalse(ceiling['blends_seasons'])

    def test_a_trailing_average_is_flagged_as_blended_not_as_trough(self):
        """It spans peak and trough, so calling it a trough-time price overclaims."""
        ceiling = audit.amazon_ceiling(self._product(current=20000, avg365=10000))
        self.assertFalse(ceiling['is_todays_price'])
        self.assertTrue(ceiling['blends_seasons'])

    def test_absent_amazon_prices_mean_no_ceiling(self):
        self.assertIsNone(audit.amazon_ceiling(self._product()))

    def test_it_still_fires_when_amazon_is_not_selling_today(self):
        """current is -1 but a 365-day average survives from when Amazon did sell."""
        ceiling = audit.amazon_ceiling(self._product(current=-1, avg365=10000))
        self.assertEqual(ceiling['basis'], 'avg365')


class TheCeilingIsMeasuredNotAssumed(_Silent):
    """End to end: a clipped row, with the mirror checked against production."""

    def _audit(self, amazon):
        month = peak_month_anchor()
        # New at $400 in the peak window: the peak-window New cap ($403.99) stays
        # out of the way so the Amazon ceiling is what these tests see.
        product = build_history(
            share_the_point=True, asin='CLIPPED001', amazon=amazon,
            new_price_points=[(month + timedelta(days=3), 40000)])
        stored = {'ASIN': 'CLIPPED001', 'list_at': 375.66}
        return audit.audit_row(stored, product, 200)

    def test_an_unclipped_row_reports_no_ceiling(self):
        row = self._audit({})
        self.assertFalse(row['ceiling_engaged'])
        self.assertIsNone(row['ceiling_basis'])
        # Version 3 counts the shared point once: median of $280/$300/$375.66.
        self.assertEqual(row['recomputed_list_at'], 300.00)
        self.assertFalse(row['duplicate_set_the_price'])

    def test_a_trailing_average_clips_the_peak_price(self):
        row = self._audit({'avg365': 20000})       # ceiling = $180.00
        self.assertTrue(row['ceiling_engaged'])
        self.assertEqual(row['ceiling_basis'], 'avg365')
        self.assertEqual(row['ceiling_price'], 180.00)
        self.assertEqual(row['recomputed_list_at'], 180.00)
        self.assertTrue(row['ceiling_blends_seasons'])
        self.assertIsNone(row['ceiling_outside_peak_month'],
                          'an average is not a trough-time reading; do not claim it is')

    def test_the_mirror_is_checked_against_what_production_wrote(self):
        row = self._audit({'avg365': 20000})
        self.assertTrue(row['ceiling_matches_production'])
        self.assertTrue(row['reconstruction_matches_production'])

    def test_a_clipped_row_does_not_count_as_the_duplicate_setting_the_price(self):
        row = self._audit({'avg365': 20000})
        self.assertEqual(row['classification'], audit.CLASS_MEDIAN)
        self.assertFalse(row['duplicate_set_the_price'])

    def test_todays_amazon_price_outside_the_peak_month_is_not_a_ceiling(self):
        """Pricing Logic Version 3: `current` is read only in the peak month.

        The fixture's peak month is always a past month, so today is off-peak.
        """
        self.assertNotEqual(datetime.now().month, peak_month_anchor().month)
        row = self._audit({'current': 20000})
        self.assertFalse(row['ceiling_engaged'])
        self.assertIsNone(row['ceiling_basis'])
        self.assertEqual(row['recomputed_list_at'], 300.00)
        self.assertTrue(row['reconstruction_matches_production'])

    def test_a_new_capped_row_is_reconstructed(self):
        month = peak_month_anchor()
        product = build_history(share_the_point=True, asin='NEWCAP0001',
                                new_price_points=[(month + timedelta(days=3), 9000)])
        row = audit.audit_row({'ASIN': 'NEWCAP0001', 'list_at': 375.66}, product, 200)
        self.assertEqual(row['peak_new_cap'], 'applied')
        self.assertEqual(row['recomputed_list_at'], 93.99)
        self.assertTrue(row['reconstruction_matches_production'])


class TheOverstatementUsesThePeakWindowNotToday(_Silent):

    def _audit(self, new_points, offers):
        product = build_history(share_the_point=True, asin='BOUNDTEST',
                                new_price_points=new_points)
        product['offers'] = offers
        stored = {'ASIN': 'BOUNDTEST', 'list_at': 375.66}
        return audit.audit_row(stored, product, 200)

    def test_overstatement_is_against_the_peak_window_floor(self):
        month = peak_month_anchor()
        row = self._audit([(month + timedelta(days=3), 9000)],
                          [_offer(1, 7499, 399)])
        self.assertEqual(row['peak_new_floor'], 90.00)
        self.assertEqual(row['overstatement'], round(375.66 - 90.00, 2))

    def test_todays_price_is_carried_but_never_used_as_the_floor(self):
        """A cheap price TODAY must not shrink the peak-season overstatement."""
        month = peak_month_anchor()
        row = self._audit([(month + timedelta(days=3), 30000)],
                          [_offer(1, 500, 0)])          # $5.00 today
        self.assertEqual(row['peak_new_floor'], 300.00)
        self.assertEqual(row['overstatement'], round(375.66 - 300.00, 2))
        self.assertEqual(row['new_landed'], 5.00)
        self.assertTrue(row['above_current_new'],
                        'still reported, as a comparison')

    def test_a_row_with_no_peak_window_price_has_no_overstatement(self):
        row = self._audit(None, [_offer(1, 500, 0)])
        self.assertIsNone(row['peak_new_floor'])
        self.assertIsNone(row['overstatement'])
        self.assertTrue(row['above_current_new'])

    def test_the_windows_are_recorded_for_the_reader(self):
        month = peak_month_anchor()
        row = self._audit([(month + timedelta(days=3), 9000)], [])
        self.assertIn('{}-{:02d}:90.00'.format(month.year, month.month),
                      row['peak_windows'])


class TheLowestNewOffer(_Silent):

    def _product(self, offers, stats_new=None):
        current = [-1, stats_new if stats_new else -1, CURRENT_USED_CENTS, 500000]
        return {'asin': 'OFFERTEST', 'offers': offers,
                'stats': {'current': current + [-1] * 19}}

    def test_it_takes_the_cheapest_landed_price_not_the_cheapest_item(self):
        product = self._product([
            _offer(1, 7499, 399, seller='A'),   # 78.98 landed
            _offer(1, 7400, 1500, seller='B'),  # 89.00 landed, cheaper item
        ])
        best = audit.lowest_new_offer(product, 200)['best_new_offer']
        self.assertEqual(best['landed_cents'], 7898)
        self.assertEqual(best['seller_id'], 'A')

    def test_used_offers_are_ignored(self):
        product = self._product([_offer(4, 1000, 0), _offer(1, 7499, 399)])
        result = audit.lowest_new_offer(product, 200)
        self.assertEqual(result['best_new_offer']['item_cents'], 7499)
        self.assertEqual(result['new_offer_count'], 1)

    def test_a_dict_shaped_condition_is_read_the_same_way(self):
        product = self._product([_offer({'value': 1}, 7499, 399)])
        self.assertIsNotNone(audit.lowest_new_offer(product, 200)['best_new_offer'])

    def test_unknown_shipping_is_zero_for_fba_and_estimated_for_mfn(self):
        fba = self._product([_offer(1, 7499, -1, is_fba=True)])
        best = audit.lowest_new_offer(fba, 200)['best_new_offer']
        self.assertEqual(best['landed_cents'], 7499)
        self.assertTrue(best['shipping_estimated'])

        mfn = self._product([_offer(1, 7499, -1, is_fba=False)])
        best = audit.lowest_new_offer(mfn, 200)['best_new_offer']
        self.assertEqual(best['landed_cents'], 7699)
        self.assertTrue(best['shipping_estimated'])

    def test_known_shipping_is_not_flagged_as_estimated(self):
        product = self._product([_offer(1, 7499, 399)])
        self.assertFalse(
            audit.lowest_new_offer(product, 200)['best_new_offer']['shipping_estimated'])

    def test_stale_offers_are_skipped(self):
        product = self._product([_offer(1, 100, 0, age_days=400)])
        self.assertIsNone(audit.lowest_new_offer(product, 200)['best_new_offer'])

    def test_no_new_offer_is_reported_as_none_not_zero(self):
        result = audit.lowest_new_offer(self._product([]), 200)
        self.assertIsNone(result['best_new_offer'])
        self.assertEqual(result['new_offer_count'], 0)

    def test_stats_current_new_is_carried_as_a_cross_check(self):
        product = self._product([_offer(1, 7499, 399)], stats_new=7499)
        self.assertEqual(audit.lowest_new_offer(product, 200)['stats_new_cents'], 7499)


# --------------------------------------------------------------------------
# Reading production's own answers rather than a mirror of them
# --------------------------------------------------------------------------

class ReadsProductionsOwnAnswers(_Silent):

    def test_the_sparse_price_source_string_still_matches_production(self):
        """`MIN_SALES_FOR_ANALYSIS` is a local and cannot be imported, so the
        script branches on the `price_source` production reports instead. If that
        string is ever reworded, this fails rather than the script silently
        classifying every sparse row as a normal-branch one."""
        path = os.path.join(REPO_ROOT, 'keepa_deals', 'stable_calculations.py')
        with open(path, encoding='utf-8') as fh:
            source = fh.read()
        self.assertIn("price_source = '{}'".format(audit.SPARSE_PRICE_SOURCE), source)

    def test_a_sparse_row_is_classified_from_that_string(self):
        product = build_history()
        sales, _, sources = audit.infer_sales_recording_sources(product)
        sparse = sorted(sales, key=lambda s: s['event_timestamp'])[:2]
        analysis, _ = audit.analyse_without_xai(product, sparse)
        self.assertEqual(analysis['price_source'], audit.SPARSE_PRICE_SOURCE)
        detail = audit.classify_list_at(sparse, analysis, sources)
        self.assertEqual(detail['classification'], audit.CLASS_SPARSE)

    def test_a_rejected_price_is_not_attributed_to_anything(self):
        analysis = {'peak_price_mode_cents': -1, 'peak_season': 'Oct'}
        detail = audit.classify_list_at([{'event_timestamp': datetime.now(),
                                          'inferred_sale_price_cents': 100}],
                                        analysis, {})
        self.assertEqual(detail['classification'], audit.CLASS_UNKNOWN)
        self.assertFalse(detail['branch_matches_production'])

    def test_peak_month_is_parsed_from_the_production_format(self):
        self.assertEqual(audit.peak_month_number('Oct'), 10)
        self.assertIsNone(audit.peak_month_number('-'))
        self.assertIsNone(audit.peak_month_number(None))


# --------------------------------------------------------------------------
# The constraints: read-only, bounded, no xAI
# --------------------------------------------------------------------------

class ItNeverCallsXai(_Silent):

    def test_the_real_check_is_not_called_and_is_restored(self):
        from keepa_deals import stable_calculations

        def explode(*args, **kwargs):
            raise AssertionError('the audit must never call xAI')

        with patch.object(stable_calculations, '_query_xai_for_reasonableness',
                          side_effect=explode) as real:
            product = build_history()
            sales, _, _ = audit.infer_sales_recording_sources(product)
            _, in_play = audit.analyse_without_xai(product, sales)
            real.assert_not_called()
            self.assertTrue(in_play, 'the 3x rule should reach the check on this row')
            self.assertIs(stable_calculations._query_xai_for_reasonableness, real)


class ItOnlyOpensTheDatabaseReadOnly(_Silent):

    def setUp(self):
        super().setUp()
        self.db_path = os.path.join(REPO_ROOT, 'test_audit_list_at.db')
        con = sqlite3.connect(self.db_path)
        con.execute('CREATE TABLE deals (ASIN TEXT, List_at REAL, "1yr_Avg" TEXT, '
                    'Price_Now REAL, Inferred_Sale_Count INTEGER, '
                    '"Pricing_Logic_Version" INTEGER, Title TEXT, Profit REAL)')
        con.executemany(
            'INSERT INTO deals VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            [('HIGH000001', 500.0, '400.00', 50.0, 5, 2, 'High', 40.0),
             ('LOW0000001', 100.0, '90.00', 20.0, 5, 2, 'Low', 30.0),
             ('HIDDEN0001', 300.0, '-', 20.0, 5, 2, 'Hidden', 30.0)])
        con.commit()
        con.close()

    def tearDown(self):
        for suffix in ('', '-wal', '-shm'):
            if os.path.exists(self.db_path + suffix):
                os.remove(self.db_path + suffix)
        super().tearDown()

    def test_the_connection_uri_asks_for_read_only(self):
        real_connect = sqlite3.connect
        seen = []

        def recording_connect(target, *args, **kwargs):
            seen.append((target, kwargs))
            return real_connect(target, *args, **kwargs)

        with patch.object(sqlite3, 'connect', recording_connect):
            audit.fetch_sample(self.db_path, 10)

        self.assertEqual(len(seen), 1)
        target, kwargs = seen[0]
        self.assertIn('mode=ro', target)
        self.assertTrue(kwargs.get('uri'))

    def test_a_write_through_that_uri_is_refused(self):
        con = sqlite3.connect('file:{}?mode=ro'.format(self.db_path), uri=True)
        try:
            with self.assertRaises(sqlite3.OperationalError):
                con.execute('UPDATE deals SET List_at = 1')
        finally:
            con.close()

    def test_the_sample_is_visible_rows_by_list_at_desc(self):
        rows = audit.fetch_sample(self.db_path, 10)
        self.assertEqual([r['ASIN'] for r in rows], ['HIGH000001', 'LOW0000001'],
                         'the row with an unusable 1yr_Avg is not dashboard-visible')

    def test_the_limit_is_applied(self):
        self.assertEqual(len(audit.fetch_sample(self.db_path, 1)), 1)

    def test_named_asins_bypass_the_sample_but_still_read_only(self):
        rows = audit.fetch_sample(self.db_path, 10, asins=('HIDDEN0001',))
        self.assertEqual([r['ASIN'] for r in rows], ['HIDDEN0001'])

    def test_the_sample_sql_uses_the_shared_visible_predicate(self):
        from repair_pricing import VISIBLE_PREDICATE
        self.assertIn(VISIBLE_PREDICATE.strip(), audit.build_sample_sql())


class TheSampleCanBeRepresentative(_Silent):

    def test_the_default_order_is_still_list_at_desc(self):
        self.assertIn('"List_at" DESC', audit.build_sample_sql())

    def test_random_order_draws_at_random_from_the_same_visible_set(self):
        from repair_pricing import VISIBLE_PREDICATE
        sql = audit.build_sample_sql('random')
        self.assertIn('RANDOM()', sql)
        self.assertIn(VISIBLE_PREDICATE.strip(), sql)


# --------------------------------------------------------------------------
# (d) The thin peak season - what each candidate minimum would unprice
# --------------------------------------------------------------------------

def _season_sale(year, month, cents, point):
    """A hand-built sale; `point` names its price point, None = unrecorded."""
    event = {'event_timestamp': datetime(year, month, 10),
             'inferred_sale_price_cents': cents}
    if point is not None:
        event['price_point'] = ('Used', datetime(2020, 1, 1) + timedelta(days=point))
    return event


class TheThinPeakSeasonIsMeasured(_Silent):
    """Counted in DISTINCT points, pooled across years, under both definitions."""

    NORMAL = {'price_source': 'Inferred Sales', 'peak_season': 'Sep'}
    SPARSE = {'price_source': audit.SPARSE_PRICE_SOURCE, 'peak_season': '-'}

    def test_the_candidates_and_width_are_named_constants(self):
        self.assertEqual(audit.PEAK_SEASON_MIN_CANDIDATES, (2, 3, 4))
        self.assertEqual(audit.PEAK_WINDOW_HALF_WIDTH_MONTHS, 1)

    def test_the_peak_month_is_pooled_across_years(self):
        sales = [_season_sale(2024, 9, 5000, 1), _season_sale(2025, 9, 5200, 2),
                 _season_sale(2025, 3, 3000, 3)]
        counts = audit.peak_season_counts(sales, self.NORMAL)
        self.assertEqual(counts['season_points_month'], 2)

    def test_the_window_adds_the_neighbouring_months_only(self):
        sales = [_season_sale(2025, 9, 5000, 1), _season_sale(2025, 8, 4800, 2),
                 _season_sale(2024, 10, 4900, 3), _season_sale(2025, 7, 4000, 4)]
        counts = audit.peak_season_counts(sales, self.NORMAL)
        self.assertEqual(counts['season_points_month'], 1)
        self.assertEqual(counts['season_points_window'], 3, 'July is two months out')

    def test_a_december_peak_window_wraps_into_january(self):
        self.assertTrue(audit._in_window(1, 12, 1))
        self.assertTrue(audit._in_window(11, 12, 1))
        self.assertFalse(audit._in_window(2, 12, 1))

    def test_sale_events_are_counted_beside_points(self):
        """Steady seller: many sales in the season, all on one price point."""
        sales = [_season_sale(2025, 9, 5000, 1), _season_sale(2025, 9, 5000, 1),
                 _season_sale(2025, 10, 5000, 1), _season_sale(2024, 8, 5000, 1),
                 _season_sale(2025, 3, 3000, 2)]
        counts = audit.peak_season_counts(sales, self.NORMAL)
        self.assertEqual(counts['season_points_window'], 1)
        self.assertEqual(counts['season_sales_window'], 4)
        self.assertEqual(counts['season_sales_month'], 2)

    def test_a_shared_point_counts_once(self):
        sales = [_season_sale(2025, 9, 5000, 1), _season_sale(2025, 9, 5000, 1),
                 _season_sale(2024, 9, 5000, 2)]
        counts = audit.peak_season_counts(sales, self.NORMAL)
        self.assertEqual(counts['season_points_month'], 2)

    def test_a_sparse_row_is_centred_on_the_mirrored_peak_month(self):
        sales = [_season_sale(2025, 9, 5000, 1), _season_sale(2025, 10, 4000, 2)]
        counts = audit.peak_season_counts(sales, self.SPARSE)
        self.assertTrue(counts['is_sparse'])
        self.assertTrue(counts['season_centre_mirrored'])
        self.assertEqual(counts['season_centre_month'], 9)
        self.assertEqual(counts['season_points_month'], 1)
        self.assertEqual(counts['season_points_window'], 2)

    def test_the_summary_counts_unpriced_rows_per_candidate(self):
        rows = [
            _row('THIN000001', season_points_month=1, season_points_window=3),
            _row('THIN000002', season_points_month=2, season_points_window=2,
                 is_sparse=True),
            _row('FULL000001', season_points_month=5, season_points_window=7),
            _row('GONE000001', recomputed_list_at=None),
        ]
        lines = audit.thin_season_lines(rows)
        self.assertIn('of 3 priced (1 already not)', lines[0])
        # min 2: only THIN000001 by month; nobody by window.
        self.assertEqual(lines[1], '  min 2:  peak month only   1 [0]  |  peak month +/-1   0 [0]')
        # min 3: both thin rows by month (one sparse); only the sparse one by window.
        self.assertEqual(lines[2], '  min 3:  peak month only   2 [1]  |  peak month +/-1   1 [1]')

    def test_section_d_appears_in_the_summary(self):
        lines = audit.summarise([_row('ASIN000001', season_points_month=1,
                                      season_points_window=1)],
                                tokens=7, limit=1, sampled='t')
        self.assertTrue(any(line.startswith('(d) THIN PEAK SEASON') for line in lines))


class TheRunIsBounded(_Silent):

    def test_an_unbounded_run_is_refused(self):
        with self.assertRaises(SystemExit) as raised:
            audit.main(['--limit', '0'])
        self.assertNotEqual(raised.exception.code, 0)

    def test_a_negative_limit_is_refused(self):
        with self.assertRaises(SystemExit):
            audit.main(['--limit', '-1'])

    def test_the_default_limit_is_fifty(self):
        self.assertEqual(audit.DEFAULT_LIMIT, 50)


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

def _row(asin, **overrides):
    row = {
        'ASIN': asin, 'list_at': 400.0, 'recomputed_list_at': 400.0,
        'classification': audit.CLASS_MODE_SHARED,
        'reconstruction_matches_production': True, 'duplicate_set_the_price': True,
        'dedup_changes_list_at': True, 'dedup_list_at': 300.0,
        'peak_new_floor': 90.0, 'overstatement': 310.0,
        'new_landed': 78.98, 'above_current_new': True,
        'ceiling_engaged': False, 'ceiling_outside_peak_month': None,
        'ceiling_blends_seasons': False, 'ceiling_matches_production': None,
        'error': None,
    }
    row.update(overrides)
    return row


class TheSummaryFitsOnScreen(_Silent):

    def test_it_is_never_more_than_25_lines(self):
        rows = [_row('ASIN%06d' % n) for n in range(60)]
        lines = audit.summarise(rows, tokens=420, limit=60, sampled='test')
        self.assertLessEqual(len(lines), 25, '\n'.join(lines))

    def test_it_lists_at_most_ten_rows(self):
        rows = [_row('ASIN%06d' % n, overstatement=float(n) + 1) for n in range(60)]
        lines = audit.summarise(rows, tokens=420, limit=60, sampled='test')
        listed = [line for line in lines if line.strip().startswith('ASIN')]
        self.assertEqual(len(listed), audit.WORST_N)

    def test_the_worst_rows_come_first(self):
        rows = [_row('ASIN%06d' % n, overstatement=float(n) + 1) for n in range(12)]
        lines = audit.summarise(rows, tokens=1, limit=12, sampled='test')
        listed = [line for line in lines if line.strip().startswith('ASIN')]
        self.assertIn('ASIN000011', listed[0])

    def test_an_empty_run_still_summarises(self):
        lines = audit.summarise([], tokens=0, limit=50, sampled='test')
        self.assertLessEqual(len(lines), 25)
        self.assertTrue(any('0 rows' in line for line in lines))

    def test_failed_rows_are_counted_not_dropped(self):
        rows = [_row('OK00000001'), {'ASIN': 'BAD0000001', 'error': 'no product'}]
        lines = audit.summarise(rows, tokens=7, limit=2, sampled='test')
        self.assertTrue(any('failed 1' in line for line in lines))

    def test_it_stays_within_25_lines_with_every_section_populated(self):
        rows = [_row('ASIN%06d' % n, overstatement=float(n) + 1,
                     ceiling_engaged=(n % 2 == 0),
                     ceiling_outside_peak_month=(n % 4 == 0),
                     ceiling_blends_seasons=(n % 3 == 0),
                     ceiling_matches_production=(n != 4))
                for n in range(60)]
        lines = audit.summarise(rows, tokens=420, limit=60, sampled='test')
        self.assertLessEqual(len(lines), 25, '\n'.join(lines))

    def test_no_line_is_wider_than_a_terminal(self):
        rows = [_row('ASIN%06d' % n, overstatement=float(n) + 1) for n in range(60)]
        for line in audit.summarise(rows, tokens=420, limit=60, sampled='test'):
            self.assertLessEqual(len(line), 100, line)

    def test_the_peak_window_floor_is_the_column_shown_not_todays_price(self):
        rows = [_row('ASIN000001', peak_new_floor=90.0, new_landed=5.0,
                     overstatement=310.0)]
        listed = [l for l in audit.summarise(rows, tokens=7, limit=1, sampled='t')
                  if l.strip().startswith('ASIN')]
        self.assertIn('90.00', listed[0])
        self.assertNotIn('5.00', listed[0])

    def test_a_disagreeing_ceiling_mirror_is_surfaced(self):
        rows = [_row('ASIN000001', ceiling_engaged=True,
                     ceiling_matches_production=False)]
        lines = audit.summarise(rows, tokens=7, limit=1, sampled='test')
        self.assertTrue(any('mirror DISAGREED on 1' in line for line in lines),
                        '\n'.join(lines))

    def test_todays_price_is_labelled_as_a_comparison_not_a_bound(self):
        lines = audit.summarise([_row('ASIN000001')], tokens=7, limit=1, sampled='t')
        joined = '\n'.join(lines)
        self.assertIn('comparison only', joined)
        self.assertIn('not a bound', joined)


class TheWholeRunHangsTogether(_Silent):
    """End to end with Keepa and the token bucket faked, because the box is not here.

    The unit tests above cover the parts; this covers the wiring - the sample
    query, the batching, the token accounting, the two output destinations - which
    is what actually fails the first time a script is run somewhere real.
    """

    def setUp(self):
        super().setUp()
        self.db_path = os.path.join(REPO_ROOT, 'test_audit_e2e.db')
        self.out_dir = os.path.join(REPO_ROOT, 'test_audit_e2e_out')
        con = sqlite3.connect(self.db_path)
        con.execute('CREATE TABLE deals (ASIN TEXT, List_at REAL, "1yr_Avg" TEXT, '
                    'Price_Now REAL, Inferred_Sale_Count INTEGER, '
                    '"Pricing_Logic_Version" INTEGER, Title TEXT, Profit REAL)')
        con.executemany(
            'INSERT INTO deals VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            [('1600910513', 375.66, '255.23', 82.97, 11, 2, 'Shared point', 120.0),
             ('DISTINCT001', 375.66, '255.23', 82.97, 11, 2, 'Repriced twice', 120.0),
             ('CLIPPED0001', 180.00, '255.23', 82.97, 11, 2, 'Amazon clipped', 60.0),
             ('MISSING0001', 200.00, '180.00', 40.00, 4, 2, 'Keepa drops it', 60.0)])
        con.commit()
        con.close()

        month = peak_month_anchor()
        peak_new = [(month + timedelta(days=3), 9000)]

        shared = build_history(share_the_point=True, asin='1600910513',
                               new_price_points=peak_new)
        shared['offers'] = [_offer(1, 7499, 399, seller='A')]
        distinct = build_history(share_the_point=False, asin='DISTINCT001',
                                 new_price_points=peak_new)
        distinct['offers'] = [_offer(1, 44900, -1, is_fba=True, seller='B')]
        # Amazon is not selling today, but a 365-day average survives from when it
        # was - so the ceiling engages on a figure that spans both seasons.
        # Its own, higher New price, so the $180 Amazon ceiling - not the
        # peak-window New cap - is what clips it.
        clipped = build_history(share_the_point=True, asin='CLIPPED0001',
                                new_price_points=[(month + timedelta(days=3), 40000)],
                                amazon={'avg365': 20000})
        clipped['offers'] = [_offer(1, 7499, 399, seller='C')]
        self.products = {p['asin']: p for p in (shared, distinct, clipped)}

    def tearDown(self):
        for suffix in ('', '-wal', '-shm'):
            if os.path.exists(self.db_path + suffix):
                os.remove(self.db_path + suffix)
        if os.path.isdir(self.out_dir):
            for name in os.listdir(self.out_dir):
                os.remove(os.path.join(self.out_dir, name))
            os.rmdir(self.out_dir)
        super().tearDown()

    def _run(self, argv):
        import keepa_deals.keepa_api as keepa_api
        import keepa_deals.token_manager as token_manager

        calls = []

        def fake_fetch(api_key, asins, **kwargs):
            calls.append((list(asins), kwargs))
            found = [self.products[a] for a in asins if a in self.products]
            return {'products': found}, {}, 7 * len(asins), 300.0

        class FakeTokenManager:
            REFILL_RATE_PER_MINUTE = 25.0
            tokens = 300.0

            def __init__(self, api_key):
                pass

            def should_skip_sync(self):
                return True

            def sync_tokens(self):
                raise AssertionError('should_skip_sync said no')

            def request_permission_for_call(self, cost):
                calls.append(('reserve', cost))

            def update_after_call(self, tokens_left):
                calls.append(('reconcile', tokens_left))

        with patch.dict(os.environ, {'KEEPA_API_KEY': 'test-key'}), \
                patch.object(keepa_api, 'fetch_product_batch', fake_fetch), \
                patch.object(token_manager, 'TokenManager', FakeTokenManager), \
                patch.object(logging, 'basicConfig'), \
                patch('sys.stdout'), patch('sys.stderr'):
            code = audit.main(['--db', self.db_path, '--out-dir', self.out_dir] + argv)
        return code, calls

    def _detail(self):
        names = os.listdir(self.out_dir)
        self.assertEqual(len(names), 1)
        with open(os.path.join(self.out_dir, names[0]), encoding='utf-8') as fh:
            return fh.read()

    def test_it_runs_and_writes_one_detail_file(self):
        code, _ = self._run(['--limit', '10'])
        self.assertEqual(code, 0)
        written = self._detail()
        for asin in ('1600910513', 'DISTINCT001', 'CLIPPED0001', 'MISSING0001'):
            self.assertIn(asin, written)

    def test_the_two_shapes_are_told_apart_end_to_end(self):
        """Same stored List_at; since version 3 only the distinct one keeps it."""
        self._run(['--limit', '10'])
        written = self._detail()
        self.assertNotIn('"classification": "{}"'.format(audit.CLASS_MODE_SHARED), written)
        self.assertIn(audit.CLASS_MODE_DISTINCT, written)
        # Both now capped by the $90.00 peak-window New price + $3.99.
        self.assertIn('"recomputed_list_at": 93.99', written)

    def test_a_row_keepa_does_not_return_is_recorded_not_dropped(self):
        self._run(['--limit', '10'])
        self.assertIn('Keepa returned no product', self._detail())

    def test_the_overstatement_is_measured_against_the_peak_window(self):
        """$375.66 against the $90.00 New price in its own peak month."""
        self._run(['--limit', '10'])
        written = self._detail()
        self.assertIn('"peak_new_floor": 90.0', written)
        self.assertIn('"overstatement": 285.66', written)

    def test_a_clipped_row_reports_the_ceiling_and_its_basis(self):
        self._run(['--limit', '10'])
        written = self._detail()
        self.assertIn('"ceiling_basis": "avg365"', written)
        self.assertIn('"ceiling_blends_seasons": true', written)
        self.assertIn('"ceiling_matches_production": true', written)

    def test_a_clipped_row_does_not_count_as_the_duplicate_setting_the_price(self):
        self._run(['--limit', '10'])
        self.assertIn('ceiling did not overwrite it 0', self._detail())

    def test_tokens_are_accumulated_from_keepas_own_figure(self):
        self._run(['--limit', '10'])
        self.assertIn('Keepa tokens consumed: **28**', self._detail())

    def test_it_reserves_before_fetching_and_reconciles_after(self):
        _, calls = self._run(['--limit', '10'])
        self.assertIn(('reserve', audit.DEFAULT_RESERVE_PER_ASIN * 4), calls)
        self.assertIn(('reconcile', 300.0), calls)

    def test_it_fetches_with_the_heavy_path_parameters(self):
        _, calls = self._run(['--limit', '10'])
        fetches = [c for c in calls if isinstance(c[0], list)]
        self.assertEqual(len(fetches), 1, 'four rows fit in one batch of five')
        self.assertEqual(fetches[0][1], {'days': 365, 'history': 1, 'offers': 20})

    def test_batching_splits_the_sample(self):
        _, calls = self._run(['--limit', '10', '--batch-size', '2'])
        fetches = [c for c in calls if isinstance(c[0], list)]
        self.assertEqual([len(f[0]) for f in fetches], [2, 2])

    def test_named_asins_skip_the_sample(self):
        _, calls = self._run(['--asin', 'DISTINCT001'])
        fetches = [c for c in calls if isinstance(c[0], list)]
        self.assertEqual(fetches[0][0], ['DISTINCT001'])

    def test_nothing_was_written_to_the_database(self):
        before = os.path.getmtime(self.db_path)
        self._run(['--limit', '10'])
        con = sqlite3.connect(self.db_path)
        try:
            rows = con.execute('SELECT List_at FROM deals ORDER BY ASIN').fetchall()
        finally:
            con.close()
        # ASIN order: 1600910513, CLIPPED0001, DISTINCT001, MISSING0001.
        self.assertEqual([r[0] for r in rows], [375.66, 180.0, 375.66, 200.0])
        self.assertEqual(os.path.getmtime(self.db_path), before)


class TheDetailFileCarriesEveryRow(_Silent):

    def setUp(self):
        super().setUp()
        self.out_path = os.path.join(REPO_ROOT, 'test_audit_detail.md')

    def tearDown(self):
        if os.path.exists(self.out_path):
            os.remove(self.out_path)
        super().tearDown()

    def test_every_sampled_row_appears(self):
        rows = [_row('ASIN%06d' % n) for n in range(30)]
        audit.write_detail(rows, self.out_path, ['summary'], 210, 'cmd')
        with open(self.out_path, encoding='utf-8') as fh:
            written = fh.read()
        for row in rows:
            self.assertIn(row['ASIN'], written)

    def test_it_says_the_ai_check_was_stubbed(self):
        audit.write_detail([_row('ASIN000001')], self.out_path, ['s'], 7, 'cmd')
        with open(self.out_path, encoding='utf-8') as fh:
            written = fh.read()
        self.assertIn('stubbed', written)
        self.assertIn('Keepa tokens consumed', written)


if __name__ == '__main__':
    unittest.main()


# --------------------------------------------------------------------------
# --hidden-v3: why did the current logic withhold a price?
# --------------------------------------------------------------------------

class TheHiddenV3SelectionAndSplit(_Silent):
    """The pricing path does not record why it withheld a price: a thin peak
    season and an AI "No" both stamp the current version and leave List_at NULL.
    `--hidden-v3` re-runs production (AI stubbed True) on exactly those rows and
    ends stdout with the split."""

    def setUp(self):
        super().setUp()
        from keepa_deals.pricing_version import PRICING_LOGIC_VERSION
        v = PRICING_LOGIC_VERSION
        self.db_path = os.path.join(REPO_ROOT, 'test_audit_hidden.db')
        self.out_dir = os.path.join(REPO_ROOT, 'test_audit_hidden_out')
        con = sqlite3.connect(self.db_path)
        con.execute('CREATE TABLE deals (ASIN TEXT, List_at REAL, "1yr_Avg" TEXT, '
                    'Price_Now REAL, Inferred_Sale_Count INTEGER, '
                    '"Pricing_Logic_Version" INTEGER, Title TEXT, Profit REAL)')
        con.executemany(
            'INSERT INTO deals VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
            [('HIDNULL001', None, '148.60', 20.0, 21, v, 'Null', None),
             ('HIDZERO001', 0.0, '50.00', 20.0, 3, v, 'Zero', None),
             ('ONESALE001', None, '50.00', 20.0, 1, v, 'One sale', None),
             ('PRICED0001', 120.0, '90.00', 20.0, 9, v, 'Priced', 30.0),
             ('STALE00001', None, '90.00', 20.0, 9, v - 1, 'Old logic', None),
             ('UNVERIF001', None, '90.00', 20.0, 9, None, 'Unverified', None)])
        con.commit()
        con.close()

    def tearDown(self):
        for suffix in ('', '-wal', '-shm'):
            if os.path.exists(self.db_path + suffix):
                os.remove(self.db_path + suffix)
        if os.path.isdir(self.out_dir):
            for name in os.listdir(self.out_dir):
                os.remove(os.path.join(self.out_dir, name))
            os.rmdir(self.out_dir)
        super().tearDown()

    def test_it_selects_current_version_withheld_rows_with_two_plus_sales(self):
        rows = audit.fetch_sample(self.db_path, 100, hidden_v3=True)
        self.assertEqual([r['ASIN'] for r in rows], ['HIDNULL001', 'HIDZERO001'])

    def test_the_limit_still_bounds_it(self):
        self.assertEqual(len(audit.fetch_sample(self.db_path, 1, hidden_v3=True)), 1)

    def test_the_split(self):
        rows = [_row('THIN000001', season_points_window=1, recomputed_list_at=None),
                _row('THIN000002', season_points_window=None, recomputed_list_at=None),
                _row('AINO000001', season_points_window=6, recomputed_list_at=24.82),
                _row('OVER150001', season_points_window=4, recomputed_list_at=None),
                {'ASIN': 'FAILED0001', 'error': 'Keepa returned no product'}]
        lines = audit.withheld_split_lines(rows)
        self.assertIn('thin (< 2 points in peak +/-1): 2', lines[0])
        self.assertIn('AI No: 1', lines[0])
        self.assertIn('other: 1', lines[0])
        self.assertIn('failed: 1', lines[0])
        self.assertEqual(lines[1], '  AI No: AINO000001')
        self.assertEqual(lines[2], '  other: OVER150001')

    def test_end_to_end_the_split_ends_stdout(self):
        import io
        import keepa_deals.keepa_api as keepa_api
        import keepa_deals.token_manager as token_manager

        product = build_history(share_the_point=False, asin='HIDNULL001')

        def fake_fetch(api_key, asins, **kwargs):
            found = [product] if 'HIDNULL001' in asins else []
            return {'products': found}, {}, 7 * len(asins), 300.0

        class FakeTokenManager:
            REFILL_RATE_PER_MINUTE = 25.0
            tokens = 300.0

            def __init__(self, api_key):
                pass

            def should_skip_sync(self):
                return True

            def request_permission_for_call(self, cost):
                pass

            def update_after_call(self, tokens_left):
                pass

        out = io.StringIO()
        with patch.dict(os.environ, {'KEEPA_API_KEY': 'test-key'}), \
                patch.object(keepa_api, 'fetch_product_batch', fake_fetch), \
                patch.object(token_manager, 'TokenManager', FakeTokenManager), \
                patch.object(logging, 'basicConfig'), \
                patch('sys.stdout', out), patch('sys.stderr'):
            code = audit.main(['--db', self.db_path, '--out-dir', self.out_dir,
                               '--hidden-v3', '--limit', '100'])
        self.assertEqual(code, 0)
        lines = out.getvalue().strip().splitlines()
        split = [i for i, l in enumerate(lines) if l.startswith('WITHHELD SPLIT')]
        self.assertEqual(len(split), 1)
        self.assertIn('2 rows', lines[split[0]])
        self.assertIn('AI No: 1', lines[split[0]])
        self.assertIn('failed: 1', lines[split[0]])
        self.assertEqual(lines[-1], '  AI No: HIDNULL001')
