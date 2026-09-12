"""The price attached to an inferred sale must be the price in force BEFORE it.

WHY THIS FILE EXISTS
--------------------
`csv[1]` and `csv[2]` hold the **lowest** New / Used offer price, not the price of
any particular copy. When the cheapest copy sells, the series does not record what
it sold for - it steps **up** to whatever the next cheapest listing asks, at
essentially the same timestamp as the offer-count drop that marks the sale.

`infer_sale_events` used to associate a price with
`merge_asof(direction='nearest')`, which has no tie-break, so it could land on the
point **at or after** the drop and store the asking price of a copy that did **not**
sell. Confirmed live on 5 of 7 sales across 3 ASINs on 2026-09-11: $124.85 recorded
as $1,000.00, $49.95 as $499.95, $328.19 as $625.59. See
`Dev_Logs/2026-09-11b_Remove_1yr_Avg_Listing_Average_Fallback.md` 4b.

The association is now `direction='backward'` with `allow_exact_matches=False`, so
it reads the last point STRICTLY BEFORE the drop, at **any** distance.

THERE IS NO TIME THRESHOLD, AND THAT IS THE MEASURED ANSWER
-----------------------------------------------------------
A 240-hour tolerance was proposed from the suite's own fixtures and then rejected on
real data, 2026-09-12 (owner decision). On live Keepa history for the same three
ASINs, the gap between an offer drop and the price point immediately preceding it,
across all 7 confirmed sales, was **3.0, 5.1, 10.2, 252.1, 389.6, 516.4 and 2281.4
hours** - bimodal, nothing between 10h and 252h, median 252.1h, max 95.1 days. A
240-hour threshold would have cut that at the median and discarded the majority.

The reason is that the price series is a **change-log**: a long gap means the lowest
offer had not changed, which makes the distant point **correct** rather than stale.
Gap length does not measure staleness. `NoTimeThreshold` pins the absence so
re-adding one has to be deliberate.

The fixtures here are deliberately SPARSE - two or three points per series, placed
at exact offsets from the drop - rather than the dense uniform grids the rest of the
suite uses. A dense grid cannot express "the only prior price point is 95 days old",
which is the shape that carried the widest real gap.

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
    infer_sale_events,
)

# The price the copy actually sold at, and the next listing up the stack. The round
# number is the point: $499.95 is a price a seller typed, which is why values like
# it, $1,000.00, $250.00 and $150.00 showed up on the box.
SOLD_AT_CENTS = 4995
NEXT_LISTING_CENTS = 49995

MINUTES_PER_HOUR = 60

# The seven preceding-gaps measured on real Keepa history, 2026-09-12, across the
# 7 confirmed sales of ASINs 1890919489, 1468308963 and 1429097078. Every one of
# these must still associate a price.
MEASURED_PRECEDING_GAPS_HOURS = (3.0, 5.1, 10.2, 252.1, 389.6, 516.4, 2281.4)

# The drop is 150 days back, far enough that the widest measured gap (2281.4h, 95.1
# days) still lands inside the 3-year inference window. Anchored on a whole Keepa
# minute so every offset below is exact rather than truncated.
SALE_KTM = int(((datetime.now() - timedelta(days=150)) - KEEPA_EPOCH)
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
        """`allow_exact_matches=False` is load-bearing, and the box proved it.

        4 of the 7 live sales had a price point sharing the EXACT minute of the
        offer drop (nearest gap 0.0h), so a zero-distance match is the single most
        common way to pick up the leftover asking price.
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


