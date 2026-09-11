"""Regression tests for the removal of the `1yr. Avg.` Keepa Stats fallback.

Owner decision 2026-09-11, audit B-6: `1yr. Avg.` and `List at` may come only from
true inferred sales. No listing average, no Amazon price, no Keepa list price, no
default, ever.

WHY THESE ARE NOT COVERED BY `tests/test_1yr_avg_logic.py`
----------------------------------------------------------
That file already has `test_insufficient_data_old_sales`, which asserts None for
sales older than 365 days - and it passed on main, before the fallback was removed.
It passed for the wrong reason: its mock product has no `stats` key at all, so the
fallback bailed out at `if not stats: return None` without ever reaching the
`avg365` candidates. It therefore never exercised the fallback and could not detect
it.

Every mock here carries a fully populated `stats.avg365`, so the removed code would
have had something to return. `test_old_sales_with_stats_returns_none` and
`test_zero_sales_with_stats_returns_none` both FAIL on main (returning $88.00, the
max of the five condition tiers) and pass after the removal.

Also covers `Inferred_Sale_Count`, which is returned on every branch of
`analyze_sales_performance` so the caller can persist it even for a rejected deal.
"""

import logging
import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from _real_module import load as _load_real  # noqa: E402

from keepa_deals.new_analytics import get_1yr_avg_sale_price  # noqa: E402
from keepa_deals.stable_calculations import (  # noqa: E402
    KEEPA_EPOCH,
    analyze_sales_performance,
    infer_sale_events,
)

# The five Keepa avg365 condition tiers the removed fallback read, in cents.
# Straight from Worked Example 3 of Diagnostics/2026-09-09_Calculation_Audit.md:
# the doc promised index 2 ($31.00); the code returned max() ($88.00).
AVG365_USED = 3100
AVG365_LIKE_NEW = 8800
AVG365_VERY_GOOD = 6400
AVG365_GOOD = 4200
AVG365_ACCEPTABLE = 2900
FALLBACK_WOULD_HAVE_RETURNED = AVG365_LIKE_NEW / 100.0  # 88.00


def _stats_with_avg365():
    """A stats object rich enough that the removed fallback would have fired.

    Index 0 is Amazon, 1 New, 2 Used, 3 rank, then the Used condition tiers at
    19-22. Amazon is left at -1 so the Amazon ceiling never engages and cannot
    silently change a peak price these tests assert on.
    """
    avg365 = [-1] * 23
    avg365[2] = AVG365_USED
    avg365[19] = AVG365_LIKE_NEW
    avg365[20] = AVG365_VERY_GOOD
    avg365[21] = AVG365_GOOD
    avg365[22] = AVG365_ACCEPTABLE
    current = [-1] * 23
    current[2] = 2600  # $26.00 current used, as in the worked example
    current[3] = 500000
    return {'current': current, 'avg365': avg365, 'avg180': [-1] * 23,
            'avg90': [-1] * 23, 'avg30': [-1] * 23}


