"""`Pricing_Logic_Version` must be written by the heavy path and nobody else.

WHY THIS FILE EXISTS
--------------------
Trello #139. Nothing in the deals table dates a row's pricing - `last_seen_utc`
and `source` are rewritten by all three paths, `Deal_found` is Keepa's creation
time, and `Inferred_Sale_Count` is disproved by ASIN 0415009804, which carries a
count AND a pre-fix price. So a version stamp was added, and its value is entirely
in WHERE it is written.

THE ONE THING THAT MATTERS: only `_process_single_deal` may stamp it, because that
is the only place `List_at` and `1yr_Avg` are computed. A light update that
stamped the current version would claim a row's prices are current when nothing
recomputed them - which is worse than having no column at all, because
`repair_pricing.py` would then skip exactly the rows that need repair.

These tests FAIL on the parent commit (ddd8c15), where the column does not exist.
"""

import json
import logging
import os
import sys
import unittest
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals.pricing_version import (  # noqa: E402
    PRICING_LOGIC_VERSION,
    PRICING_VERSION_COLUMN,
    PRICING_VERSION_HEADER,
    STALE_PRICING_PREDICATE,
)

HEADERS_PATH = os.path.join(os.path.dirname(__file__), '..', 'keepa_deals',
                            'headers.json')


class TheColumnExistsAndIsWired(unittest.TestCase):
    """Schema plumbing: the header, the FUNCTION_LIST slot, and the DB type."""

    def test_the_header_is_present_exactly_once(self):
        with open(HEADERS_PATH) as fh:
            headers = json.load(fh)
        self.assertEqual(headers.count(PRICING_VERSION_HEADER), 1)

    def test_function_list_stays_index_aligned_with_headers(self):
        """The generic loop pairs them BY INDEX (`row_data[headers[i]] = val`).

        A length mismatch silently writes values into the wrong columns, which is
        the failure mode AGENTS.md 7.12 exists to prevent.
        """
        from keepa_deals.field_mappings import FUNCTION_LIST
        with open(HEADERS_PATH) as fh:
            headers = json.load(fh)
        self.assertEqual(len(FUNCTION_LIST), len(headers))

    def test_the_slot_is_none_because_processing_writes_it_explicitly(self):
        from keepa_deals.field_mappings import FUNCTION_LIST
        with open(HEADERS_PATH) as fh:
            headers = json.load(fh)
        self.assertIsNone(FUNCTION_LIST[headers.index(PRICING_VERSION_HEADER)])

    def test_the_header_sanitizes_to_the_documented_column_name(self):
        from keepa_deals.db_utils import sanitize_col_name
        self.assertEqual(sanitize_col_name(PRICING_VERSION_HEADER),
                         PRICING_VERSION_COLUMN)

    def test_it_is_an_integer_column_not_text(self):
        """TEXT would compare lexically, so '10' < '9' once the version reaches 10.

        The type comes from a keyword rule in db_utils; 'Version' had to be added
        to it, and both copies of that rule (create-if-missing and recreate) have
        to agree.
        """
        import sqlite3
        import tempfile
        import importlib
        tmp = tempfile.mkdtemp()
        with patch.dict(os.environ,
                        {'DATABASE_URL': os.path.join(tmp, 'dev_deals.db')}):
            from keepa_deals import db_utils
            importlib.reload(db_utils)
            try:
                db_utils.recreate_deals_table()
                con = sqlite3.connect(db_utils.DB_PATH)
                try:
                    info = {r[1]: r[2] for r in
                            con.execute('PRAGMA table_info(deals)')}
                finally:
                    con.close()
                self.assertEqual(info.get(PRICING_VERSION_COLUMN), 'INTEGER')
            finally:
                importlib.reload(db_utils)


