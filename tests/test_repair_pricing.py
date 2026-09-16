"""`repair_pricing.py` must repair, resume and preview without surprises.

WHY THIS FILE EXISTS
--------------------
Trello #139. This script runs for DAYS against the production database, unattended,
alongside normal ingestion. Three of its properties are load-bearing and none of
them are obvious from reading it:

  1.  A DRY RUN WRITES NOTHING. It still spends Keepa tokens, so the temptation to
      "just let it run" is real; if it also wrote, the safety valve would be
      decorative.
  2.  AN INTERRUPTED RUN RESUMES WITHOUT REDOING WORK. There is no checkpoint
      file: resumption falls out of the predicate, because a repaired row carries
      the current version and stops matching. If that ever stopped being true the
      script would loop on the same rows forever, burning tokens.
  3.  IT NEVER USES `_merge_db_keyed`. That is the LIGHT path's preservation
      helper - it skips a value rather than overwriting a stored one, which would
      protect exactly the stale `List_at` this script exists to replace. Using it
      would make the script a very expensive no-op.

Also pinned here: the heavy path's overwrite semantics, which are what let the
script work at all. A re-fetch that now finds zero sales must write NULL prices and
a zero count, not leave the old values in place.

These tests FAIL on the parent commit (ddd8c15), where neither the script nor the
version column exists.
"""

import importlib
import json
import logging
import os
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import repair_pricing as R  # noqa: E402
from keepa_deals.pricing_version import (  # noqa: E402
    PRICING_LOGIC_VERSION,
    PRICING_VERSION_COLUMN,
    STALE_PRICING_PREDICATE,
)

HEADERS_PATH = os.path.join(os.path.dirname(__file__), '..', 'keepa_deals',
                            'headers.json')


def _col_type(header):
    """The same type rule `db_utils` applies, mirrored so the fixture agrees.

    It matters here: `Inferred_Sale_Count` is INTEGER in production (the "Count"
    keyword), so a fixture that made it TEXT would compare `'0' != 0` and hide the
    thing the test is checking.
    """
    real = ["Price", "Cost", "Fee", "Fees", "Profit", "Margin", "List at",
            "Total AMZ fees", "Total_AMZ_fees"]
    if any(k.lower() in header.lower() for k in real):
        return 'REAL'
    if ("Rank" in header or "Count" in header or "Drops" in header
            or "Version" in header):
        return 'INTEGER'
    return 'TEXT'


def _build_db(path, rows):
    """A deals table with the real schema, from headers.json.

    Built through `sanitize_col_name` - the same transform that CREATEs the real
    table - so a fixture cannot encode a different column convention than
    production uses (AGENTS.md 7.12).
    """
    from keepa_deals.db_utils import sanitize_col_name
    with open(HEADERS_PATH) as fh:
        headers = json.load(fh)
    cols = []
    for h in headers:
        name = sanitize_col_name(h)
        if name == 'ASIN':
            continue
        cols.append('"{}" {}'.format(name, _col_type(h)))
    # `last_seen_utc` and `source` are already IN headers.json, so they arrive
    # through the loop above. Appending them again would be a duplicate column.
    con = sqlite3.connect(path)
    con.execute('CREATE TABLE deals (id INTEGER PRIMARY KEY AUTOINCREMENT, '
                '"ASIN" TEXT NOT NULL UNIQUE, {})'.format(', '.join(cols)))
    for row in rows:
        keys = ['"{}"'.format(k) for k in row]
        con.execute('INSERT INTO deals ({}) VALUES ({})'
                    .format(', '.join(keys), ', '.join('?' * len(row))),
                    tuple(row.values()))
    con.commit()
    con.close()


def _row(asin, version=None, list_at=None, yr_avg=None, profit=None, count=None):
    row = {'ASIN': asin}
    if version is not None:
        row[PRICING_VERSION_COLUMN] = version
    if list_at is not None:
        row['List_at'] = list_at
    if yr_avg is not None:
        row['1yr_Avg'] = yr_avg
    if profit is not None:
        row['Profit'] = profit
    if count is not None:
        row['Inferred_Sale_Count'] = count
    return row


