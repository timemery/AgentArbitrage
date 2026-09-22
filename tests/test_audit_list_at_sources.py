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


def build_history(share_the_point=True, asin='AUDITFIXT'):
    """Eleven confirmed sales, the peak month holding a duplicated price.

    `share_the_point=True` places ONE price point before the last two drops, so
    both backward matches land on it - the 1600910513 shape. `False` places two
    separate points holding the SAME price, which is ordinary repricing and must
    be classified differently.
    """
    # Peak month is the most recent one; 60-day spacing guarantees four distinct
    # calendar months whenever this runs.
    months = [_month_anchor(45), _month_anchor(105), _month_anchor(165),
              _month_anchor(225)]
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
    csv_data[2] = _flat(price_points)
    csv_data[3] = _flat(rank_points)
    csv_data[12] = _flat(offer_points)

    return {
        'asin': asin,
        'title': 'List at source fixture',
        'csv': csv_data,
        # Amazon absent on every index, exactly like 1600910513, so the 90%
        # ceiling cannot quietly move the number these tests assert on.
        'stats': {
            'current': [-1, -1, CURRENT_USED_CENTS, 500000] + [-1] * 19,
            'avg90': [-1] * 23, 'avg180': [-1] * 23, 'avg365': [-1] * 23,
        },
        'offers': [],
    }


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

    def test_list_at_is_the_duplicated_price(self):
        self.assertEqual(self.analysis['peak_price_mode_cents'], float(DUP_CENTS))

    def test_it_is_classified_as_mode_shared(self):
        detail = audit.classify_list_at(self.sales, self.analysis, self.sources)
        self.assertEqual(detail['classification'], audit.CLASS_MODE_SHARED)
        self.assertEqual(detail['mode_count'], 2)
        self.assertEqual(detail['contributing_count'] if 'contributing_count' in detail
                         else len(detail['contributing']), 2)
        self.assertEqual(detail['distinct_source_points'], 1)
        self.assertEqual(detail['shared_point_sales'], 1)
        self.assertTrue(detail['branch_matches_production'],
                        'the reconstruction must agree with the production value '
                        'before any duplicate finding is trusted')

    def test_removing_the_duplicate_lowers_list_at(self):
        """The counterfactual, run through the production function again."""
        deduped = audit.dedupe_by_source_point(self.sales, self.sources)
        self.assertEqual(len(deduped), 10)

        after, _ = audit.analyse_without_xai(self.product, deduped)
        self.assertEqual(after['peak_price_mode_cents'], float(PEAK_OTHER[0]))
        self.assertLess(after['peak_price_mode_cents'],
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
        self.assertEqual(detail['classification'], audit.CLASS_MODE_DISTINCT)


# --------------------------------------------------------------------------
# (b) The lowest current New offer
# --------------------------------------------------------------------------

def _offer(condition, item_cents, shipping_cents, is_fba=False, seller='S1', age_days=1):
    moment = _ktm(datetime.now() - timedelta(days=age_days))
    return {'condition': condition, 'isFBA': is_fba, 'sellerId': seller,
            'offerCSV': [moment, item_cents, shipping_cents]}


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
        'classification': audit.CLASS_MODE_SHARED, 'branch_matches_production': True,
        'dedup_changes_list_at': True, 'dedup_list_at': 300.0,
        'new_landed': 78.98, 'overstatement': 321.02, 'error': None,
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
             ('MISSING0001', 200.00, '180.00', 40.00, 4, 2, 'Keepa drops it', 60.0)])
        con.commit()
        con.close()

        shared = build_history(share_the_point=True, asin='1600910513')
        shared['offers'] = [_offer(1, 7499, 399, seller='A')]
        distinct = build_history(share_the_point=False, asin='DISTINCT001')
        distinct['offers'] = [_offer(1, 44900, -1, is_fba=True, seller='B')]
        self.products = {p['asin']: p for p in (shared, distinct)}

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
        for asin in ('1600910513', 'DISTINCT001', 'MISSING0001'):
            self.assertIn(asin, written)

    def test_the_two_shapes_are_told_apart_end_to_end(self):
        """Same stored List_at, same recomputed value, different cause."""
        self._run(['--limit', '10'])
        written = self._detail()
        self.assertIn(audit.CLASS_MODE_SHARED, written)
        self.assertIn(audit.CLASS_MODE_DISTINCT, written)

    def test_a_row_keepa_does_not_return_is_recorded_not_dropped(self):
        self._run(['--limit', '10'])
        self.assertIn('Keepa returned no product', self._detail())

    def test_tokens_are_accumulated_from_keepas_own_figure(self):
        self._run(['--limit', '10'])
        self.assertIn('Keepa tokens consumed: **21**', self._detail())

    def test_it_reserves_before_fetching_and_reconciles_after(self):
        _, calls = self._run(['--limit', '10'])
        self.assertIn(('reserve', audit.DEFAULT_RESERVE_PER_ASIN * 3), calls)
        self.assertIn(('reconcile', 300.0), calls)

    def test_it_fetches_with_the_heavy_path_parameters(self):
        _, calls = self._run(['--limit', '10'])
        fetches = [c for c in calls if isinstance(c[0], list)]
        self.assertEqual(len(fetches), 1, 'three rows fit in one batch of five')
        self.assertEqual(fetches[0][1], {'days': 365, 'history': 1, 'offers': 20})

    def test_batching_splits_the_sample(self):
        _, calls = self._run(['--limit', '10', '--batch-size', '2'])
        fetches = [c for c in calls if isinstance(c[0], list)]
        self.assertEqual([len(f[0]) for f in fetches], [2, 1])

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
        # ASIN order: 1600910513, DISTINCT001, MISSING0001.
        self.assertEqual([r[0] for r in rows], [375.66, 375.66, 200.0])
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
