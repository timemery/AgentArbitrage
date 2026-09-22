"""The AI Reasonableness Check fails CLOSED (Trello #144, Pricing Logic Version 3).

WHY THIS FILE EXISTS
--------------------
`_query_xai_for_reasonableness` used to return True - "reasonable" - on two paths
where it had checked nothing: the daily cap reached, and any xAI error. The price
was then accepted unchecked AND stamped with the current `Pricing_Logic_Version`,
which drops the row out of the repair predicate, so nothing ever re-checked it.
PR #346's headroom guard kept `repair_pricing.py` off the cap path; nothing
covered the error path, so a transient xAI outage passed prices exactly as the
cap used to.

A missing API key was the same failure in a third place: it returned True too.
Owner decision 2026-09-22: it fails closed as well.

Now all three paths return None - UNVERIFIABLE. `analyze_sales_performance` withholds
the price (List at NULL, row hidden) and flags `price_unverified`, and
`_process_single_deal` writes `Pricing_Logic_Version` NULL for that row, so it
stays in `STALE_PRICING_PREDICATE` and the repair sweep retries it.
"""

import logging
import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import httpx

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from _real_module import load as _load_real  # noqa: E402

from keepa_deals import stable_calculations  # noqa: E402
from keepa_deals.pricing_version import PRICING_LOGIC_VERSION  # noqa: E402
from keepa_deals.stable_calculations import analyze_sales_performance  # noqa: E402

from test_1yr_avg_no_fallback import _mock_product  # noqa: E402


def _ask():
    return stable_calculations._query_xai_for_reasonableness(
        'A Title', 'Books', 'Sep', 123.45, 'fake-key')


def _uncached():
    cache = MagicMock()
    cache.get.return_value = None
    return patch.object(stable_calculations, 'xai_cache', cache)


class _Silent(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)
        stable_calculations.clear_analysis_cache()

    def tearDown(self):
        stable_calculations.clear_analysis_cache()
        logging.disable(logging.NOTSET)


class TheCheckReportsUnverifiableNotReasonable(_Silent):

    def test_a_missing_api_key_is_unverifiable(self):
        manager = MagicMock()
        with _uncached(), patch.object(stable_calculations, 'xai_token_manager', manager):
            self.assertIsNone(stable_calculations._query_xai_for_reasonableness(
                'A Title', 'Books', 'Sep', 123.45, None))
        manager.request_permission.assert_not_called()

    def test_the_daily_cap_is_unverifiable(self):
        manager = MagicMock()
        manager.request_permission.return_value = False
        with _uncached(), patch.object(stable_calculations, 'xai_token_manager', manager):
            self.assertIsNone(_ask())

    def test_an_xai_error_is_unverifiable(self):
        manager = MagicMock()
        manager.request_permission.return_value = True
        with _uncached(), \
                patch.object(stable_calculations, 'xai_token_manager', manager), \
                patch.object(stable_calculations.httpx, 'Client',
                             side_effect=httpx.ConnectError('xAI is down')):
            self.assertIsNone(_ask())

    def test_an_unverifiable_answer_is_not_cached(self):
        manager = MagicMock()
        manager.request_permission.return_value = True
        cache = MagicMock()
        cache.get.return_value = None
        with patch.object(stable_calculations, 'xai_cache', cache), \
                patch.object(stable_calculations, 'xai_token_manager', manager), \
                patch.object(stable_calculations.httpx, 'Client',
                             side_effect=httpx.ConnectError('xAI is down')):
            _ask()
        cache.set.assert_not_called()


def _events(prices=(28000, 30000, 32000)):
    year = datetime.now().year - 1
    return [{'event_timestamp': datetime(year, 3, 10 + 2 * i),
             'inferred_sale_price_cents': cents,
             'price_point': ('Used', datetime(2000, 1, 1) + timedelta(days=i))}
            for i, cents in enumerate(prices)]


PRODUCT = {'asin': 'FAILCLOSED', 'title': 'fixture', 'csv': [None] * 13,
           'stats': {'current': [-1] * 23, 'avg180': [-1] * 23, 'avg365': [-1] * 23}}


