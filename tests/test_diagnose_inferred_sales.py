"""Tests for diagnose_inferred_sales.py.

The diagnostic is read-only and changes no pricing behaviour, but it makes two
claims that would be worse than useless if they stopped being true:

1.  Its correlation loop MIRRORS `infer_sale_events`. It re-implements rather than
    calls, because `infer_sale_events` invokes xAI on both of its zero-sale
    branches. Its own docstring says KEEP IN SYNC; `MirrorsProduction` is what makes
    that enforceable instead of aspirational. A drifted mirror does not fail loudly,
    it prints a confident wrong answer.

2.  Its PRICE STEP-UP TEST detects the leftover-asking-price mechanism.
    `StepUpDetection` builds a history where a copy demonstrably sells at $28.99 and
    asserts that production records $499.95 for it, then that the diagnostic flags
    exactly that.

Nothing here touches the network, xAI, deals.db or any cache.
"""

import contextlib
import io
import logging
import os
import sys
import unittest
from datetime import datetime, timedelta

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import diagnose_inferred_sales as D  # noqa: E402
from keepa_deals.stable_calculations import (  # noqa: E402
    KEEPA_EPOCH,
    infer_sale_events,
)

# The cheapest copy is listed at $28.99. The next cheapest asks $499.95 - a price a
# seller typed, which is why the values seen on the box are round.
SOLD_AT_CENTS = 2899
NEXT_LISTING_CENTS = 49995


def _flat(times, values):
    out = []
    for t, v in zip(times, values):
        out.extend([t, v])
    return out


def _history(history_days=400, step_hours=6):
    now = datetime.now()
    timestamps = []
    for i in range(0, history_days * 24, step_hours):
        ts = now - timedelta(hours=i)
        timestamps.append(int((ts - KEEPA_EPOCH).total_seconds() / 60))
    timestamps.reverse()
    return now, timestamps


def _index_for(timestamps, now, days_ago):
    target = int(((now - timedelta(days=days_ago)) - KEEPA_EPOCH).total_seconds() / 60)
    for i, ts in enumerate(timestamps):
        if ts >= target:
            return i
    return len(timestamps) - 1


def _step_up_product(sale_days_ago=100, history_days=400):
    """A history where the lowest-used series steps UP at the moment of the sale.

    This is the real Keepa shape, not a contrivance: csv[2] is the LOWEST used offer
    price across all sellers, so when the cheapest copy is bought the series jumps to
    whatever the next cheapest seller is asking. The offer count drops and the rank
    improves at the same moment, which is exactly what the inference looks for.
    """
    now, timestamps = _history(history_days)
    n = len(timestamps)
    ranks = [100000] * n
    new_prices = [3500] * n
    used_prices = [SOLD_AT_CENTS] * n
    new_counts = [5] * n
    used_counts = [5] * n

    idx = _index_for(timestamps, now, sale_days_ago)
    used_counts[idx] = 4                       # a copy sold
    for j in range(idx, n):                    # ...and the floor steps up
        used_prices[j] = NEXT_LISTING_CENTS
    ranks[idx + 1] = 50000                     # Amazon registers the sale

    csv_data = [None] * 13
    csv_data[1] = _flat(timestamps, new_prices)
    csv_data[2] = _flat(timestamps, used_prices)
    csv_data[3] = _flat(timestamps, ranks)
    csv_data[11] = _flat(timestamps, new_counts)
    csv_data[12] = _flat(timestamps, used_counts)

    return {
        'asin': 'STEPUPTEST',
        'title': 'Step-up fixture',
        'csv': csv_data,
        'stats': {'current': [-1, -1, SOLD_AT_CENTS, 500000] + [-1] * 19,
                  'avg180': [-1] * 23, 'avg365': [-1] * 23},
    }


