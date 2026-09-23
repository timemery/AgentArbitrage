"""Pricing Logic Version 4: peak by pooled support, the 2x median cap, the AI skip.

WHY THIS FILE EXISTS
--------------------
Measured on the 2026-09-23 `--hidden-v3` audit (63 withheld rows):

*   27 of 31 thin rows were LONE SPIKES: v3 picked the single month with the
    highest median, one isolated high sale won, and its season held one point.
    v4 chooses the peak SEASON by pooled support - every peak-month +/- 1 window
    with >= 2 distinct points is eligible, the highest median wins.
*   That is still a maximum over thin estimates: 15 of 61 rows priced by it came
    out above 2x their own 1yr median, the worst 5-20x. v4 caps `List at` at
    PEAK_MEDIAN_CAP_RATIO (2) x the 1yr median of inferred sales. No sale in the
    last year: no median cap.
*   The AI check rejected prices at the book's own 1yr average (1936164116:
    $398.99 vs $398.99) - it is never shown the book's sale prices. v4 skips it at
    <= AI_SKIP_MEDIAN_RATIO (1.25) x the 1yr median; above that it runs,
    fail-closed, as in v3.
*   Every withheld price records why (`withheld_reason`).
"""

import logging
import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals import stable_calculations as sc  # noqa: E402
from keepa_deals.pricing_version import PRICING_LOGIC_VERSION  # noqa: E402

NOW = datetime.now()
_POINT = [0]


def _sale(when, cents):
    _POINT[0] += 1
    return {'event_timestamp': when, 'inferred_sale_price_cents': cents,
            'price_point': ('Used', datetime(2000, 1, 1) + timedelta(days=_POINT[0]))}


def _days_ago(*pairs):
    return [_sale(NOW - timedelta(days=d), c) for d, c in pairs]