def _mock_product(history_days=500, sales_count=0, sales_age_days=None,
                  sale_price_cents=1500, with_stats=True, points_per_day=24):
    """Synthetic Keepa history with a controllable number of inferred sales.

    A sale is manufactured the way the production inference detects one: drop the
    used offer count at some index, then improve the rank at the next index, inside
    the 240-hour confirmation window.

    `points_per_day` trades fidelity for speed. The default 24 (hourly) matches
    `tests/test_1yr_avg_logic.py`. The end-to-end tests drop to 4 because
    `_process_single_deal` re-runs `infer_sale_events` several times per product
    (audit A-13) over the whole array, and an hourly 400-day history costs ~10
    seconds per call. The detection windows are all measured in days, so a 6-hourly
    grid exercises exactly the same branches.
    """
    now = datetime.now()
    step_hours = 24 // points_per_day
    timestamps, ranks, new_prices, used_prices, new_counts, used_counts = (
        [], [], [], [], [], [])

    for i in range(0, history_days * 24, step_hours):
        ts = now - timedelta(hours=i)
        timestamps.append(int((ts - KEEPA_EPOCH).total_seconds() / 60))
        ranks.append(100000)
        new_prices.append(2000)
        used_prices.append(sale_price_cents)
        new_counts.append(5)
        used_counts.append(5)

    for seq in (timestamps, ranks, new_prices, used_prices, new_counts, used_counts):
        seq.reverse()

    def idx_for(days_ago):
        target = int(((now - timedelta(days=days_ago)) - KEEPA_EPOCH)
                     .total_seconds() / 60)
        for i, ts in enumerate(timestamps):
            if ts >= target:
                return i
        return len(timestamps) - 1

    if sales_count > 0:
        start = idx_for(sales_age_days) if sales_age_days else len(timestamps) // 2
        for i in range(sales_count):
            idx = start + (i * points_per_day)  # one sale per day of history
            if idx + 1 < len(timestamps):
                used_counts[idx] = 4 - i
                ranks[idx + 1] = 50000

    def flat(times, vals):
        out = []
        for t, v in zip(times, vals):
            out.extend([t, v])
        return out

    csv_data = [None] * 13
    csv_data[1] = flat(timestamps, new_prices)
    csv_data[2] = flat(timestamps, used_prices)
    csv_data[3] = flat(timestamps, ranks)
    csv_data[11] = flat(timestamps, new_counts)
    csv_data[12] = flat(timestamps, used_counts)

    product = {'asin': 'TESTFALLBK', 'csv': csv_data, 'title': 'Test Book'}
    if with_stats:
        product['stats'] = _stats_with_avg365()
    return product


class NoListingAverageFallback(unittest.TestCase):
    """The core B-6 contract."""

    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_old_sales_with_stats_returns_none(self):
        """Sales exist, all older than 365 days, avg365 fully populated.

        FAILS ON MAIN: the fallback returned max(avg365[2,19,20,21,22]) = $88.00.
        This is the exact shape of Worked Example 3 in the audit.
        """
        product = _mock_product(history_days=500, sales_count=4, sales_age_days=400)

        events, _ = infer_sale_events(product)
        self.assertGreater(
            len(events), 0,
            "Fixture is wrong: the inference must find sales, just old ones. "
            "Without them this would pass for the trivial reason instead."
        )
        year_ago = datetime.now() - timedelta(days=365)
        self.assertTrue(
            all(e['event_timestamp'] < year_ago for e in events),
            "Fixture is wrong: every inferred sale must be older than 365 days."
        )

        result = get_1yr_avg_sale_price(product)
        self.assertIsNone(
            result,
            "Sales outside 365 days must yield None. Got {!r}. If this is "
            "{:.2f}, a listing-average fallback has been reintroduced."
            .format(result, FALLBACK_WOULD_HAVE_RETURNED)
        )

    def test_zero_sales_with_stats_returns_none(self):
        """No inferred sale at all, avg365 fully populated.

        FAILS ON MAIN for the same reason. Patches the xAI rescue off so the test
        exercises the fallback branch rather than the network.
        """
        product = _mock_product(history_days=500, sales_count=0)
        with patch('keepa_deals.stable_calculations.infer_sales_with_xai',
                   return_value=None):
            result = get_1yr_avg_sale_price(product)
        self.assertIsNone(
            result,
            "Zero inferred sales must yield None, not an estimate. Got {!r}."
            .format(result)
        )

    def test_never_returns_a_price_source_flag(self):
        """The contract that kept processing.py's 'Low (Est.)' branch alive.

        The branch fired on `price_source == 'Keepa Stats Fallback'`, and this
        function was the only producer of that flag. Asserting the key is never
        returned is what makes removing the branch safe, and it fails loudly if a
        future change reintroduces a flagged estimate.
        """
        cases = [
            _mock_product(history_days=500, sales_count=4, sales_age_days=400),
            _mock_product(history_days=400, sales_count=4, sales_age_days=100),
        ]
        with patch('keepa_deals.stable_calculations.infer_sales_with_xai',
                   return_value=None):
            for product in cases:
                result = get_1yr_avg_sale_price(product)
                if result is not None:
                    self.assertNotIn(
                        'price_source', result,
                        "get_1yr_avg_sale_price must not flag a price source; "
                        "the only flag it ever set was the removed fallback."
                    )

    def test_recent_sales_still_produce_a_value(self):
        """Guard against over-correcting: real recent sales must still compute."""
        product = _mock_product(history_days=400, sales_count=4,
                                sales_age_days=100, sale_price_cents=1500)
        result = get_1yr_avg_sale_price(product)
        self.assertIsNotNone(result, "Recent inferred sales must still yield a value.")
        self.assertAlmostEqual(result['1yr. Avg.'], 15.00, places=2)
        self.assertNotAlmostEqual(
            result['1yr. Avg.'], FALLBACK_WOULD_HAVE_RETURNED, places=2,
            msg="Value matches the old fallback figure, not the inferred sales."
        )


