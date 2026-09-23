"""A peak season too thin to price gets no price (Pricing Logic Version 3).

WHY THIS FILE EXISTS
--------------------
`List at` was the mode/median of ONE calendar month, chosen by `idxmax` over up to
twelve monthly medians. On the 2026-09-22 audit the median peak month held ONE
sale, so for a slow book `List at` was the highest single sale in three years.

Owner decision, 2026-09-22, chosen from audit section (d) on 100 random visible
rows:

*   The peak SEASON is the peak month +/- 1 month, pooled across every year of
    the history (`PEAK_SEASON_HALF_WIDTH_MONTHS`). The price is estimated over it.
*   A season holding fewer than 2 DISTINCT price points
    (`PEAK_SEASON_MIN_PRICE_POINTS`) is not priced: `List at` is withheld, the
    row is PERSISTED unpriced and hidden - never deleted (AGENTS.md 7.8).
*   The Sparse Sales Rescue (1-2 sales) is held to the same minimum.
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

from keepa_deals import stable_calculations  # noqa: E402
from keepa_deals.pricing_version import PRICING_LOGIC_VERSION  # noqa: E402
from keepa_deals.stable_calculations import analyze_sales_performance  # noqa: E402

from test_1yr_avg_no_fallback import _mock_product  # noqa: E402

YEAR = datetime.now().year - 2
_POINT = [0]


def _sale(year, month, cents, point=None):
    """One sale on the 10th. Each gets its own price point unless `point` is given."""
    if point is None:
        _POINT[0] += 1
        point = _POINT[0]
    return {'event_timestamp': datetime(year, month, 10),
            'inferred_sale_price_cents': cents,
            'price_point': ('Used', datetime(2000, 1, 1) + timedelta(days=point))}


PRODUCT = {'asin': 'THINPEAK', 'title': 'fixture', 'csv': [None] * 13,
           'stats': {'current': [-1] * 23, 'avg180': [-1] * 23, 'avg365': [-1] * 23}}


class _Silent(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def _analyse(self, events):
        with patch.object(stable_calculations, '_query_xai_for_reasonableness',
                          return_value=True) as ai:
            result = analyze_sales_performance(PRODUCT, events)
        return result, ai


class TheRuleIsNamed(_Silent):

    def test_the_minimum_and_width_are_named_constants(self):
        self.assertEqual(stable_calculations.PEAK_SEASON_MIN_PRICE_POINTS, 2)
        self.assertEqual(stable_calculations.PEAK_SEASON_HALF_WIDTH_MONTHS, 1)

    def test_the_season_wraps_the_year_end(self):
        self.assertTrue(stable_calculations._in_peak_season(1, 12))
        self.assertTrue(stable_calculations._in_peak_season(11, 12))
        self.assertFalse(stable_calculations._in_peak_season(2, 12))


class AThinPeakSeasonIsNotPriced(_Silent):

    def test_no_season_with_two_points_withholds_the_price(self):
        """Every sale alone in its season, pooled across years or not."""
        events = [_sale(YEAR, 1, 10000), _sale(YEAR, 5, 11000), _sale(YEAR, 9, 40000)]
        result, ai = self._analyse(events)
        self.assertEqual(result['peak_price_mode_cents'], -1)
        self.assertTrue(result['thin_peak_season'])
        self.assertEqual(result['withheld_reason'], stable_calculations.WITHHELD_THIN)
        self.assertEqual(result['inferred_sale_count'], 3)
        ai.assert_not_called()

    def test_a_lone_high_month_no_longer_hides_a_supported_season(self):
        """v3 hid this row: Sep won the single-month vote and held one point.

        Pricing Logic Version 4 chooses the peak by pooled support, so the
        Mar-Apr season prices it (the 142249151X shape).
        """
        events = [_sale(YEAR, 9, 40000), _sale(YEAR, 3, 10000), _sale(YEAR, 4, 11000)]
        result, _ = self._analyse(events)
        self.assertEqual(result['peak_price_mode_cents'], 10500.0)
        self.assertFalse(result['thin_peak_season'])
        self.assertIsNone(result['withheld_reason'])

    def test_two_sales_on_one_price_point_are_one_point(self):
        events = [_sale(YEAR, 9, 40000, point=900), _sale(YEAR, 9, 40000, point=900),
                  _sale(YEAR, 3, 10000)]
        result, _ = self._analyse(events)
        self.assertEqual(result['peak_price_mode_cents'], -1)
        self.assertTrue(result['thin_peak_season'])


class ThePeakSeasonIsPooled(_Silent):

    def test_a_neighbouring_month_completes_the_season(self):
        events = [_sale(YEAR, 9, 40000), _sale(YEAR, 10, 30000), _sale(YEAR, 3, 10000)]
        result, _ = self._analyse(events)
        # Distinct points in Aug-Oct: [400, 300] -> median $350.
        self.assertEqual(result['peak_price_mode_cents'], 35000.0)
        self.assertFalse(result['thin_peak_season'])
        self.assertEqual(result['peak_season'], 'Sep')

    def test_the_same_month_in_another_year_completes_the_season(self):
        events = [_sale(YEAR, 9, 40000), _sale(YEAR + 1, 9, 36000),
                  _sale(YEAR, 3, 10000)]
        result, _ = self._analyse(events)
        self.assertEqual(result['peak_price_mode_cents'], 38000.0)

    def test_a_december_peak_pools_january(self):
        events = [_sale(YEAR, 12, 40000), _sale(YEAR + 1, 1, 30000),
                  _sale(YEAR, 6, 10000)]
        result, _ = self._analyse(events)
        self.assertEqual(result['peak_price_mode_cents'], 35000.0)

    def test_a_month_two_away_is_pooled_by_the_window_between(self):
        """Sep and Nov are each other's +/-2, but both sit in Oct's window."""
        events = [_sale(YEAR, 9, 40000), _sale(YEAR, 11, 30000), _sale(YEAR, 3, 10000)]
        result, _ = self._analyse(events)
        self.assertEqual(result['peak_price_mode_cents'], 35000.0)
        self.assertEqual(result['peak_window'], 'Sep-Oct-Nov')


class TheSparseRescueIsHeldToTheSameMinimum(_Silent):

    def test_one_sale_is_not_priced(self):
        result, _ = self._analyse([_sale(YEAR, 9, 20000)])
        self.assertEqual(result['peak_price_mode_cents'], -1)
        self.assertTrue(result['thin_peak_season'])
        self.assertEqual(result['price_source'], 'Inferred Sales (Sparse)')
        self.assertEqual(result['inferred_sale_count'], 1)

    def test_two_sales_in_one_season_are_priced(self):
        result, _ = self._analyse([_sale(YEAR, 9, 20000), _sale(YEAR, 10, 30000)])
        self.assertEqual(result['peak_price_mode_cents'], 25000.0)
        self.assertFalse(result['thin_peak_season'])

    def test_two_sales_in_different_seasons_are_not_priced(self):
        result, _ = self._analyse([_sale(YEAR, 9, 20000), _sale(YEAR, 3, 30000)])
        self.assertEqual(result['peak_price_mode_cents'], -1)

    def test_two_sales_on_one_price_point_are_not_priced(self):
        result, _ = self._analyse([_sale(YEAR, 9, 20000, point=950),
                                   _sale(YEAR, 9, 20000, point=950)])
        self.assertEqual(result['peak_price_mode_cents'], -1)


class AThinRowIsPersistedNotDeleted(_Silent):
    """End to end through the real `_process_single_deal` (AGENTS.md 7.8)."""

    def test_the_heavy_path_returns_an_unpriced_row_left_stale(self):
        from keepa_deals import processing
        stable_calculations.clear_analysis_cache()
        to_db_keys = _load_real('keepa_deals.db_utils').to_db_keys
        product = _mock_product(history_days=400, sales_count=1, sales_age_days=100,
                                points_per_day=4)
        product['asin'] = 'THINROW001'
        try:
            with patch('retrying.time.sleep'), \
                 patch.object(processing, 'get_used_product_info',
                              return_value=(2899, 'SELLERID', True, 11)), \
                 patch.object(processing, 'classify_seasonality',
                              return_value='Year-round'), \
                 patch.object(processing, 'get_sells_period', return_value='-'), \
                 patch('keepa_deals.stable_calculations._query_xai_for_reasonableness',
                       return_value=True):
                row = processing._process_single_deal(product, {}, 'fake-key')
        finally:
            stable_calculations.clear_analysis_cache()
        self.assertIsNotNone(row, 'a thin row must be persisted, not rejected')
        db_row = to_db_keys(processing.clean_numeric_values(row))
        self.assertIn(db_row.get('List_at'), (None, '-', ''))
        self.assertEqual(db_row['Inferred_Sale_Count'], 1)
        # Pricing Logic Version 4 (#152): written NULL, so the sweep re-evaluates
        # it as the book gains sales. It was stamped current in v3.
        self.assertIsNone(db_row['Pricing_Logic_Version'])


if __name__ == '__main__':
    unittest.main()
