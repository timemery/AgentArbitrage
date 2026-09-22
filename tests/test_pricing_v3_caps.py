"""Pricing Logic Version 3: the peak-window New cap and the gated Amazon ceiling.

WHY THIS FILE EXISTS
--------------------
Both rest on one premise the owner set on 2026-09-22 (Dev_Logs
2026-09-22_Prime_Picks_Guard_And_The_Thin_Peak_Month.md 2): the product buys at
the trough and sells at the peak, so a price taken TODAY is the buy side. A bound
on a peak-season `List at` has to be measured at the same point in the season.

1.  PEAK-WINDOW NEW CAP. `List at` <= median, across the (year, month) windows
    that fed it, of the lowest New price in each window, + $3.99. A row with no
    New price in any window is uncapped and records that the cap was unavailable -
    never a fallback to today's New price.
2.  AMAZON CEILING. `min(current, avg180, avg365) x 0.90` still, but `current` - a
    single reading taken today - counts only when today's month IS the peak month.
    Both trailing averages stay. This ships only beside the cap: removing a clamp
    can only raise prices.
"""

import logging
import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals import stable_calculations  # noqa: E402
from keepa_deals.stable_calculations import (  # noqa: E402
    KEEPA_EPOCH,
    analyze_sales_performance,
)

TODAY = datetime.now()