class InferredSaleCountIsReturned(unittest.TestCase):
    """analyze_sales_performance must report the count on EVERY branch."""

    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_zero_sales_branch_returns_zero_not_missing(self):
        """A rejected deal still gets a count. 0 is a reading; NULL is not.

        The distinction is load-bearing: NULL means "never computed" (a legacy row,
        or one only ever touched by the light path) and must never be read as zero.
        """
        product = _mock_product(history_days=500, sales_count=0)
        result = analyze_sales_performance(product, [])
        self.assertIn('inferred_sale_count', result)
        self.assertEqual(result['inferred_sale_count'], 0)
        self.assertEqual(result['peak_price_mode_cents'], -1,
                         "Zero sales must still reject the price.")

    def test_sparse_branch_returns_the_count(self):
        product = _mock_product(history_days=400, sales_count=2, sales_age_days=100)
        events, _ = infer_sale_events(product)
        result = analyze_sales_performance(product, events)
        self.assertIn('inferred_sale_count', result)
        self.assertEqual(result['inferred_sale_count'], len(events))
        self.assertEqual(result.get('price_source'), 'Inferred Sales (Sparse)',
                         "Fixture must land on the sparse branch (<3 sales).")

    def test_normal_branch_returns_the_count(self):
        product = _mock_product(history_days=400, sales_count=4, sales_age_days=100)
        events, _ = infer_sale_events(product)
        self.assertGreaterEqual(len(events), 3,
                                "Fixture must land on the normal branch (>=3 sales).")
        with patch('keepa_deals.stable_calculations._query_xai_for_reasonableness',
                   return_value=True):
            result = analyze_sales_performance(product, events)
        self.assertIn('inferred_sale_count', result)
        self.assertEqual(result['inferred_sale_count'], len(events))

    def test_count_matches_the_post_iqr_sale_list(self):
        """The stored count is the SANE count, the same list the prices come from."""
        product = _mock_product(history_days=400, sales_count=4, sales_age_days=100)
        events, _ = infer_sale_events(product)
        with patch('keepa_deals.stable_calculations._query_xai_for_reasonableness',
                   return_value=True):
            result = analyze_sales_performance(product, events)
        self.assertEqual(result['inferred_sale_count'], len(events))


class SparseAiSkipSurvives(unittest.TestCase):
    """The sparse half of the AI-check skip is deliberately unchanged.

    Only the 'Keepa Stats Fallback' half was removed. 1-2 inferred sales are TRUE
    sales with thin context, and skipping the check for them is intended behaviour
    (AGENTS.md 7.8, Sparse Sales Rescue).
    """

    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_sparse_price_still_skips_the_ai_check(self):
        product = _mock_product(history_days=400, sales_count=2,
                                sales_age_days=100, sale_price_cents=1500)
        events, _ = infer_sale_events(product)
        with patch('keepa_deals.stable_calculations._query_xai_for_reasonableness') as ai:
            result = analyze_sales_performance(product, events)
        ai.assert_not_called()
        self.assertGreater(result['peak_price_mode_cents'], 0,
                           "The sparse price must survive, not be invalidated.")

    def test_suspiciously_high_sparse_price_still_forces_the_ai_check(self):
        """The 3x rule still overrides the sparse skip. Current used is $26.00."""
        product = _mock_product(history_days=400, sales_count=2,
                                sales_age_days=100, sale_price_cents=20000)
        events, _ = infer_sale_events(product)
        with patch('keepa_deals.stable_calculations._query_xai_for_reasonableness',
                   return_value=True) as ai:
            analyze_sales_performance(product, events)
        ai.assert_called_once()


