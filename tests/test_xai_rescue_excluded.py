"""The xAI sales rescue must never run from `infer_sale_events`.

WHY THIS FILE EXISTS
--------------------
Until 2026-09-16 `infer_sale_events` called `infer_sales_with_xai` on BOTH of its
zero-sale branches and returned the model's events verbatim. Owner decision,
Trello #141: that is not a true inferred sale, and it is excluded.

The reasoning lives in the block comment above `infer_sale_events` in
`keepa_deals/stable_calculations.py`. What this file does is make the absence
*executable*, because a removal that is only a deleted line comes back the moment
somebody re-adds an import while chasing deal volume.

THE FOUR FACTS PINNED HERE
--------------------------
1.  Neither zero-sale branch reaches xAI. Asserted twice over: by driving real
    histories through the real function with the network stubbed and a spy on
    every plausible entry point, and by reading the module's own source.
2.  `stable_calculations` does not import `infer_sales_with_xai` at all. This is
    the guard that actually holds, because it fails on the re-added import rather
    than waiting for a fixture that happens to reach the branch.
3.  Branch 2 - offer drops that all FAILED correlation - returns those drops as
    the `Deal Trust` denominator, so the column reads a truthful **0%**. The
    rescue used to return one model event over that same denominator, which read
    **1/N**: a positive confidence score built from drops that had just failed.
4.  Zero sales flows through to NULL pricing and `Inferred_Sale_Count = 0`, and
    the deal is PERSISTED rather than rejected (AGENTS.md 7.8). `0` means
    "computed, none found" and must stay distinguishable from NULL.

These tests FAIL on the parent commit (a082f43) and pass on this branch.

NOTE ON FIXTURE SHAPE: the histories here are built to reach a specific branch of
`infer_sale_events`, not to be realistic. `_no_offer_drops_product` has a
monotonically rising offer count; `_uncorrelated_drops_product` has offer drops
whose rank never improves anywhere in the confirmation, sparse-lookahead or
near-miss windows.
"""

import logging
import os
import sys
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import keepa_deals.stable_calculations as sc  # noqa: E402
from keepa_deals.stable_calculations import (  # noqa: E402
    KEEPA_EPOCH,
    analyze_sales_performance,
    deal_trust,
    infer_sale_events,
)

MINUTES_PER_HOUR = 60