class DistantPrecedingPointsStillAssociate(_Silent):
    """A long gap means the price had not changed, so the point is correct.

    This class is the executable form of the box measurement that killed the
    240-hour tolerance. Every gap here is a real one.
    """

    def test_the_widest_measured_gap_still_associates(self):
        """2281.4 hours, 95.1 days: the widest real gap in the live sample.

        A 240-hour tolerance discarded this sale. It must not be discarded: the
        series is a change-log and this is simply a price that held for 95 days.
        """
        product = _product(used_price_points=[(_at(-2281.4), SOLD_AT_CENTS),
                                              (_at(0), NEXT_LISTING_CENTS)])
        events, drops = infer_sale_events(product)
        self.assertEqual(drops, 1)
        self.assertEqual(len(events), 1,
                         "A 95-day-old preceding price point must still be "
                         "associated. Gap length does not measure staleness.")
        self.assertEqual(int(events[0]['inferred_sale_price_cents']),
                         SOLD_AT_CENTS)

    def test_every_gap_measured_on_the_box_associates_a_price(self):
        """All 7 of the real preceding-gaps, including the 4 a tolerance would cut."""
        for gap in MEASURED_PRECEDING_GAPS_HOURS:
            with self.subTest(gap_hours=gap):
                product = _product(
                    used_price_points=[(_at(-gap), SOLD_AT_CENTS),
                                       (_at(0), NEXT_LISTING_CENTS)])
                events, drops = infer_sale_events(product)
                self.assertEqual(drops, 1)
                self.assertEqual(
                    len(events), 1,
                    "Gap of {}h lost its price. All 7 gaps measured on real "
                    "Keepa history must associate.".format(gap))
                self.assertEqual(
                    int(events[0]['inferred_sale_price_cents']), SOLD_AT_CENTS,
                    "Gap of {}h associated the wrong side of the drop.".format(gap))

    def test_the_gaps_a_two_forty_hour_tolerance_would_have_rejected(self):
        """Names the four explicitly, so the cost of re-adding one is visible."""
        would_have_been_cut = [g for g in MEASURED_PRECEDING_GAPS_HOURS if g > 240]
        self.assertEqual(
            len(would_have_been_cut), 4,
            "The live sample had 4 of 7 gaps above 240h. If this changes, the "
            "tolerance decision of 2026-09-12 was based on different data.")
        for gap in would_have_been_cut:
            with self.subTest(gap_hours=gap):
                product = _product(
                    used_price_points=[(_at(-gap), SOLD_AT_CENTS),
                                       (_at(0), NEXT_LISTING_CENTS)])
                events, _ = infer_sale_events(product)
                self.assertEqual(len(events), 1)


class NoPriorPointYieldsNoPrice(_Silent):
    """The one case in which a confirmed drop still loses its price.

    With no time threshold, this is the ONLY way the association fails: the drop
    precedes every point in the series. It was 0 of 7 on the live sample, which is
    why the Deal Trust and xAI-rescue consequences of this change are negligible.
    """

    def test_a_drop_with_no_prior_price_point_at_all_yields_no_sale(self):
        """The first drop in a history can precede every price point."""
        product = _product(used_price_points=[(_at(2), NEXT_LISTING_CENTS),
                                              (_at(96), NEXT_LISTING_CENTS)])
        events, drops, _ = self._infer_expecting_no_sales(product)
        self.assertEqual(events, [])
        self.assertEqual(drops, 1,
                         "The offer drop still happened. It must stay in the Deal "
                         "Trust denominator even though no price could be attached.")

    def test_that_failure_never_leaks_through_as_nan(self):
        """`merge_asof` returns NaN when the backward match finds nothing.

        `NaN <= 0` is False, so the pre-existing `price <= 0` guard does NOT catch
        it. A NaN reaching `confirmed_sales` would poison the IQR bounds, the mean
        and the mode for the whole ASIN.
        """
        product = _product(used_price_points=[(_at(2), NEXT_LISTING_CENTS)])
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


class NoTimeThreshold(unittest.TestCase):
    """Pin the ABSENCE of a tolerance, so re-adding one has to be deliberate.

    Same pattern as `tests/test_field_mappings_call_contract.py`'s pinning of
    `FUNCTION_LIST[10] = None`: "the association has no bound, let's add one" is an
    intuition that has already been tried and refuted by measurement. The next
    agent should have to read why before reversing it.
    """

    @staticmethod
    def _source():
        return open(os.path.join(
            os.path.dirname(os.path.abspath(__file__)), '..',
            'keepa_deals', 'stable_calculations.py')).read()

    def test_the_tolerance_constant_is_gone(self):
        import keepa_deals.stable_calculations as sc
        self.assertFalse(
            hasattr(sc, 'PRICE_ASSOCIATION_TOLERANCE_HOURS'),
            "The tolerance was rejected on real data 2026-09-12: 4 of 7 live "
            "preceding-gaps exceeded 240h, so the threshold would have discarded "
            "the majority of true sales. A long gap means the lowest offer had not "
            "changed, which makes the distant point correct rather than stale.")

    def test_the_association_passes_no_tolerance(self):
        source = self._source()
        self.assertIn("direction='backward'", source)
        self.assertIn('allow_exact_matches=False', source)
        self.assertNotIn(
            'tolerance=', source,
            "Gap length does not measure staleness. If a stale-price guard is "
            "wanted it needs continuity of the price series across the gap, not "
            "gap length - and that is an open item, not this change.")

    def test_the_reasoning_is_recorded_next_to_the_code(self):
        """A bare absence is indistinguishable from an oversight."""
        source = self._source()
        self.assertIn('NO TIME THRESHOLD', source)
        self.assertIn('2281.4', source,
                      "The widest measured gap belongs in the module, so the next "
                      "reader sees the evidence and not just the conclusion.")


if __name__ == '__main__':
    unittest.main()
