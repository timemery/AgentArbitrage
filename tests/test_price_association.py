"""The price attached to an inferred sale must be the price in force BEFORE it.

WHY THIS FILE EXISTS
--------------------
`csv[1]` and `csv[2]` hold the **lowest** New / Used offer price, not the price of
any particular copy. When the cheapest copy sells, the series does not record what
it sold for - it steps **up** to whatever the next cheapest listing asks, at
essentially the same timestamp as the offer-count drop that marks the sale.

`infer_sale_events` used to associate a price with
`merge_asof(direction='nearest')`, which has no tolerance and no tie-break, so it
could land on the point **at or after** the drop and store the asking price of a
copy that did **not** sell. Confirmed live on 5 of 7 sales across 3 ASINs on
2026-09-11: $124.85 recorded as $1,000.00, $49.95 as $499.95, $328.19 as $625.59.
See `Dev_Logs/2026-09-11b_Remove_1yr_Avg_Listing_Average_Fallback.md` 4b.

The association is now `direction='backward'`, `allow_exact_matches=False` and a
tolerance of `PRICE_ASSOCIATION_TOLERANCE_HOURS`, so it reads the last point
STRICTLY BEFORE the drop and yields NO price at all when that point is too old to
be trusted as the price in force.

The fixtures here are deliberately SPARSE - two or three points per series, placed
at exact offsets from the drop - rather than the dense uniform grids the rest of
the suite uses. A dense grid cannot express "the only prior price point is 30 days
old", which is the shape that produced the worst live result.

NOTE ON THE ZERO-SALE BRANCHES: `infer_sale_events` calls xAI when it confirms no
sales, so every test that expects zero sales patches `infer_sales_with_xai`. The
patch is scoped, per `AGENTS.md` 6.4 and `tests/conftest.py`.
"""

import logging
import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals.stable_calculations import (  # noqa: E402
    KEEPA_EPOCH,
    PRICE_ASSOCIATION_TOLERANCE_HOURS,
    infer_sale_events,
)

# The price the copy actually sold at, and the next listing up the stack. The round
# number is the point: $499.95 is a price a seller typed, which is why values like
# it, $1,000.00, $250.00 and $150.00 showed up on the box.
SOLD_AT_CENTS = 4995
NEXT_LISTING_CENTS = 49995

MINUTES_PER_HOUR = 60