# Anchor 200 days back, on a whole Keepa minute so the offsets below are exact.
# Every fixture then runs FORWARD from here to within a few days of now.
#
# The forward reach matters. The removed rescue only looked at the last 100 days
# (`format_history_for_xai(product, days=100)`) and returned None outright when it
# found nothing there. A fixture placed entirely before that window makes the
# rescue bail for the wrong reason, which would let these tests pass on the parent
# commit while proving nothing. These histories reach into the last 100 days, so on
# the parent the rescue genuinely fires.
ANCHOR_KTM = int(((datetime.now() - timedelta(days=200)) - KEEPA_EPOCH)
                 .total_seconds() // 60)


def _at(hours):
    """A Keepa minute `hours` from the anchor. Negative is before it."""
    return ANCHOR_KTM + int(round(hours * MINUTES_PER_HOUR))


def _flat(points):
    """[(ktm, value), ...] -> Keepa's flat [time, value, time, value, ...]."""
    out = []
    for ktm, value in points:
        out.extend([int(ktm), int(value)])
    return out


def _product(rank_points, used_offer_points, used_price_points, asin='XAIEXCLUDED'):
    csv_data = [None] * 13
    csv_data[2] = _flat(used_price_points)
    csv_data[3] = _flat(rank_points)
    csv_data[12] = _flat(used_offer_points)
    return {
        'asin': asin,
        'title': 'xAI rescue exclusion fixture',
        'categoryTree': [{'name': 'Books'}],
        'csv': csv_data,
        # Rank kept well under the old rescue's 2,000,000 "dead inventory" gate, so
        # a re-added rescue would genuinely fire rather than being skipped for an
        # unrelated reason. Amazon prices left at -1 so no ceiling moves anything.
        'stats': {'current': [-1, -1, 2999, 400000] + [-1] * 19,
                  'avg90': [-1] * 23, 'avg180': [-1] * 23, 'avg365': [-1] * 23},
    }


def _no_offer_drops_product():
    """Branch 1: the offer count never decreases, so there is no trigger at all.

    `infer_sale_events` bails at `if not all_offer_drops_list`. This used to call
    xAI and return `(events, 0)`.
    """
    days = 24
    rank_points = [(_at(i * days), 400000 - i * 5000) for i in range(8)]
    # Monotonically RISING offer count: nothing for `offer_diff < 0` to find.
    offer_points = [(_at(i * days), 3 + i) for i in range(8)]
    price_points = [(_at(i * days), 2999 + i * 50) for i in range(8)]
    return _product(
        rank_points=rank_points,
        used_offer_points=offer_points,
        used_price_points=price_points,
        asin='NOOFFERDROPS',
    )


def _uncorrelated_drops_product(drop_count=3):
    """Branch 2: real offer drops, none of which correlate with a rank drop.

    The rank series rises monotonically (gets WORSE) across the whole fixture, so
    no drop is confirmed by the 240h window, the 30-day sparse lookahead, or the
    72h near-miss check. `infer_sale_events` bails at `if not confirmed_sales`
    with `total_offer_drops_count == drop_count`. This used to call xAI and return
    `(events, drop_count)` - the 1/N Deal Trust defect.
    """
    offer_points = []
    rank_points = []
    price_points = []
    offers = 10
    rank = 300000
    for i in range(drop_count + 1):
        hours = i * 24 * 45  # 45 days apart: far outside every lookahead window
        # With ANCHOR at -200 days, drop_count=3 spans -200d to -65d and
        # drop_count=2 spans -200d to -110d. Both reach inside the old rescue's
        # 100-day window via the trailing rank/price points below.
        offer_points.append((_at(hours), offers))
        offers -= 1
        # Rank gets steadily worse, so `rank_diff < 0` is never true.
        rank_points.append((_at(hours), rank))
        rank += 20000
        price_points.append((_at(hours - 24), 2999 + i))
    return _product(
        rank_points=rank_points,
        used_offer_points=offer_points,
        used_price_points=price_points,
        asin='UNCORRELATED',
    )


# A sale the model would have asserted. Any of these reaching the pricing stage
# means the rescue ran.
INVENTED_PRICE_CENTS = 99999
INVENTED_SALE = [{'event_timestamp': datetime.now() - timedelta(days=5),
                  'inferred_sale_price_cents': INVENTED_PRICE_CENTS}]


class _RescueSpy:
    """Patch the rescue wherever it is reachable, and record whether it fired.

    Two entry points have to be covered, and which ones exist is the whole point:

      * `keepa_deals.xai_sales_inference.infer_sales_with_xai` - the definition.
        Always present. Patching it alone is NOT enough on the parent commit,
        because `stable_calculations` did `from ... import infer_sales_with_xai`,
        binding its own name at import time.
      * `keepa_deals.stable_calculations.infer_sales_with_xai` - the binding this
        PR removes. Patched ONLY if it exists, so this helper works on both sides
        of the change instead of raising AttributeError on one of them.

    `query_xai_sales_inference` is stubbed underneath either way, so no test in
    this file can reach the network even if a third entry point appears.

    The stub returns a real sale rather than None. That is deliberate: a stub
    returning None would let the parent commit pass these tests for the wrong
    reason (no sales either way). Returning a sale makes the parent's behaviour
    visibly different - events appear, and Deal Trust reads 1/N.
    """

    def __init__(self):
        self._patchers = []
        self.definition = None
        self.binding = None
        self.network = None

    def __enter__(self):
        import keepa_deals.xai_sales_inference as xsi

        targets = ['keepa_deals.xai_sales_inference.infer_sales_with_xai']
        if hasattr(sc, 'infer_sales_with_xai'):
            targets.append('keepa_deals.stable_calculations.infer_sales_with_xai')

        for target in targets:
            patcher = patch(target, return_value=list(INVENTED_SALE))
            self._patchers.append(patcher)
        net_patcher = patch.object(xsi, 'query_xai_sales_inference',
                                   return_value=None)
        self._patchers.append(net_patcher)
        # The pricing stage's OWN xAI call (the AI Reasonableness Check) is a
        # different mechanism and is not what this file is about, but an invented
        # $999.99 sale against a $29.99 current used price trips the 3x rule and
        # forces it. Stub it to True so the assertions below measure the rescue,
        # not the reasonableness check, and so no test here touches the network.
        self._patchers.append(
            patch.object(sc, '_query_xai_for_reasonableness', return_value=True))

        started = [p.start() for p in self._patchers]
        self.definition = started[0]
        self.binding = started[1] if len(targets) > 1 else None
        self.network = started[len(targets)]
        return self

    def __exit__(self, *exc):
        for patcher in reversed(self._patchers):
            patcher.stop()
        return False

    def assert_never_fired(self):
        assert not self.definition.called, (
            "keepa_deals.xai_sales_inference.infer_sales_with_xai was called.")
        assert self.binding is None or not self.binding.called, (
            "keepa_deals.stable_calculations.infer_sales_with_xai was called - "
            "the rescue has been re-wired into infer_sale_events.")
        assert not self.network.called, (
            "query_xai_sales_inference was called: something reached the xAI "
            "network layer from infer_sale_events.")


class _Silent(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)


class TheRescueIsNeverCalled(_Silent):
    """Drive the real function down both zero-sale branches with a spy attached."""

    def _assert_no_xai(self, product, expected_drops):
        """Run the inference with every xAI entry point stubbed and watched."""
        with _RescueSpy() as spy:
            events, drops = infer_sale_events(product)

        self.assertEqual(
            events, [],
            "A zero-sale branch produced sale events. The only thing that can "
            "manufacture a sale where the correlation loop found none is the xAI "
            "rescue - it has been re-wired into infer_sale_events.")
        self.assertEqual(
            drops, expected_drops,
            "The offer-drop count changed. That is the Deal Trust denominator.")
        spy.assert_never_fired()

    def test_branch_one_no_offer_drops_at_all(self):
        self._assert_no_xai(_no_offer_drops_product(), expected_drops=0)

    def test_branch_two_offer_drops_that_all_failed_correlation(self):
        self._assert_no_xai(_uncorrelated_drops_product(drop_count=3),
                            expected_drops=3)


class TheImportIsGone(unittest.TestCase):
    """The guard that actually holds: the name is not in `stable_calculations`.

    A fixture-driven test only fails if the fixture reaches the branch. This one
    fails on the re-added import itself, which is the real regression shape.
    """

    def test_stable_calculations_does_not_expose_the_rescue(self):
        self.assertFalse(
            hasattr(sc, 'infer_sales_with_xai'),
            "keepa_deals.stable_calculations imports infer_sales_with_xai again. "
            "The xAI sales rescue was removed on 2026-09-16 by owner decision "
            "(Trello #141); see the block comment above infer_sale_events.")

    def test_the_source_contains_no_call_to_the_rescue(self):
        source = open(sc.__file__, encoding='utf-8').read()
        code_lines = [
            line for line in source.splitlines()
            if 'infer_sales_with_xai' in line and not line.lstrip().startswith('#')
        ]
        self.assertEqual(
            code_lines, [],
            "A live (non-comment) reference to infer_sales_with_xai is back in "
            "stable_calculations.py: {}".format(code_lines))

    def test_the_reasoning_is_recorded_next_to_the_code(self):
        """Per AGENTS.md 6.2: the intent must survive the next reader.

        A removal with no recorded reason gets undone by the next person chasing
        deal volume. The same pattern as `NoTimeThreshold` in
        `tests/test_price_association.py`.
        """
        source = open(sc.__file__, encoding='utf-8').read()
        self.assertIn('THE XAI SALES RESCUE WAS REMOVED HERE', source)
        self.assertIn('2026-09-16', source)


class DealTrustTellsTheTruthOnBranchTwo(_Silent):
    """Offer drops still count in the denominator, and the numerator is honest."""

    def test_uncorrelated_drops_yield_zero_percent_not_one_over_n(self):
        product = _uncorrelated_drops_product(drop_count=3)
        with _RescueSpy():
            result = deal_trust(product)
        self.assertEqual(
            result, {'Deal Trust': '0%'},
            "Deal Trust must read 0% when no offer drop correlated with a rank "
            "drop. The rescue used to put one model-asserted event over this "
            "same denominator, reading 33% here.")

    def test_two_drops_would_have_read_fifty_percent_under_the_rescue(self):
        """The sharpest case: N=2 put a rescued row above the Agent's Choice floor.

        `/api/deals` requires `Deal_Trust >= 40` for the Agent's Choice filter
        (wsgi_handler.py). One rescued event over two failed drops read 50% and
        cleared it.
        """
        product = _uncorrelated_drops_product(drop_count=2)
        with _RescueSpy():
            events, drops = infer_sale_events(product)
            trust = deal_trust(product)
        self.assertEqual(events, [])
        self.assertEqual(drops, 2)
        self.assertEqual(trust, {'Deal Trust': '0%'})

    def test_branch_one_still_reports_the_non_numeric_state(self):
        """No offer drops means no denominator, which is '-', not 0%.

        Unchanged by this PR, pinned because the two branches now differ only in
        their denominator and it would be easy to collapse them.
        """
        with _RescueSpy():
            trust = deal_trust(_no_offer_drops_product())
        self.assertEqual(trust, {'Deal Trust': '-'})


class ZeroSalesReachesThePricingStageAsZero(_Silent):
    """Persisted with NULL pricing and a countable zero - not rejected."""

    def _analysis(self, product):
        with _RescueSpy():
            sale_events, _ = infer_sale_events(product)
            return analyze_sales_performance(product, sale_events)

    def test_no_offer_drops_yields_null_price_and_zero_count(self):
        analysis = self._analysis(_no_offer_drops_product())
        self.assertEqual(analysis['peak_price_mode_cents'], -1)
        self.assertEqual(analysis['inferred_sale_count'], 0)
        self.assertEqual(analysis['price_source'], 'None')

    def test_uncorrelated_drops_yield_null_price_and_zero_count(self):
        analysis = self._analysis(_uncorrelated_drops_product(drop_count=3))
        self.assertEqual(analysis['peak_price_mode_cents'], -1)
        self.assertEqual(analysis['inferred_sale_count'], 0)

    def test_the_count_is_zero_not_none(self):
        """`0` is 'computed, none found'. NULL is 'never computed'.

        Data_Logic.md and INFERRED_PRICE_LOGIC.md both require these to stay
        distinguishable: NULL must never be read as zero or used to hide a deal.
        """
        analysis = self._analysis(_no_offer_drops_product())
        self.assertIsNotNone(analysis['inferred_sale_count'])
        self.assertIsInstance(analysis['inferred_sale_count'], int)

    def test_no_price_is_invented_from_the_history(self):
        """The pricing stage must not reach for anything when there are no sales.

        AGENTS.md 7.1: no listing average, no Amazon price, no default, on any
        path. With the rescue gone this is the branch every zero-sale deal takes,
        so it is worth pinning here as well as in test_1yr_avg_no_fallback.py.
        """
        product = _uncorrelated_drops_product(drop_count=3)
        # Give the product rich Keepa stats. If anything reaches for them, the
        # price stops being -1.
        product['stats']['avg365'] = [50000] * 23
        product['stats']['avg180'] = [50000] * 23
        analysis = self._analysis(product)
        self.assertEqual(analysis['peak_price_mode_cents'], -1)


if __name__ == '__main__':
    unittest.main()
