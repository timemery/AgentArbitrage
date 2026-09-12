"""Every FUNCTION_LIST entry must be callable the way processing.py actually calls it.

WHAT THIS WOULD HAVE CAUGHT
---------------------------
`field_mappings.FUNCTION_LIST` index 10 held `stable_deals.last_update`, whose signature
was `last_update(deal_object, logger_param, product_data=None)` with no default on
`logger_param`. The generic extraction loop in `processing.py` calls every entry as
`func(product_data)` - one positional argument - so the call raised TypeError on **every**
heavy-path deal from the day the entry was added. Nothing stored the `last_update`
column, and the `@retry(stop_max_attempt_number=3, wait_fixed=5000)` on the function
turned that permanent error into two 5-second sleeps per newly discovered deal.

It was invisible because `_process_single_deal` catches the exception per field and logs
a warning, so the pipeline carried on and only the column and the wall clock suffered.

The defect is a *signature* mismatch, so the guard is a signature check over the whole
list rather than a test of one function. A new entry that needs a second required
argument fails here instead of silently costing 10 seconds a deal in production.
"""

import inspect
import json
import os
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from keepa_deals.field_mappings import FUNCTION_LIST  # noqa: E402
from keepa_deals.stable_deals import last_update  # noqa: E402

HEADERS_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'keepa_deals', 'headers.json')

with open(HEADERS_PATH) as _f:
    HEADERS = json.load(_f)


def _product_fixture():
    """A product dict shaped like what `_process_single_deal` receives.

    `smart_ingestor.run()` merges the Keepa deal object into the product with
    `product_data.update(deal)` before calling `_process_single_deal`, so top-level
    deal keys such as `lastUpdate` and `currentSince` are present alongside the
    product's own `stats` and `csv`.

    `csv` is deliberately left as a list of empty slots: `infer_sale_events` returns
    early on it, which keeps the pricing entries off the xAI rescue branch and makes
    this test hermetic.
    """
    empty_tier = [-1] * 40
    return {
        'asin': 'B0TESTASIN',
        'title': 'A Test Book',
        'manufacturer': 'A Publisher',
        'lastUpdate': 7_000_000,
        'currentSince': [-1] * 40,
        'stats': {
            'current': list(empty_tier),
            'avg30': list(empty_tier),
            'avg90': list(empty_tier),
            'avg180': list(empty_tier),
            'avg365': list(empty_tier),
            'min': [],
            'lastOffersUpdate': 7_100_000,
            'salesRankDrops30': 2,
            'salesRankDrops180': 8,
            'salesRankDrops365': 12,
        },
        'csv': [None] * 35,
        'offers': [],
        'categoryTree': [],
    }


class FunctionListCallContractTest(unittest.TestCase):
    """`processing.py` calls every entry as `func(product_data)`. Hold it to that."""

    def _entries(self):
        for index, func in enumerate(FUNCTION_LIST):
            if func is None:
                continue
            header = HEADERS[index] if index < len(HEADERS) else '<no header>'
            yield index, header, func

    def test_function_list_and_headers_stay_aligned(self):
        """A length mismatch would silently shift every column's label."""
        self.assertEqual(
            len(HEADERS), len(FUNCTION_LIST),
            "headers.json and FUNCTION_LIST must stay index-aligned; a None slot is "
            "required for every header with no field function.")

    def test_every_entry_accepts_a_single_positional_argument(self):
        """The signature check. This is the one that fails on the last_update shape."""
        product_data = _product_fixture()
        broken = []
        for index, header, func in self._entries():
            try:
                inspect.signature(func).bind(product_data)
            except TypeError as exc:
                broken.append(
                    "  FUNCTION_LIST[{}] ({!r}) -> {}.{}{}: {}".format(
                        index, header, func.__module__, func.__name__,
                        inspect.signature(func), exc))
        self.assertEqual(
            [], broken,
            "processing.py calls every field function as func(product_data), with one "
            "positional argument. These entries cannot accept that, so they raise "
            "TypeError on every deal and store nothing:\n" + "\n".join(broken))

    def test_no_entry_raises_type_error_when_called(self):
        """Call each entry for real, exactly as the generic loop does."""
        product_data = _product_fixture()
        raised = []
        # Force the xAI rescue off so the pricing entries cannot reach the network,
        # whatever the ambient environment holds.
        with patch.dict(os.environ, {'XAI_TOKEN': ''}):
            for index, header, func in self._entries():
                try:
                    func(product_data)
                except TypeError as exc:
                    raised.append(
                        "  FUNCTION_LIST[{}] ({!r}) -> {}.{}: {}".format(
                            index, header, func.__module__, func.__name__, exc))
                except Exception:
                    # Thin fixture data legitimately produces the '-' sentinel and, on
                    # some entries, a value error on the way there. Only the call
                    # contract is under test here.
                    pass
        self.assertEqual(
            [], raised,
            "these field functions raised TypeError when called the way processing.py "
            "calls them:\n" + "\n".join(raised))

    def test_calling_the_whole_list_costs_no_retry_sleeps(self):
        """The 10 seconds per deal, expressed as a test rather than as wall clock.

        `last_update` carried @retry(stop_max_attempt_number=3, wait_fixed=5000), so its
        TypeError cost two 5-second sleeps on every newly discovered deal. Asserting on
        elapsed time would be flaky; asserting that nothing in the list sleeps is not.
        """
        product_data = _product_fixture()
        with patch.dict(os.environ, {'XAI_TOKEN': ''}), \
                patch.object(time, 'sleep') as mock_sleep:
            for _index, _header, func in self._entries():
                try:
                    func(product_data)
                except Exception:
                    pass
        self.assertEqual(
            0, mock_sleep.call_count,
            "a field function slept while being called. A retry decorator on a function "
            "whose failure is permanent burns wall clock on every deal and fixes "
            "nothing; {} sleep(s) requested: {}".format(
                mock_sleep.call_count, mock_sleep.call_args_list))


class LastUpdateCallContractTest(unittest.TestCase):
    """The specific entry the contract was broken on."""

    def test_last_update_runs_and_returns_a_timestamp(self):
        result = last_update(_product_fixture())
        self.assertIsInstance(result, dict)
        self.assertIn('last update', result)
        # 7,000,000 Keepa minutes after 2011-01-01 UTC, rendered in America/Toronto.
        self.assertEqual('2024-04-22 22:40:00', result['last update'])

    def test_last_update_reports_missing_data_with_the_sentinel(self):
        product_data = _product_fixture()
        del product_data['lastUpdate']
        self.assertEqual({'last update': '-'}, last_update(product_data))

    def test_a_failure_in_last_update_does_not_sleep(self):
        """No retry decorator. Its failure modes are permanent, so retrying only waits."""
        with patch.object(time, 'sleep') as mock_sleep:
            with self.assertRaises(AttributeError):
                last_update(None)
        self.assertEqual(
            0, mock_sleep.call_count,
            "last_update retried a permanent failure. Each retry is a wait_fixed sleep "
            "on the heavy path, which is what cost 10 seconds per newly discovered deal.")


if __name__ == '__main__':
    unittest.main()