def _plain_product(sales_count=4, sale_days_ago=100, history_days=400,
                   price_cents=1500):
    """A history with no price step, for the mirror comparison."""
    now, timestamps = _history(history_days)
    n = len(timestamps)
    ranks = [100000] * n
    used_counts = [5] * n

    start = _index_for(timestamps, now, sale_days_ago)
    for i in range(sales_count):
        idx = start + (i * 4)
        if idx + 1 < n:
            used_counts[idx] = 4 - i
            ranks[idx + 1] = 50000

    csv_data = [None] * 13
    csv_data[1] = _flat(timestamps, [2000] * n)
    csv_data[2] = _flat(timestamps, [price_cents] * n)
    csv_data[3] = _flat(timestamps, ranks)
    csv_data[11] = _flat(timestamps, [5] * n)
    csv_data[12] = _flat(timestamps, used_counts)
    return {'asin': 'MIRRORTEST', 'title': 'Mirror fixture', 'csv': csv_data,
            'stats': {'current': [-1] * 23, 'avg180': [-1] * 23,
                      'avg365': [-1] * 23}}


def _run_diagnostic(product):
    """Drive the diagnostic's analysis stages, capturing its printed output."""
    window = datetime.now() - timedelta(days=D.HISTORY_WINDOW_DAYS)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        drops, total = D.find_offer_drops(product['csv'], window)
        confirmed, rejected = (D.confirm_sales(drops, product['csv'], window)
                               if total else ([], []))
        sane = D.sanitise(confirmed)
    return {'total_drops': total, 'confirmed': confirmed, 'sane': sane,
            'output': buf.getvalue()}


class MirrorsProduction(unittest.TestCase):
    """The re-implemented loop must agree with infer_sale_events, or it lies."""

    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def _assert_agrees(self, product):
        prod_events, prod_drops = infer_sale_events(product)
        result = _run_diagnostic(product)
        self.assertEqual(
            result['total_drops'], prod_drops,
            "Offer-drop count diverged. That is the Deal Trust denominator.")
        self.assertEqual(
            sorted(int(e['inferred_sale_price_cents']) for e in prod_events),
            sorted(int(c['inferred_sale_price_cents']) for c in result['sane']),
            "Sale prices diverged from production. The diagnostic mirrors "
            "infer_sale_events by hand; re-sync it before trusting its output.")

    def test_agrees_on_a_multi_sale_history(self):
        self._assert_agrees(_plain_product(sales_count=4))

    def test_agrees_on_a_sparse_history(self):
        self._assert_agrees(_plain_product(sales_count=2))

    def test_agrees_on_sales_older_than_a_year(self):
        self._assert_agrees(
            _plain_product(sales_count=4, sale_days_ago=400, history_days=500))

    def test_agrees_on_the_step_up_history(self):
        self._assert_agrees(_step_up_product())


class StepUpDetection(unittest.TestCase):
    """The leftover-asking-price mechanism, demonstrated and then detected."""

    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_production_records_the_asking_price_not_the_sale_price(self):
        """The defect itself, stated as an executable fact.

        A copy sold at $28.99. Production stores $499.95 for it - the price of a copy
        that did NOT sell. This test documents current behaviour; it is NOT a request
        to change it, and no pricing code was touched in this PR.
        """
        product = _step_up_product()
        events, _ = infer_sale_events(product)
        self.assertEqual(len(events), 1)
        self.assertEqual(int(events[0]['inferred_sale_price_cents']),
                         NEXT_LISTING_CENTS,
                         "Fixture no longer reproduces the step-up mechanism.")
        self.assertNotEqual(int(events[0]['inferred_sale_price_cents']),
                            SOLD_AT_CENTS)

    def test_diagnostic_flags_the_step_up(self):
        result = _run_diagnostic(_step_up_product())
        out = result['output']
        self.assertIn('PRICE STEP-UP TEST', out)
        self.assertIn('STEP-UP SUSPECT', out,
                      "The diagnostic must flag the very pattern it was added for.")
        self.assertIn('1 of 1 sale(s) match the step-up signature', out)

    def test_before_and_after_are_captured_from_the_same_series(self):
        result = _run_diagnostic(_step_up_product())
        sale = result['confirmed'][0]
        self.assertEqual(int(sale['price_before_cents']), SOLD_AT_CENTS,
                         "'before' must be the price the copy actually sold at.")
        self.assertEqual(int(sale['price_after_cents']), NEXT_LISTING_CENTS,
                         "'after' must be the next listing's asking price.")
        self.assertTrue(sale['chose_at_or_after'],
                        "merge_asof landed on the at/after side in this fixture.")
        self.assertEqual(sale['series'], 'csv[2] Used')

    def test_ordinary_history_is_not_flagged(self):
        """No false positive when the price does not step."""
        result = _run_diagnostic(_plain_product(sales_count=4))
        self.assertNotIn('STEP-UP SUSPECT', result['output'])
        self.assertIn('No sale matches the step-up signature', result['output'])