class _Silent(unittest.TestCase):
    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, 'dev_deals.db')

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def _targets(self, limit=50):
        sql = R.build_target_sql(STALE_PRICING_PREDICATE)
        return R.fetch_targets(self.db, sql, limit)


class SelectionAndOrder(_Silent):
    """What it picks, and in what order."""

    def test_it_selects_null_and_older_versions_only(self):
        _build_db(self.db, [
            _row('LEGACY01', list_at='10.0'),
            _row('OLDVER01', version=PRICING_LOGIC_VERSION - 1, list_at='10.0'),
            _row('CURRENT1', version=PRICING_LOGIC_VERSION, list_at='10.0'),
        ])
        got = sorted(t['ASIN'] for t in self._targets())
        self.assertEqual(got, ['LEGACY01', 'OLDVER01'])

    def test_visible_rows_come_first_then_priced_desc_then_unpriced(self):
        """Order is the whole point of the tiering: worst-seen damage first."""
        _build_db(self.db, [
            _row('UNPRICED', ),
            _row('PRICEDLO', list_at='60.0'),
            _row('PRICEDHI', list_at='900.0'),
            _row('VISIBLE1', list_at='70.0', yr_avg='70.0', profit='$25.00'),
        ])
        got = [t['ASIN'] for t in self._targets()]
        self.assertEqual(got, ['VISIBLE1', 'PRICEDHI', 'PRICEDLO', 'UNPRICED'])

    def test_the_tier_is_reported_so_the_log_shows_why(self):
        _build_db(self.db, [
            _row('VISIBLE1', list_at='70.0', yr_avg='70.0', profit='$25.00'),
            _row('UNPRICED'),
        ])
        tiers = {t['ASIN']: t['tier'] for t in self._targets()}
        self.assertEqual(tiers['VISIBLE1'], 0)
        self.assertEqual(tiers['UNPRICED'], 2)


class ResumesWithoutRedoingWork(_Silent):
    """No checkpoint file: resumption falls out of the predicate."""

    def test_a_repaired_row_stops_matching(self):
        _build_db(self.db, [
            _row('DONE0001', list_at='10.0'),
            _row('TODO0001', list_at='10.0'),
        ])
        self.assertEqual(len(self._targets()), 2)

        con = sqlite3.connect(self.db)
        con.execute('UPDATE deals SET "{}" = ? WHERE "ASIN" = ?'
                    .format(PRICING_VERSION_COLUMN),
                    (PRICING_LOGIC_VERSION, 'DONE0001'))
        con.commit()
        con.close()

        got = [t['ASIN'] for t in self._targets()]
        self.assertEqual(got, ['TODO0001'],
                         "A repaired row must drop out of the predicate, or a "
                         "resumed run redoes it and burns tokens forever.")

    def test_an_interrupted_run_resumes_from_where_it_stopped(self):
        """Simulates: batch 1 committed, process killed, run again."""
        _build_db(self.db, [_row('A0000001', list_at='500.0'),
                            _row('B0000002', list_at='400.0'),
                            _row('C0000003', list_at='300.0')])
        first = [t['ASIN'] for t in self._targets(limit=1)]
        self.assertEqual(first, ['A0000001'])

        con = sqlite3.connect(self.db)
        con.execute('UPDATE deals SET "{}" = ? WHERE "ASIN" = ?'
                    .format(PRICING_VERSION_COLUMN),
                    (PRICING_LOGIC_VERSION, first[0]))
        con.commit()
        con.close()

        second = [t['ASIN'] for t in self._targets(limit=1)]
        self.assertEqual(second, ['B0000002'])
        remaining = sorted(t['ASIN'] for t in self._targets())
        self.assertEqual(remaining, ['B0000002', 'C0000003'])

    def test_the_target_list_is_a_function_not_a_snapshot(self):
        """It must be re-derivable per batch: the Janitor deletes mid-run."""
        self.assertTrue(callable(R.build_target_sql))
        self.assertTrue(callable(R.fetch_targets))


