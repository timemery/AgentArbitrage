"""Tests for diagnose_inferred_sales.py.

The diagnostic is read-only and changes no pricing behaviour, but it makes two
claims that would be worse than useless if they stopped being true:

1.  Its correlation loop MIRRORS `infer_sale_events`. It re-implements rather than
    calls. The original reason was that `infer_sale_events` invoked xAI on both of
    its zero-sale branches, which would have spent budget and hidden the very
    mechanism the diagnostic exists to expose; that rescue was removed on
    2026-09-16 (Trello #141), but re-implementing still buys the per-stage printout
    that calling the function cannot give. Its own docstring says KEEP IN SYNC;
    `MirrorsProduction` is what makes that enforceable instead of aspirational. A
    drifted mirror does not fail loudly, it prints a confident wrong answer.

2.  Its PRICE STEP-UP TEST accounts for the leftover-asking-price mechanism.
    `StepUpDetection` builds a history where a copy demonstrably sells at $28.99 and
    the used floor steps up to $499.95 at the same timestamp. Production now records
    $28.99; the diagnostic still reports what the pre-fix nearest-match would have
    stored, because rows written before the fix carry that value and explaining a
    stored number is the script's whole job.

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
        confirmed, rejected, legacy_only = (
            D.confirm_sales(drops, product['csv'], window)
            if total else ([], [], []))
        sane = D.sanitise(confirmed)
    return {'total_drops': total, 'confirmed': confirmed, 'sane': sane,
            'legacy_only': legacy_only, 'output': buf.getvalue()}


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

    def test_production_records_the_sale_price_not_the_asking_price(self):
        """The defect, now fixed, stated as an executable fact.

        A copy sold at $28.99 and the used floor stepped up to $499.95 at the same
        timestamp. Production used to store $499.95 - the price of a copy that did
        NOT sell. It now stores $28.99, the price in force strictly before the drop.

        The fixture is unchanged; only the expectation flipped. The full set of
        association cases lives in `tests/test_price_association.py`.
        """
        product = _step_up_product()
        events, _ = infer_sale_events(product)
        self.assertEqual(len(events), 1)
        self.assertEqual(int(events[0]['inferred_sale_price_cents']),
                         SOLD_AT_CENTS,
                         "The price in force before the drop is what the copy sold "
                         "at.")
        self.assertNotEqual(int(events[0]['inferred_sale_price_cents']),
                            NEXT_LISTING_CENTS,
                            "Fixture no longer reproduces the step-up shape.")

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
        self.assertEqual(int(sale['inferred_sale_price_cents']), SOLD_AT_CENTS,
                         "The association records the 'before' price.")
        self.assertTrue(sale['legacy_chose_at_or_after'],
                        "The pre-fix nearest-match landed on the at/after side in "
                        "this fixture, which is why it is still reported.")
        self.assertEqual(int(sale['legacy_nearest_cents']), NEXT_LISTING_CENTS,
                         "'old would' must be what a pre-fix row carries.")
        self.assertEqual(sale['series'], 'csv[2] Used')

    def test_ordinary_history_is_not_flagged(self):
        """No false positive when the price does not step."""
        result = _run_diagnostic(_plain_product(sales_count=4))
        self.assertNotIn('STEP-UP SUSPECT', result['output'])
        self.assertIn('No sale matches the step-up signature', result['output'])


class ReadOnlyGuarantees(unittest.TestCase):
    """The promises in the module docstring, checked rather than trusted."""

    def test_makes_no_xai_call_while_analysing(self):
        """The diagnostic must reach a zero-sale state without spending xAI budget.

        This was originally the reason the correlation loop is re-implemented by
        hand rather than calling `infer_sale_events`: that function called
        `infer_sales_with_xai` on both of its zero-sale branches. The rescue was
        removed on 2026-09-16 (Trello #141), so the hazard is gone, but the
        guarantee in the module docstring still stands and is still worth checking
        - nothing here may reach xAI by any route.

        `stable_calculations` no longer binds the name, so it is patched only if
        present; asserting on a patch target that this PR deliberately removed
        would test the wrong thing.
        """
        from unittest.mock import patch
        import keepa_deals.stable_calculations as sc
        product = _plain_product(sales_count=0)
        with patch('keepa_deals.xai_sales_inference.infer_sales_with_xai') as xai, \
             patch('keepa_deals.xai_sales_inference.query_xai_sales_inference') as net:
            if hasattr(sc, 'infer_sales_with_xai'):
                with patch.object(sc, 'infer_sales_with_xai') as legacy:
                    _run_diagnostic(product)
                legacy.assert_not_called()
            else:
                _run_diagnostic(product)
        xai.assert_not_called()
        net.assert_not_called()

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


# The live case this class exists for. ASIN 0415009804, run 2026-09-16 with
# --stored-price 500.00. The step-up table reported 'old would' $500.00 on sale 1
# and $-0.01 on sale 2; today's code recomputes $223.75.
PREFIX_STORED_USD = 500.00
PREFIX_LEGACY_ONE_CENTS = 50000     # 'old would' on sale 1
PREFIX_LEGACY_TWO_CENTS = -1        # 'old would' on sale 2: Keepa's "no offer"
PREFIX_TODAY_ONE_CENTS = 20000      # what today's association takes on sale 1
PREFIX_TODAY_TWO_CENTS = 24750      # ...and on sale 2; median 223.75


class PreFixReconstruction(unittest.TestCase):
    """`recompute` must compute the ORDINARY cause before naming an exotic one.

    THE DEFECT, 2026-09-16, ASIN 0415009804. With --stored-price 500.00 the script
    recomputed $223.75 and concluded "Either the history moved, or the stored value
    came from the xAI rescue path". Neither was true. The stored $500.00 is exactly
    what the pre-fix code would have produced: its nearest-match took $500.00 on
    sale 1 and $-0.01 on sale 2, the `price <= 0` guard discarded the second, and a
    single remaining sale goes down the sparse branch and stores its median.

    This is the same class of error as the `check_stored_price` fix of 2026-09-11,
    which blamed xAI for a value that was just the mean of two real prices. Both
    named an exotic cause without first computing the boring one.
    """

    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    @staticmethod
    def _confirmed(today_cents, legacy_cents, days_ago):
        """One rank-confirmed sale, as `confirm_sales` emits it."""
        return {
            'event_timestamp': datetime.now() - timedelta(days=days_ago),
            'inferred_sale_price_cents': today_cents,
            'offer_type': 'Used',
            'series': 'csv[2] Used',
            'how': 'direct rank drop within 240h',
            'price_before_cents': today_cents,
            'price_after_cents': legacy_cents,
            'legacy_nearest_cents': legacy_cents,
            'legacy_chose_at_or_after': True,
        }

    def _live_case(self):
        return [
            self._confirmed(PREFIX_TODAY_ONE_CENTS, PREFIX_LEGACY_ONE_CENTS, 120),
            self._confirmed(PREFIX_TODAY_TWO_CENTS, PREFIX_LEGACY_TWO_CENTS, 60),
        ]

    def _run_recompute(self, confirmed, legacy_only=None, stored_usd=None):
        sane = [{'event_timestamp': c['event_timestamp'],
                 'inferred_sale_price_cents': c['inferred_sale_price_cents']}
                for c in confirmed]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            D.recompute(sane, 2999, stored_usd, confirmed=confirmed,
                        legacy_only=legacy_only or [])
        return buf.getvalue()

    # --- the reconstruction itself -------------------------------------------

    def test_the_non_positive_legacy_price_is_discarded(self):
        """The pre-fix `price <= 0` guard is what leaves one sale standing."""
        prefix = D.reconstruct_prefix_value(self._live_case(), [])
        self.assertEqual(len(prefix['kept']), 1)
        self.assertEqual(prefix['kept'][0]['inferred_sale_price_cents'],
                         float(PREFIX_LEGACY_ONE_CENTS))
        self.assertEqual(len(prefix['dropped']), 1)
        self.assertIn('price <= 0', prefix['dropped'][0][2])

    def test_one_surviving_sale_takes_the_sparse_median(self):
        prefix = D.reconstruct_prefix_value(self._live_case(), [])
        self.assertAlmostEqual(prefix['list_at_cents'],
                               float(PREFIX_LEGACY_ONE_CENTS))
        self.assertIn('SPARSE', prefix['list_at_branch'])

    def test_a_drop_today_discards_on_price_still_counts_pre_fix(self):
        """A rank-confirmed drop today's code cannot price still had a pre-fix price.

        Leaving these out would under-count the pre-fix set and could report "no
        match" for a row that is in fact fully explained.
        """
        legacy_only = [{
            'event_timestamp': datetime.now() - timedelta(days=90),
            'offer_type': 'Used',
            'series': 'csv[2] Used',
            'legacy_nearest_cents': 50000,
            'dropped_today_because': 'no price point exists before the drop',
        }]
        prefix = D.reconstruct_prefix_value(self._live_case(), legacy_only)
        self.assertEqual(len(prefix['kept']), 2)
        self.assertAlmostEqual(prefix['list_at_cents'], 50000.0)

    # --- the conclusion ------------------------------------------------------

    def test_a_pre_fix_row_is_named_as_such_and_not_blamed_on_xai(self):
        """The whole point. This is what the 0415009804 run should have printed."""
        out = self._run_recompute(self._live_case(),
                                  stored_usd=PREFIX_STORED_USD)
        self.assertIn('DIFFERS FROM', out,
                      "Today's code must still be reported as not reproducing it.")
        self.assertIn('THIS ROW PREDATES THE PRICE-ASSOCIATION FIX', out)
        self.assertIn('HEAVY RE-FETCH', out)
        self.assertNotIn('the history moved since the row was written', out)
        self.assertNotIn('came from the xAI rescue path', out)

    def test_the_reconstruction_is_shown_not_just_asserted(self):
        """The reader must be able to check the arithmetic, per the 09-11 lesson."""
        out = self._run_recompute(self._live_case(),
                                  stored_usd=PREFIX_STORED_USD)
        self.assertIn("WHAT THE PRE-FIX CODE WOULD HAVE PRODUCED", out)
        self.assertIn('DISCARDED', out)
        self.assertIn('Pre-fix List at', out)

    def test_xai_and_drift_are_named_only_when_nothing_explains_the_value(self):
        """The escape hatch must still exist, and must still be conditional."""
        out = self._run_recompute(self._live_case(), stored_usd=987.65)
        self.assertIn('matches NEITHER', out)
        self.assertIn('came from the xAI rescue path', out)
        self.assertIn('the history moved since the row was written', out)
        self.assertNotIn('THIS ROW PREDATES', out)

    def test_a_value_todays_code_reproduces_draws_no_conclusion_at_all(self):
        """No reconstruction, no blame: today's code already explains it."""
        out = self._run_recompute(self._live_case(), stored_usd=223.75)
        self.assertIn('MATCHES', out)
        self.assertNotIn('THIS ROW PREDATES', out)
        self.assertNotIn('came from the xAI rescue path', out)
        self.assertNotIn('WHAT THE PRE-FIX CODE WOULD HAVE PRODUCED', out)

    def test_a_stored_one_year_average_is_matched_too(self):
        """--stored-price may be the 1yr Avg rather than List at.

        Two pre-fix sales inside 365 days: List at is their median, 1yr Avg their
        mean. With two values those coincide, so this fixture uses three so the
        mean and the median differ and the match is unambiguous.
        """
        confirmed = [
            self._confirmed(10000, 10000, 300),
            self._confirmed(10000, 20000, 200),
            self._confirmed(10000, 60000, 100),
        ]
        prefix = D.reconstruct_prefix_value(confirmed, [])
        self.assertAlmostEqual(prefix['yr_avg_cents'], 30000.0)
        out = self._run_recompute(confirmed, stored_usd=300.00)
        self.assertIn('THIS ROW PREDATES THE PRICE-ASSOCIATION FIX', out)
        self.assertIn('1yr Avg', out)