def _product(current_used=-1, new_points=None):
    current = [-1] * 23
    current[2] = current_used
    csv_data = [None] * 13
    if new_points:
        flat = []
        for when, cents in sorted(new_points):
            flat.extend([int((when - sc.KEEPA_EPOCH).total_seconds() // 60), cents])
        csv_data[1] = flat
    return {'asin': 'PRICEV4', 'title': 'fixture', 'csv': csv_data,
            'stats': {'current': current, 'avg180': [-1] * 23, 'avg365': [-1] * 23}}


def _analyse(events, product=None, answer=True):
    with patch.object(sc, '_query_xai_for_reasonableness', return_value=answer) as ai:
        result = sc.analyze_sales_performance(product or _product(), events)
    return result, ai


# A recent peak season well above a larger body of recent low sales. Window
# prices [300, 320] (median $310); the 1yr median of all seven sales is $56.
RECENT_SPIKY = [(60, 30000), (62, 32000),
                (300, 5000), (302, 5200), (304, 5400), (306, 5600), (308, 5800)]


class _Silent(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)


class TheVersionIsFour(_Silent):

    def test_the_constants(self):
        self.assertEqual(PRICING_LOGIC_VERSION, 4)
        self.assertEqual(sc.PEAK_MEDIAN_CAP_RATIO, 2.0)
        self.assertEqual(sc.AI_SKIP_MEDIAN_RATIO, 1.25)


class ThePeakIsChosenByPooledSupport(_Silent):

    def test_an_isolated_high_month_cannot_win(self):
        y = NOW.year - 2
        events = [_sale(datetime(y, 6, 10), 90000),
                  _sale(datetime(y, 1, 10), 30000), _sale(datetime(y, 1, 20), 32000),
                  _sale(datetime(y, 2, 10), 34000)]
        result, _ = _analyse(events)
        self.assertEqual(result['peak_window'], 'Dec-Jan-Feb')
        self.assertEqual(result['peak_season'], 'Jan')
        self.assertEqual(result['peak_price_mode_cents'], 32000.0)

    def test_among_eligible_windows_the_highest_median_wins(self):
        y = NOW.year - 2
        events = [_sale(datetime(y, 3, 10), 10000), _sale(datetime(y, 3, 20), 11000),
                  _sale(datetime(y, 9, 10), 30000), _sale(datetime(y, 9, 20), 31000)]
        result, _ = _analyse(events)
        self.assertEqual(result['peak_season'], 'Sep')
        self.assertEqual(result['peak_price_mode_cents'], 30500.0)


class TheMedianCap(_Silent):

    def test_list_at_is_capped_at_twice_the_1yr_median(self):
        result, _ = _analyse(_days_ago(*RECENT_SPIKY))
        self.assertEqual(result['one_year_median_cents'], 5600.0)
        self.assertEqual(result['median_cap_cents'], 11200.0)
        self.assertEqual(result['peak_price_mode_cents'], 11200.0)

    def test_no_sale_in_the_last_year_means_no_median_cap(self):
        events = [_sale(NOW - timedelta(days=d + 730), c) for d, c in RECENT_SPIKY]
        result, ai = _analyse(events)
        self.assertIsNone(result['one_year_median_cents'])
        self.assertIsNone(result['median_cap_cents'])
        self.assertEqual(result['peak_price_mode_cents'], 31000.0)
        ai.assert_called_once()

    def test_the_lower_of_the_new_cap_and_the_median_cap_binds(self):
        window = NOW - timedelta(days=61)
        product = _product(new_points=[(window - timedelta(days=90), 9000)])
        result, _ = _analyse(_days_ago(*RECENT_SPIKY), product)
        # New cap $90 + $3.99 = $93.99 is below the $112 median cap.
        self.assertEqual(result['peak_price_mode_cents'], 9399.0)


class TheAiSkip(_Silent):

    def test_a_price_backed_by_the_1yr_median_skips_the_check(self):
        result, ai = _analyse(_days_ago((60, 10000), (62, 11000), (64, 12000)))
        self.assertEqual(result['peak_price_mode_cents'], 11000.0)
        self.assertTrue(result['ai_skipped_by_median'])
        ai.assert_not_called()

    def test_a_price_above_it_still_goes_to_the_check(self):
        result, ai = _analyse(_days_ago(*RECENT_SPIKY))
        # $112 capped price > 1.25 x $56 = $70.
        self.assertFalse(result['ai_skipped_by_median'])
        ai.assert_called_once()

    def test_the_skip_takes_precedence_over_the_3x_rule(self):
        """Current Used $20 makes $110 'suspiciously high'; the book sold at $110."""
        product = _product(current_used=2000)
        result, ai = _analyse(_days_ago((60, 10000), (62, 11000), (64, 12000)), product)
        self.assertTrue(result['ai_skipped_by_median'])
        ai.assert_not_called()

    def test_above_the_skip_the_check_still_fails_closed(self):
        result, _ = _analyse(_days_ago(*RECENT_SPIKY), answer=None)
        self.assertEqual(result['peak_price_mode_cents'], -1)
        self.assertTrue(result['price_unverified'])


class EveryWithheldPriceSaysWhy(_Silent):

    def test_thin(self):
        y = NOW.year - 2
        events = [_sale(datetime(y, m, 10), 10000 + m) for m in (1, 5, 9)]
        self.assertEqual(_analyse(events)[0]['withheld_reason'], sc.WITHHELD_THIN)

    def test_ai_rejected(self):
        result, _ = _analyse(_days_ago(*RECENT_SPIKY), answer=False)
        self.assertEqual(result['withheld_reason'], sc.WITHHELD_AI_REJECTED)

    def test_unverifiable(self):
        result, _ = _analyse(_days_ago(*RECENT_SPIKY), answer=None)
        self.assertEqual(result['withheld_reason'], sc.WITHHELD_UNVERIFIABLE)

    def test_over_1500(self):
        y = NOW.year - 2
        events = [_sale(datetime(y, 9, 10), 200000), _sale(datetime(y, 9, 20), 210000),
                  _sale(datetime(y, 3, 10), 190000)]
        result, ai = _analyse(events)
        self.assertEqual(result['withheld_reason'], sc.WITHHELD_OVER_1500)
        ai.assert_not_called()

    def test_no_sales(self):
        self.assertEqual(_analyse([])[0]['withheld_reason'], sc.WITHHELD_NO_SALES)

    def test_a_priced_row_has_no_reason(self):
        result, _ = _analyse(_days_ago((60, 10000), (62, 11000), (64, 12000)))
        self.assertIsNone(result['withheld_reason'])


if __name__ == '__main__':
    unittest.main()