class OnlyTheHeavyPathStampsIt(unittest.TestCase):
    """The load-bearing assertion of this whole feature."""

    def setUp(self):
        logging.disable(logging.CRITICAL)

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_the_heavy_path_writes_the_current_version(self):
        from keepa_deals import processing
        source = open(processing.__file__, encoding='utf-8').read()
        # Current version unless the price could not be verified (Trello #144),
        # in which case NULL - see tests/test_xai_fail_closed.py.
        self.assertIn("list_at_analysis.get('price_unverified')", source)
        self.assertIn("list_at_analysis.get('thin_peak_season')", source)
        self.assertIn("else PRICING_LOGIC_VERSION)",
                      source,
                      "_process_single_deal must stamp the version beside "
                      "Inferred Sale Count.")

    def test_the_light_path_never_writes_it(self):
        """`_process_lightweight_update` recomputes no price, so it may not stamp.

        Asserted against the function's own source rather than a fixture, because
        a fixture only catches the write if it happens to reach that branch.
        """
        import inspect
        from keepa_deals.processing import _process_lightweight_update
        source = inspect.getsource(_process_lightweight_update)
        self.assertNotIn(PRICING_VERSION_HEADER, source)
        self.assertNotIn(PRICING_VERSION_COLUMN, source)
        self.assertNotIn('PRICING_LOGIC_VERSION', source)

    def test_the_stale_rescue_and_ingestor_never_write_it(self):
        """Stale Rescue routes to the light path and must not stamp either."""
        from keepa_deals import smart_ingestor
        source = open(smart_ingestor.__file__, encoding='utf-8').read()
        code = [ln for ln in source.splitlines()
                if 'PRICING_LOGIC_VERSION' in ln or PRICING_VERSION_COLUMN in ln]
        self.assertEqual(code, [],
                         "smart_ingestor must not stamp the pricing version; "
                         "only _process_single_deal may: {}".format(code))

    def test_the_recalculator_and_janitor_never_write_it(self):
        from keepa_deals import recalculator, janitor
        for module in (recalculator, janitor):
            source = open(module.__file__, encoding='utf-8').read()
            self.assertNotIn('PRICING_LOGIC_VERSION', source, module.__name__)
            self.assertNotIn(PRICING_VERSION_COLUMN, source, module.__name__)

    def test_a_light_update_leaves_a_stored_version_untouched(self):
        """Behavioural counterpart to the source checks above.

        A light update builds its row from `dict(sqlite3.Row)`, so whatever the
        heavy path stamped rides along unchanged - it is preserved, not refreshed.
        That is the correct behaviour: the row's prices are still whatever the
        heavy path computed.
        """
        from keepa_deals.processing import _process_lightweight_update
        existing = {'ASIN': 'LIGHTKEEP', PRICING_VERSION_COLUMN: 1,
                    'List_at': 999.99, '1yr_Avg': '999.99',
                    'Sales_Rank_Current': 100000, 'Offers': '5'}
        product = {'asin': 'LIGHTKEEP', 'title': 'x',
                   'stats': {'current': [-1] * 23, 'avg30': [-1] * 23,
                             'avg90': [-1] * 23, 'avg180': [-1] * 23,
                             'avg365': [-1] * 23}}
        row = _process_lightweight_update(existing, product)
        if row is not None:
            self.assertEqual(row.get(PRICING_VERSION_COLUMN), 1,
                             "The light path must neither bump nor clear the "
                             "stored version.")


class TheStalePredicate(unittest.TestCase):
    """What `repair_pricing.py` selects."""

    def test_null_counts_as_stale(self):
        self.assertIn('IS NULL', STALE_PRICING_PREDICATE)

    def test_an_older_version_counts_as_stale(self):
        self.assertIn('< {}'.format(PRICING_LOGIC_VERSION),
                      STALE_PRICING_PREDICATE)

    def test_it_selects_null_and_older_but_not_current(self):
        import sqlite3
        con = sqlite3.connect(':memory:')
        con.execute('CREATE TABLE deals ("ASIN" TEXT, "{}" INTEGER)'
                    .format(PRICING_VERSION_COLUMN))
        con.executemany('INSERT INTO deals VALUES (?, ?)', [
            ('LEGACY', None),
            ('OLDVER', PRICING_LOGIC_VERSION - 1),
            ('CURRENT', PRICING_LOGIC_VERSION),
            ('FUTURE', PRICING_LOGIC_VERSION + 1),
        ])
        got = [r[0] for r in con.execute(
            'SELECT "ASIN" FROM deals WHERE {} ORDER BY "ASIN"'
            .format(STALE_PRICING_PREDICATE))]
        con.close()
        self.assertEqual(got, ['LEGACY', 'OLDVER'],
                         "NULL and older versions are stale; the current version "
                         "and anything ahead of it are not.")

    def test_a_future_version_is_never_selected(self):
        """Guards against a rollback re-fetching the whole database.

        If the code is rolled back to an older PRICING_LOGIC_VERSION, rows stamped
        by the newer one must be left alone rather than 'repaired' backwards.
        """
        self.assertNotIn('>', STALE_PRICING_PREDICATE)
        self.assertNotIn('!=', STALE_PRICING_PREDICATE)


class TheVersionConstantIsDocumented(unittest.TestCase):
    """The rules live next to the constant, per AGENTS.md 6.2."""

    def test_the_null_rule_is_recorded(self):
        from keepa_deals import pricing_version
        doc = pricing_version.__doc__
        self.assertIn('STALE PRICING', doc)
        self.assertIn('Inferred_Sale_Count', doc,
                      "The contrast with the other NULL rule must be explicit, "
                      "or someone will 'harmonise' them.")
        self.assertIn('NO BACKFILL', doc)

    def test_the_version_is_an_integer_above_one(self):
        self.assertIsInstance(PRICING_LOGIC_VERSION, int)
        self.assertGreaterEqual(PRICING_LOGIC_VERSION, 2)


if __name__ == '__main__':
    unittest.main()