class ReadOnlyGuarantees(unittest.TestCase):
    """The promises in the module docstring, checked rather than trusted."""

    def test_makes_no_xai_call_while_analysing(self):
        """The reason the loop is re-implemented at all.

        infer_sale_events calls infer_sales_with_xai on both zero-sale branches. The
        diagnostic must reach the same zero-sale state without doing so.
        """
        from unittest.mock import patch
        product = _plain_product(sales_count=0)
        with patch('keepa_deals.xai_sales_inference.infer_sales_with_xai') as xai, \
             patch('keepa_deals.stable_calculations.infer_sales_with_xai') as xai2:
            _run_diagnostic(product)
        xai.assert_not_called()
        xai2.assert_not_called()

    def test_module_cannot_reach_the_database(self):
        """No sqlite3, no db_utils, no connection helper - checked in the source.

        'deals.db' does appear in the module, but only in the docstring saying it is
        never touched, so its presence is not what this asserts.
        """
        source = open(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '..',
            'diagnose_inferred_sales.py')).read()
        for forbidden in ('sqlite3', 'db_utils', 'get_db_connection'):
            self.assertNotIn(
                forbidden, source,
                "The diagnostic must not reach the database; found "
                "{!r} in its source.".format(forbidden))


class StoredPriceConclusion(unittest.TestCase):
    """The section that drew a wrong conclusion on a live ASIN, 2026-09-11.

    It reported that a value absent from the price history "points at an
    xAI-invented event". On ASIN 1429097078 that was wrong: the stored $699.11 is
    mean($699.99, $698.23), an average of two prices that ARE in the history. An
    average of real prices is usually not itself a real price, so absence proves
    nothing on its own.
    """

    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    @staticmethod
    def _history_without(target_cents, values, history_days=400):
        now, timestamps = _history(history_days)
        used = [values[i % len(values)] for i in range(len(timestamps))]
        assert target_cents not in used
        csv_data = [None] * 13
        csv_data[2] = _flat(timestamps, used)
        return now, csv_data

    def _run(self, csv_data, stored_usd, sane):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            D.check_stored_price(csv_data, stored_usd, sane)
        return buf.getvalue()

    def test_a_mean_absent_from_history_is_not_blamed_on_xai(self):
        """The 1429097078 case, reproduced."""
        now, csv_data = self._history_without(69911, [69999, 69823])
        sane = [
            {'event_timestamp': now - timedelta(days=173),
             'inferred_sale_price_cents': 69999},
            {'event_timestamp': now - timedelta(days=116),
             'inferred_sale_price_cents': 69823},
        ]
        out = self._run(csv_data, 699.11, sane)
        self.assertIn('NOT PRESENT', out)
        self.assertIn('MATCHES STORED', out)
        self.assertIn('COMPUTED average', out)
        self.assertNotIn('xAI is worth considering', out,
                         "A derivable value must never be attributed to xAI.")

    def test_xai_is_named_only_when_the_value_is_also_underivable(self):
        now, csv_data = self._history_without(12345, [2000, 2500])
        sane = [{'event_timestamp': now - timedelta(days=100),
                 'inferred_sale_price_cents': 2000}]
        out = self._run(csv_data, 123.45, sane)
        self.assertIn('not derivable', out)
        self.assertIn('xAI is worth considering', out)

    def test_a_price_present_in_history_short_circuits(self):
        now, timestamps = _history()
        csv_data = [None] * 13
        csv_data[2] = _flat(timestamps, [49995] * len(timestamps))
        out = self._run(csv_data, 499.95, [])
        self.assertIn('real historical listing price', out)
        self.assertNotIn('COMPUTED average', out)


if __name__ == '__main__':
    unittest.main()