class TheDryRunWritesNothing(_Silent):
    """The safety valve, asserted rather than trusted."""

    def _fake_pipeline(self, new_list_at):
        """Patch the heavy pipeline so no network or Keepa key is needed."""
        product = {'asin': 'DRYRUN01', 'title': 'x'}
        row = {'List_at': new_list_at, '1yr_Avg': str(new_list_at),
               'Inferred_Sale_Count': 4, 'Deal_Trust': '80%',
               PRICING_VERSION_COLUMN: PRICING_LOGIC_VERSION}
        return patch.multiple(
            'repair_pricing',
            **{}  # nothing module-level to patch; see the context managers below
        ), product, row

    def _run_batch(self, apply_changes):
        from keepa_deals.db_utils import sanitize_col_name  # noqa: F401
        targets = self._targets()
        processed = {'List_at': 42.0, '1yr_Avg': '42.0',
                     'Inferred_Sale_Count': 4, 'Deal_Trust': '80%',
                     PRICING_VERSION_COLUMN: PRICING_LOGIC_VERSION}

        class _TM:
            REFILL_RATE_PER_MINUTE = 25.0

            def request_permission_for_call(self, cost):
                pass

            def update_after_call(self, left):
                pass

        with patch('keepa_deals.keepa_api.fetch_product_batch') as fetch, \
             patch('keepa_deals.processing._process_single_deal') as heavy, \
             patch('keepa_deals.processing.clean_numeric_values',
                   side_effect=lambda r: r), \
             patch('keepa_deals.db_utils.to_db_keys', side_effect=lambda r: r), \
             patch('keepa_deals.seller_info.get_seller_info_for_single_deal',
                   return_value={}), \
             patch('keepa_deals.db_utils.DB_PATH', self.db):
            fetch.return_value = (
                {'products': [{'asin': t['ASIN']} for t in targets]},
                {}, 0, 100)
            heavy.return_value = dict(processed)
            return R.repair_batch(targets, 'key', None, _TM(), 10, apply_changes)

    def test_dry_run_leaves_every_stored_value_unchanged(self):
        _build_db(self.db, [_row('DRYRUN01', list_at='999.0', yr_avg='999.0')])
        before = sqlite3.connect(self.db).execute(
            'SELECT "List_at", "1yr_Avg", "{}" FROM deals'
            .format(PRICING_VERSION_COLUMN)).fetchone()
        self._run_batch(apply_changes=False)
        after = sqlite3.connect(self.db).execute(
            'SELECT "List_at", "1yr_Avg", "{}" FROM deals'
            .format(PRICING_VERSION_COLUMN)).fetchone()
        self.assertEqual(before, after,
                         "A dry run must not write. It spends Keepa tokens, so "
                         "the temptation to let it run unattended is real.")

    def test_dry_run_still_reports_what_it_would_have_written(self):
        _build_db(self.db, [_row('DRYRUN01', list_at='999.0', yr_avg='999.0')])
        _, outcomes = self._run_batch(apply_changes=False)
        self.assertEqual(len(outcomes), 1)
        self.assertEqual(outcomes[0]['old_list_at'], 999.0)
        self.assertEqual(outcomes[0]['new_list_at'], 42.0)

    def test_apply_requires_an_explicit_flag(self):
        parsed = R.argparse.ArgumentParser()  # sanity: argparse is imported
        self.assertIsNotNone(parsed)
        source = open(R.__file__, encoding='utf-8').read()
        self.assertIn("'--apply', action='store_true'", source)


class NeverUsesTheLightPathsPreservationHelper(unittest.TestCase):
    """`_merge_db_keyed` would protect the very value being replaced."""

    def test_the_script_never_calls_merge_db_keyed(self):
        """The name appears in prose explaining why it is NOT used; a CALL is the
        regression. Asserting on the mention would forbid documenting the reason.
        """
        source = open(R.__file__, encoding='utf-8').read()
        calls = [ln for ln in source.splitlines() if '_merge_db_keyed(' in ln]
        self.assertEqual(calls, [],
                         "repair_pricing must overwrite, not preserve: {}"
                         .format(calls))

    def test_the_reason_is_recorded_next_to_the_code(self):
        """Per AGENTS.md 6.2 - otherwise someone 'fixes' it back in."""
        source = open(R.__file__, encoding='utf-8').read()
        self.assertIn('_merge_db_keyed', source)
        self.assertIn('LIGHT path', source)

    def test_it_uses_the_shared_upsert_helper(self):
        """AGENTS.md 7.12: never hand-roll the deals upsert SQL at a call site."""
        source = open(R.__file__, encoding='utf-8').read()
        self.assertIn('upsert_deal_rows', source)
        self.assertNotIn('INSERT INTO deals', source)

    def test_it_never_takes_the_smart_ingestor_lock(self):
        """Holding it for days would block every ingestion cycle."""
        source = open(R.__file__, encoding='utf-8').read()
        self.assertNotIn('LOCK_KEY', source)
        self.assertNotIn('smart_ingestor_lock', source)