def _ktm(moment):
    return int((moment - KEEPA_EPOCH).total_seconds() // 60)


def _flat(points):
    out = []
    for moment, value in sorted(points, key=lambda p: p[0]):
        out.extend([_ktm(moment), int(value)])
    return out


def _peak_sales(year, month, prices, first_point=0):
    """Sales on the 10th-16th of one month, each on its own price point."""
    return [{'event_timestamp': datetime(year, month, 10 + 2 * i),
             'inferred_sale_price_cents': cents,
             'price_point': ('Used', datetime(2000, 1, 1)
                             + timedelta(days=first_point + i))}
            for i, cents in enumerate(prices)]


def _product(new_points=None, amazon=None, current_new=-1):
    amazon = amazon or {}
    current = [-1] * 23
    current[0] = amazon.get('current', -1)
    current[1] = current_new
    csv_data = [None] * 13
    if new_points:
        csv_data[1] = _flat(new_points)
    return {'asin': 'PRICEV3', 'title': 'fixture', 'csv': csv_data,
            'stats': {'current': current,
                      'avg180': [amazon.get('avg180', -1)] + [-1] * 22,
                      'avg365': [amazon.get('avg365', -1)] + [-1] * 22}}


def _analyse(product, events):
    with patch.object(stable_calculations, '_query_xai_for_reasonableness',
                      return_value=True):
        return analyze_sales_performance(product, events)


def _off_peak_month():
    """A month that is not today's, a year back so every sale is in the past."""
    month = TODAY.month - 3 if TODAY.month > 3 else TODAY.month + 9
    return TODAY.year - 1, month


class _Silent(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)


# Peak month with distinct prices $280, $300, $320: no mode, median $300.
PEAK_PRICES = (28000, 30000, 32000)


class ThePeakWindowNewCap(_Silent):

    def setUp(self):
        super().setUp()
        self.year, self.month = _off_peak_month()
        self.window = datetime(self.year, self.month, 1)

    def test_the_allowance_is_a_named_constant(self):
        self.assertEqual(stable_calculations.PEAK_NEW_CAP_ALLOWANCE_CENTS, 399)

    def test_a_peak_price_above_the_window_new_price_is_capped(self):
        product = _product(new_points=[(self.window + timedelta(days=5), 20000)])
        result = _analyse(product, _peak_sales(self.year, self.month, PEAK_PRICES))
        self.assertEqual(result['peak_price_mode_cents'], 20399.0)
        self.assertEqual(result['peak_new_cap'], stable_calculations.NEW_CAP_APPLIED)

    def test_a_peak_price_under_the_cap_is_untouched(self):
        product = _product(new_points=[(self.window + timedelta(days=5), 40000)])
        result = _analyse(product, _peak_sales(self.year, self.month, PEAK_PRICES))
        self.assertEqual(result['peak_price_mode_cents'], 30000.0)
        self.assertEqual(result['peak_new_cap'], stable_calculations.NEW_CAP_NOT_NEEDED)

    def test_the_cap_is_the_median_of_the_per_window_floors(self):
        """Same peak month in two years = two windows: floors $100 and $200."""
        older = datetime(self.year - 1, self.month, 1)
        product = _product(new_points=[(older + timedelta(days=5), 10000),
                                       (older + timedelta(days=20), 20000),
                                       (self.window + timedelta(days=5), 20000)])
        events = (_peak_sales(self.year - 1, self.month, (28000,), first_point=0)
                  + _peak_sales(self.year, self.month, (30000, 32000), first_point=10))
        result = _analyse(product, events)
        # Median of [100, 200] = 150, + 3.99.
        self.assertEqual(result['peak_new_cap_cents'], 15399.0)
        self.assertEqual(result['peak_price_mode_cents'], 15399.0)

    def test_a_price_carried_into_the_window_counts(self):
        """`csv[1]` is a change-log: no point in the window means the price held."""
        product = _product(new_points=[(self.window - timedelta(days=90), 20000)])
        result = _analyse(product, _peak_sales(self.year, self.month, PEAK_PRICES))
        self.assertEqual(result['peak_price_mode_cents'], 20399.0)

    def test_todays_new_price_is_never_the_cap(self):
        """$5.00 New today is the BUY side and must not touch a peak price."""
        product = _product(new_points=[(self.window + timedelta(days=5), 40000),
                                       (TODAY - timedelta(days=1), 500)],
                           current_new=500)
        result = _analyse(product, _peak_sales(self.year, self.month, PEAK_PRICES))
        self.assertEqual(result['peak_price_mode_cents'], 30000.0)

    def test_no_new_price_in_the_window_leaves_it_uncapped_and_says_so(self):
        """Only a LATER New price exists, and today's is cheap: still uncapped."""
        product = _product(new_points=[(TODAY - timedelta(days=1), 500)],
                           current_new=500)
        result = _analyse(product, _peak_sales(self.year, self.month, PEAK_PRICES))
        self.assertEqual(result['peak_price_mode_cents'], 30000.0)
        self.assertEqual(result['peak_new_cap'], stable_calculations.NEW_CAP_UNAVAILABLE)
        self.assertIsNone(result['peak_new_cap_cents'])

    def test_it_applies_to_the_sparse_rescue_too(self):
        product = _product(new_points=[(self.window + timedelta(days=5), 20000)])
        events = _peak_sales(self.year, self.month, (30000, 32000))
        result = _analyse(product, events)
        self.assertEqual(result['price_source'], 'Inferred Sales (Sparse)')
        self.assertEqual(result['peak_price_mode_cents'], 20399.0)


class TheAmazonCeilingReadsTodayOnlyInThePeakMonth(_Silent):
    """No New history here, so only the Amazon ceiling can move the price."""

    def test_todays_amazon_price_outside_the_peak_month_does_not_clip(self):
        year, month = _off_peak_month()
        product = _product(amazon={'current': 20000})
        result = _analyse(product, _peak_sales(year, month, PEAK_PRICES))
        self.assertEqual(result['peak_price_mode_cents'], 30000.0)

    def test_todays_amazon_price_in_the_peak_month_still_clips(self):
        product = _product(amazon={'current': 20000})
        events = _peak_sales(TODAY.year - 1, TODAY.month, PEAK_PRICES)
        result = _analyse(product, events)
        self.assertEqual(result['peak_price_mode_cents'], 18000.0)

    def test_the_trailing_averages_still_clip_off_peak(self):
        year, month = _off_peak_month()
        for key in ('avg180', 'avg365'):
            product = _product(amazon={key: 20000, 'current': 50000})
            result = _analyse(product, _peak_sales(year, month, PEAK_PRICES))
            self.assertEqual(result['peak_price_mode_cents'], 18000.0, key)

    def test_the_sparse_rescue_has_no_peak_month_so_never_reads_today(self):
        product = _product(amazon={'current': 20000})
        events = _peak_sales(TODAY.year - 1, TODAY.month, (30000, 32000))
        result = _analyse(product, events)
        self.assertEqual(result['price_source'], 'Inferred Sales (Sparse)')
        self.assertEqual(result['peak_price_mode_cents'], 31000.0)


if __name__ == '__main__':
    unittest.main()