# The drop is 120 days back: inside the 3-year inference window and inside the
# 365-day window `1yr. Avg.` uses. Anchored on a whole Keepa minute so every offset
# below is exact rather than truncated.
SALE_KTM = int(((datetime.now() - timedelta(days=120)) - KEEPA_EPOCH)
               .total_seconds() // 60)
SALE_TS = KEEPA_EPOCH + timedelta(minutes=SALE_KTM)


def _flat(points):
    """[(ktm, value), ...] -> Keepa's flat [time, value, time, value, ...]."""
    out = []
    for ktm, value in points:
        out.extend([int(ktm), int(value)])
    return out


def _at(hours):
    """A Keepa minute `hours` from the offer drop. Negative is before it."""
    return SALE_KTM + int(round(hours * MINUTES_PER_HOUR))


def _product(used_price_points=None, new_price_points=None,
             used_offer_points=None, new_offer_points=None,
             rank_points=None, asin='PRICEASSOC'):
    """One offer drop at SALE_KTM, confirmed by a rank drop one hour later.

    Defaults give a Used drop; pass `new_offer_points` to exercise the New series.
    """
    if rank_points is None:
        # A rank point before the drop and a better one inside the 240-hour
        # confirmation window, which is what `rank_diff < 0` needs to see.
        rank_points = [(_at(-1), 100000), (_at(1), 50000)]
    if used_offer_points is None and new_offer_points is None:
        used_offer_points = [(_at(-240), 5), (_at(0), 4)]

    csv_data = [None] * 13
    if new_price_points:
        csv_data[1] = _flat(new_price_points)
    if used_price_points:
        csv_data[2] = _flat(used_price_points)
    csv_data[3] = _flat(rank_points)
    if new_offer_points:
        csv_data[11] = _flat(new_offer_points)
    if used_offer_points:
        csv_data[12] = _flat(used_offer_points)

    return {
        'asin': asin,
        'title': 'Price association fixture',
        'csv': csv_data,
        # Amazon left at -1 so no ceiling can silently move a price these tests
        # assert on. Nothing here calls the pricing stage, but keep it honest.
        'stats': {'current': [-1, -1, SOLD_AT_CENTS, 500000] + [-1] * 19,
                  'avg180': [-1] * 23, 'avg365': [-1] * 23},
    }


class _Silent(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def _infer_expecting_no_sales(self, product):
        """Run the inference with the xAI rescue stubbed out.

        The rescue fires on the zero-confirmed-sales branch, and these tests are
        about the algorithmic association, not about the model.
        """
        with patch('keepa_deals.stable_calculations.infer_sales_with_xai',
                   return_value=[]) as xai:
            events, drops = infer_sale_events(product)
        return events, drops, xai


class PriceInForceBeforeTheDrop(_Silent):
    """The step-up defect, and the fix for it."""

    def test_records_the_price_the_copy_sold_at_not_the_next_listing(self):
        """The live defect, as an executable fact.

        A copy sold at $49.95 and the floor stepped up to $499.95 at the same
        timestamp. The recorded price must be $49.95.
        """
        product = _product(used_price_points=[(_at(-6), SOLD_AT_CENTS),
                                              (_at(0), NEXT_LISTING_CENTS)])
        events, drops = infer_sale_events(product)
        self.assertEqual(drops, 1)
        self.assertEqual(len(events), 1)
        self.assertEqual(int(events[0]['inferred_sale_price_cents']),
                         SOLD_AT_CENTS,
                         "The price in force before the drop is what the copy sold "
                         "at; the at/after point is the next listing's asking price.")

    def test_a_price_point_exactly_at_the_drop_is_never_used(self):
        """`allow_exact_matches=False` is load-bearing, not decoration.

        Keepa stamps the offer-count drop and the price step-up at the same minute,
        so a zero-distance match is the single most common way to pick up the
        leftover asking price.
        """
        product = _product(used_price_points=[(_at(-48), SOLD_AT_CENTS),
                                              (_at(0), NEXT_LISTING_CENTS)])
        events, _ = infer_sale_events(product)
        self.assertEqual(len(events), 1)
        self.assertEqual(int(events[0]['inferred_sale_price_cents']), SOLD_AT_CENTS)

    def test_a_later_price_point_is_never_reached_backwards(self):
        """Even when the only nearby point is after the drop, it is not used."""
        product = _product(used_price_points=[(_at(-12), SOLD_AT_CENTS),
                                              (_at(2), NEXT_LISTING_CENTS),
                                              (_at(96), NEXT_LISTING_CENTS)])
        events, _ = infer_sale_events(product)
        self.assertEqual(len(events), 1)
        self.assertEqual(int(events[0]['inferred_sale_price_cents']), SOLD_AT_CENTS)

    def test_the_new_series_follows_the_same_rule(self):
        """A New offer drop reads `csv[1]` under the identical association."""
        product = _product(
            used_price_points=[(_at(-6), 111), (_at(0), 222)],
            new_price_points=[(_at(-6), SOLD_AT_CENTS),
                              (_at(0), NEXT_LISTING_CENTS)],
            new_offer_points=[(_at(-240), 5), (_at(0), 4)],
        )
        events, drops = infer_sale_events(product)
        self.assertEqual(drops, 1)
        self.assertEqual(len(events), 1)
        self.assertEqual(int(events[0]['inferred_sale_price_cents']),
                         SOLD_AT_CENTS,
                         "A New drop must read csv[1], and still take the point "
                         "strictly before the drop.")


class ToleranceRejectsADistantPrice(_Silent):
    """A drop with no nearby prior price point yields no price, not a distant one."""

    def test_a_prior_price_beyond_the_tolerance_yields_no_sale(self):
        """The 1468308963 shape: the nearest price point was 60.3 days away.

        Production used to record it. A price point that old is not a statement
        about what was being asked at the moment of the drop.
        """
        far = -(PRICE_ASSOCIATION_TOLERANCE_HOURS * 3)
        product = _product(used_price_points=[(_at(far), SOLD_AT_CENTS),
                                              (_at(0), NEXT_LISTING_CENTS)])
        events, drops, _ = self._infer_expecting_no_sales(product)
        self.assertEqual(events, [],
                         "A price point {} hours before the drop must not be "
                         "associated with it.".format(-far))
        self.assertEqual(drops, 1,
                         "The offer drop still happened. It must stay in the Deal "
                         "Trust denominator even though no price could be attached.")

    def test_a_prior_price_exactly_at_the_tolerance_is_still_used(self):
        """The bound is inclusive, and this test is what says so."""
        product = _product(
            used_price_points=[(_at(-PRICE_ASSOCIATION_TOLERANCE_HOURS),
                                SOLD_AT_CENTS),
                               (_at(0), NEXT_LISTING_CENTS)])
        events, _ = infer_sale_events(product)
        self.assertEqual(len(events), 1)
        self.assertEqual(int(events[0]['inferred_sale_price_cents']), SOLD_AT_CENTS)

    def test_one_hour_past_the_tolerance_is_rejected(self):
        product = _product(
            used_price_points=[(_at(-(PRICE_ASSOCIATION_TOLERANCE_HOURS + 1)),
                                SOLD_AT_CENTS),
                               (_at(0), NEXT_LISTING_CENTS)])
        events, drops, _ = self._infer_expecting_no_sales(product)
        self.assertEqual(events, [])
        self.assertEqual(drops, 1)

    def test_a_drop_with_no_prior_price_point_at_all_yields_no_sale(self):
        """The first drop in a history can precede every price point."""
        product = _product(used_price_points=[(_at(2), NEXT_LISTING_CENTS),
                                              (_at(96), NEXT_LISTING_CENTS)])
        events, drops, _ = self._infer_expecting_no_sales(product)
        self.assertEqual(events, [])
        self.assertEqual(drops, 1)

    def test_a_rejected_price_never_leaks_through_as_nan(self):
        """`merge_asof` returns NaN when the tolerance matches nothing.

        `NaN <= 0` is False, so the pre-existing `price <= 0` guard does NOT catch
        it. A NaN reaching `confirmed_sales` would poison the IQR bounds, the mean
        and the mode for the whole ASIN.
        """
        far = -(PRICE_ASSOCIATION_TOLERANCE_HOURS * 3)
        product = _product(used_price_points=[(_at(far), SOLD_AT_CENTS),
                                              (_at(0), NEXT_LISTING_CENTS)])
        events, _, _ = self._infer_expecting_no_sales(product)
        for event in events:
            price = event['inferred_sale_price_cents']
            self.assertEqual(price, price, "NaN price leaked into a sale event.")
            self.assertGreater(price, 0)

    def test_a_non_positive_prior_price_is_still_discarded(self):
        """Keepa writes -1 for "no offer at this condition". Unchanged behaviour."""
        product = _product(used_price_points=[(_at(-6), -1),
                                              (_at(0), NEXT_LISTING_CENTS)])
        events, drops, _ = self._infer_expecting_no_sales(product)
        self.assertEqual(events, [])
        self.assertEqual(drops, 1)


class ToleranceIsWideEnoughForTheSuitesOwnShapes(_Silent):
    """The measured lower bound on the tolerance.

    Measured across every Keepa `csv` fixture in the suite, the gap between an
    offer drop and the price point preceding it is 1h (x17), 6h (x15) and 24h (x2).
    The 24-hour pair is `tests/test_synchronous_updates.py`, where the price series
    carries a point at the drop and one a day earlier. A tolerance under 24 hours
    would silently drop those sales, so this test pins the floor explicitly rather
    than leaving it to be discovered by a failure two files away.
    """

    def test_a_twenty_four_hour_old_price_is_still_associated(self):
        self.assertGreaterEqual(
            PRICE_ASSOCIATION_TOLERANCE_HOURS, 24,
            "24 hours is the widest gap any existing suite fixture relies on.")
        product = _product(used_price_points=[(_at(-24), SOLD_AT_CENTS),
                                              (_at(0), SOLD_AT_CENTS)])
        events, _ = infer_sale_events(product)
        self.assertEqual(len(events), 1)
        self.assertEqual(int(events[0]['inferred_sale_price_cents']), SOLD_AT_CENTS)


class TheConstant(unittest.TestCase):
    """The value is an owner decision, so make changing it deliberate and visible.

    Same pattern as `tests/test_field_mappings_call_contract.py`'s pinning of
    `FUNCTION_LIST[10] = None`: a bare number in a module is easy to nudge, and
    this one decides how many true sales the system is willing to discard.
    """

    def test_is_a_module_level_int_in_hours(self):
        self.assertIsInstance(PRICE_ASSOCIATION_TOLERANCE_HOURS, int)
        self.assertGreater(PRICE_ASSOCIATION_TOLERANCE_HOURS, 0)

    def test_is_pinned_to_the_approved_value(self):
        self.assertEqual(
            PRICE_ASSOCIATION_TOLERANCE_HOURS, 240,
            "Changing the price-association tolerance changes how many true "
            "inferred sales are discarded. It is an owner decision - update this "
            "test in the same change, with the reasoning.")

    def test_is_not_an_inline_literal(self):
        source = open(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '..',
            'keepa_deals', 'stable_calculations.py')).read()
        self.assertIn('PRICE_ASSOCIATION_TOLERANCE_HOURS = ', source)
        self.assertIn('hours=PRICE_ASSOCIATION_TOLERANCE_HOURS', source)


if __name__ == '__main__':
    unittest.main()