class HeavyPathWritesTheCount(unittest.TestCase):
    """End-to-end through the real _process_single_deal and the real key transform.

    The unit tests above prove analyze_sales_performance RETURNS the count. This
    proves the production wiring PERSISTS it: written under the headers.json display
    name, survived by clean_numeric_values, and re-keyed to the sanitized DB column
    by to_db_keys - the AGENTS.md 7.12 namespace contract that destroyed data in
    production when it was got wrong.
    """

    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def _run_heavy_path(self, product):
        from keepa_deals import processing
        # Loaded off disk rather than imported by name: test_approve_dedup.py leaves
        # a MagicMock at sys.modules['keepa_deals.db_utils'] for the whole session.
        # See tests/_real_module.py.
        to_db_keys = _load_real('keepa_deals.db_utils').to_db_keys
        # retrying's sleep is stubbed, and it is masking a PRE-EXISTING defect, not
        # anything this PR introduced. field_mappings.FUNCTION_LIST holds a direct
        # reference to stable_deals.last_update, whose signature is
        # (deal_object, logger_param, product_data=None) - logger_param has no
        # default. The generic loop in _process_single_deal calls every field
        # function as func(product_data), one positional argument, so last_update
        # raises TypeError on EVERY call. It carries
        # @retry(stop_max_attempt_number=3, wait_fixed=5000), so each newly
        # discovered deal burns 10 seconds of wall clock on two 5-second sleeps and
        # then stores nothing. Its sibling last_price_change survives only because
        # its logger_param does have a default. Reported to the owner; out of scope
        # here (AGENTS.md 3).
        with patch('retrying.time.sleep'), \
             patch.object(processing, 'get_used_product_info',
                          return_value=(2899, 'SELLERID', True, 11)), \
             patch.object(processing, 'classify_seasonality',
                          return_value='Year-round'), \
             patch.object(processing, 'get_sells_period', return_value='-'), \
             patch('keepa_deals.stable_calculations._query_xai_for_reasonableness',
                   return_value=True), \
             patch('keepa_deals.stable_calculations.infer_sales_with_xai',
                   return_value=None):
            row = processing._process_single_deal(product, {}, 'fake-key')
        self.assertIsNotNone(row, "Fixture must produce a row.")
        return to_db_keys(processing.clean_numeric_values(row))

    def test_count_reaches_the_sanitized_db_key(self):
        product = _mock_product(history_days=400, sales_count=4, sales_age_days=100,
                                points_per_day=4)
        events, _ = infer_sale_events(product)
        db_row = self._run_heavy_path(product)
        self.assertIn('Inferred_Sale_Count', db_row,
                      "The count must arrive under the sanitized DB column name.")
        self.assertEqual(db_row['Inferred_Sale_Count'], len(events))
        self.assertNotIn('Inferred Sale Count', db_row,
                         "to_db_keys must leave no display-name key behind.")

    def test_zero_sale_deal_still_records_a_zero_count(self):
        product = _mock_product(history_days=500, sales_count=0, points_per_day=4)
        db_row = self._run_heavy_path(product)
        self.assertEqual(db_row.get('Inferred_Sale_Count'), 0)
        self.assertIsNone(db_row.get('1yr_Avg'),
                          "Zero sales must leave 1yr_Avg unset, not estimated.")

    def test_heavy_path_no_longer_writes_the_low_est_marker(self):
        """The dead branch is gone; nothing may write that string again."""
        for product in (_mock_product(history_days=500, sales_count=0,
                                      points_per_day=4),
                        _mock_product(history_days=500, sales_count=4,
                                      sales_age_days=400, points_per_day=4)):
            db_row = self._run_heavy_path(product)
            self.assertNotEqual(db_row.get('Deal_Trust'), 'Low (Est.)')


if __name__ == '__main__':
    unittest.main()