class TheAnalysisWithholdsAnUnverifiablePrice(_Silent):

    def _analyse(self, answer):
        with patch.object(stable_calculations, '_query_xai_for_reasonableness',
                          return_value=answer):
            return analyze_sales_performance(PRODUCT, _events())

    def test_unverifiable_withholds_the_price_and_flags_it(self):
        result = self._analyse(None)
        self.assertEqual(result['peak_price_mode_cents'], -1)
        self.assertTrue(result['price_unverified'])

    def test_a_rejection_is_not_flagged_unverified(self):
        result = self._analyse(False)
        self.assertEqual(result['peak_price_mode_cents'], -1)
        self.assertFalse(result['price_unverified'])

    def test_a_pass_keeps_the_price(self):
        result = self._analyse(True)
        self.assertEqual(result['peak_price_mode_cents'], 30000.0)
        self.assertFalse(result['price_unverified'])


class AMissingKeyWithholdsThePrice(_Silent):
    """End to end through the real check: no XAI_TOKEN in the environment."""

    def test_no_key_means_no_price_and_a_flag(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('XAI_TOKEN', None)
            with _uncached():
                result = analyze_sales_performance(PRODUCT, _events())
        self.assertEqual(result['peak_price_mode_cents'], -1)
        self.assertTrue(result['price_unverified'])


class TheHeavyPathLeavesAnUnverifiedRowStale(_Silent):
    """End to end through the real `_process_single_deal` and key transform."""

    def _run(self, answer, asin):
        from keepa_deals import processing
        to_db_keys = _load_real('keepa_deals.db_utils').to_db_keys
        product = _mock_product(history_days=400, sales_count=4, sales_age_days=100,
                                points_per_day=4, new_price_cents=90000)
        product['asin'] = asin
        with patch('retrying.time.sleep'), \
             patch.object(processing, 'get_used_product_info',
                          return_value=(2899, 'SELLERID', True, 11)), \
             patch.object(processing, 'classify_seasonality',
                          return_value='Year-round'), \
             patch.object(processing, 'get_sells_period', return_value='-'), \
             patch('keepa_deals.stable_calculations._query_xai_for_reasonableness',
                   return_value=answer):
            row = processing._process_single_deal(product, {}, 'fake-key')
        self.assertIsNotNone(row, 'Fixture must produce a row.')
        return to_db_keys(processing.clean_numeric_values(row))

    def test_an_unverifiable_price_is_hidden_and_left_stale(self):
        db_row = self._run(None, 'FAILCLOSE1')
        self.assertIn(db_row.get('List_at'), (None, '-', ''),
                      'an unverifiable price must not be shown')
        self.assertIn('Pricing_Logic_Version', db_row)
        self.assertIsNone(db_row['Pricing_Logic_Version'],
                          'NULL keeps the row in the repair predicate')

    def test_a_verified_price_is_stamped_current(self):
        db_row = self._run(True, 'FAILCLOSE2')
        self.assertTrue(db_row.get('List_at'))
        self.assertEqual(db_row['Pricing_Logic_Version'], PRICING_LOGIC_VERSION)

    def test_the_stamp_follows_the_analysis_that_produced_list_at(self):
        """A second, later check that succeeds must not launder the first."""
        from keepa_deals import processing
        answers = iter([None, True, True, True])
        to_db_keys = _load_real('keepa_deals.db_utils').to_db_keys
        product = _mock_product(history_days=400, sales_count=4, sales_age_days=100,
                                points_per_day=4, new_price_cents=90000)
        product['asin'] = 'FAILCLOSE3'
        with patch('retrying.time.sleep'), \
             patch.object(processing, 'get_used_product_info',
                          return_value=(2899, 'SELLERID', True, 11)), \
             patch.object(processing, 'classify_seasonality',
                          return_value='Year-round'), \
             patch.object(processing, 'get_sells_period', return_value='-'), \
             patch('keepa_deals.stable_calculations._query_xai_for_reasonableness',
                   side_effect=lambda *a, **k: next(answers)):
            row = processing._process_single_deal(product, {}, 'fake-key')
        db_row = to_db_keys(processing.clean_numeric_values(row))
        self.assertIsNone(db_row['Pricing_Logic_Version'])


if __name__ == '__main__':
    unittest.main()