class HeavyOverwriteSemantics(unittest.TestCase):
    """What makes the repair possible: the heavy path replaces, including NULLs.

    If a re-fetch now finds zero sales, the row must end up NULL-priced with a
    zero count - not holding its old inflated price. That is the single most
    important behaviour the sweep depends on.
    """

    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def test_a_missing_key_binds_null_through_the_real_upsert(self):
        from keepa_deals import db_utils
        with open(HEADERS_PATH) as fh:
            headers = json.load(fh)
        db = os.path.join(self.tmp, 'dev_deals.db')
        _build_db(db, [_row('ZEROSALE', list_at='999.0', yr_avg='999.0',
                            count=7)])

        # The shape the heavy path produces for a zero-sale deal: List_at set to
        # None, 1yr_Avg key ABSENT entirely, count 0.
        row = {'ASIN': 'ZEROSALE', 'List_at': None,
               'Inferred_Sale_Count': 0, 'Deal_Trust': '0%',
               PRICING_VERSION_COLUMN: PRICING_LOGIC_VERSION}
        con = sqlite3.connect(db)
        cur = con.cursor()
        db_utils.upsert_deal_rows(cur, [row], headers)
        con.commit()
        got = cur.execute(
            'SELECT "List_at", "1yr_Avg", "Inferred_Sale_Count", "{}" '
            'FROM deals WHERE "ASIN" = ?'.format(PRICING_VERSION_COLUMN),
            ('ZEROSALE',)).fetchone()
        con.close()

        self.assertIsNone(got[0], "List_at must be overwritten with NULL.")
        self.assertIsNone(got[1],
                          "1yr_Avg must be NULLed by key ABSENCE, which is how "
                          "the heavy path reports 'no value'.")
        self.assertEqual(got[2], 0,
                         "0 means 'computed, none found' - not NULL, and not the "
                         "stale 7.")
        self.assertEqual(got[3], PRICING_LOGIC_VERSION)


class OperatorAffordances(unittest.TestCase):
    """The things that matter only because it runs for days, unattended."""

    def test_it_installs_handlers_for_sigterm_and_sigint(self):
        self.assertTrue(hasattr(R, 'GracefulStop'))
        source = open(R.__file__, encoding='utf-8').read()
        self.assertIn('signal.SIGTERM', source)
        self.assertIn('signal.SIGINT', source)

    def test_it_logs_to_its_own_file_not_the_celery_log(self):
        self.assertTrue(R.DEFAULT_LOG_PATH.endswith('repair_pricing.log'))
        self.assertNotIn('celery', R.DEFAULT_LOG_PATH.lower())

    def test_it_stops_when_the_refill_rate_is_too_low(self):
        self.assertGreaterEqual(R.MIN_REFILL_RATE, 20.0)

    def test_it_marks_its_own_rows(self):
        self.assertEqual(R.SOURCE_MARKER, 'pricing_repair')

    def test_the_launch_and_stop_commands_are_documented(self):
        """A multi-day script nobody can safely stop is a liability."""
        doc = R.__doc__
        self.assertIn('nohup', doc)
        self.assertIn('pkill -f repair_pricing.py', doc)
        self.assertIn('tail -f', doc)

    def test_it_reminds_the_operator_to_refresh_prime_picks(self):
        """prime_picks caches a SELECTION made on old prices and is not scheduled."""
        source = open(R.__file__, encoding='utf-8').read()
        self.assertIn('/api/prime_picks/refresh', source)

    def test_the_progress_query_is_shipped_with_the_script(self):
        self.assertIn('Pricing_Logic_Version', R.PROGRESS_SQL)
        self.assertIn('GROUP BY', R.PROGRESS_SQL)


if __name__ == '__main__':
    unittest.main()
