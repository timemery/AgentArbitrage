"""The peak-season mode counts DISTINCT price points, not sale events.

WHY THIS FILE EXISTS
--------------------
`infer_sale_events` prices a sale from the last change-log point strictly before
its offer drop, at any distance (PR #340). Two drops with no price change between
them are therefore both priced by the SAME point. That association is correct -
the lowest offer had not moved - but it is ONE asking price. Counted twice, it was
the only repeated value in a peak month of otherwise distinct prices and won the
mode uncontested: 4 of 50 audited rows on 2026-09-22 (Dev_Logs
2026-09-22_Prime_Picks_Guard_And_The_Thin_Peak_Month.md 4).

Since Pricing Logic Version 3 each sale carries `price_point` = (series, matched
point timestamp), and `analyze_sales_performance` scores one price per distinct
point. Identity is the point's own timestamp, never price equality: two separate
points holding the same price are ordinary repricing and each counts.
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
    infer_sale_events,
)

# Anchored on a whole Keepa minute, far enough back to sit inside the 3-year window.
BASE_KTM = int(((datetime.now() - timedelta(days=120)) - KEEPA_EPOCH)
               .total_seconds() // 60)
HOUR = 60
DAY = 24 * HOUR


def _ts(ktm):
    return KEEPA_EPOCH + timedelta(minutes=ktm)


def _flat(points):
    out = []
    for ktm, value in points:
        out.extend([int(ktm), int(value)])
    return out


def _two_drops_product(second_drop_has_own_point):
    """Two Used offer drops two days apart, each confirmed by a rank drop.

    One price point sits a day before the first drop. With
    `second_drop_has_own_point` a second point (same price) sits a day before the
    second drop; without it, the second drop reaches back to the first's point.
    """
    first, second = BASE_KTM, BASE_KTM + 2 * DAY
    price_points = [(first - DAY, 5000)]
    if second_drop_has_own_point:
        price_points.append((second - DAY, 5000))
    csv_data = [None] * 13
    csv_data[2] = _flat(price_points)
    csv_data[3] = _flat([(first - HOUR, 100000), (first + HOUR, 50000),
                         (second - HOUR, 100000), (second + HOUR, 50000)])
    csv_data[12] = _flat([(first - 3 * DAY, 6), (first, 5), (second, 4)])
    return {'asin': 'POINTID', 'csv': csv_data, 'stats': {}}


def _sale(day, cents, point):
    event = {'event_timestamp': _ts(BASE_KTM + day * DAY),
             'inferred_sale_price_cents': cents}
    if point is not None:
        event['price_point'] = ('Used', _ts(BASE_KTM + point * DAY - DAY))
    return event


def _analyse(events):
    # No Amazon price, no current Used: nothing but the branch can move the number.
    product = {'asin': 'POINTMODE', 'title': 'fixture',
               'stats': {'current': [-1] * 23, 'avg180': [-1] * 23,
                         'avg365': [-1] * 23}}
    with patch.object(stable_calculations, '_query_xai_for_reasonableness',
                      return_value=True):
        return analyze_sales_performance(product, events)


class _Silent(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)


class EverySaleRecordsWhichPointPricedIt(_Silent):

    def test_two_drops_on_one_point_share_its_identity(self):
        events, drops = infer_sale_events(_two_drops_product(False))
        self.assertEqual(drops, 2)
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]['price_point'], events[1]['price_point'])
        self.assertEqual(events[0]['price_point'], ('Used', _ts(BASE_KTM - DAY)))

    def test_two_points_at_the_same_price_are_two_identities(self):
        events, _ = infer_sale_events(_two_drops_product(True))
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]['inferred_sale_price_cents'],
                         events[1]['inferred_sale_price_cents'])
        self.assertNotEqual(events[0]['price_point'], events[1]['price_point'])


class TheModeCountsDistinctPoints(_Silent):
    """Peak month [$280, $300, $375.66, $375.66]; only the pairing differs."""

    def test_a_shared_point_does_not_win_the_mode(self):
        events = [_sale(0, 28000, 0), _sale(2, 30000, 2),
                  _sale(4, 37566, 4), _sale(6, 37566, 4)]   # 6 reaches back to 4
        result = _analyse(events)
        # Distinct points [280, 300, 375.66]: no repeat -> median $300.
        self.assertEqual(result['peak_price_mode_cents'], 30000.0)

    def test_separate_points_at_one_price_still_make_a_mode(self):
        events = [_sale(0, 28000, 0), _sale(2, 30000, 2),
                  _sale(4, 37566, 4), _sale(6, 37566, 6)]
        self.assertEqual(_analyse(events)['peak_price_mode_cents'], 37566.0)

    def test_events_without_an_identity_each_count(self):
        """A missing identity can never merge two sales."""
        events = [_sale(0, 28000, None), _sale(2, 30000, None),
                  _sale(4, 37566, None), _sale(6, 37566, None)]
        self.assertEqual(_analyse(events)['peak_price_mode_cents'], 37566.0)

    def test_the_sale_count_is_still_the_sale_count(self):
        events = [_sale(0, 28000, 0), _sale(2, 30000, 2),
                  _sale(4, 37566, 4), _sale(6, 37566, 4)]
        self.assertEqual(_analyse(events)['inferred_sale_count'], 4)


if __name__ == '__main__':
    unittest.main()
