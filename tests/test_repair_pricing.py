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


def _row(asin, version=None, list_at=None, yr_avg=None, profit=None, count=None,
         deal_found=None, last_price_change=None):
    row = {'ASIN': asin}
    if deal_found is not None:
        row['Deal_found'] = deal_found
    if last_price_change is not None:
        row['last_price_change'] = last_price_change
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
            return R.repair_batch(targets, 'key', None, _TM(), 10,
                                  apply_changes)

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
        _, outcomes, _ = self._run_batch(apply_changes=False)
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


class DealFeedColumnsAreCarriedForward(_Silent):
    """The two columns the repair structurally cannot compute.

    The ingestor merges the /deal feed object into product_data before the heavy
    path (`smart_ingestor.py:573`). This script has only the /product response, so
    `deal_found` (reads `creationDate`) and `last_price_change` (falls back to
    `deal_object.currentSince`, because its csv branch never fires under a
    single-positional call) both return their `-` sentinel - which the full-column
    upsert would then write over good stored values, blanking the dashboard's
    "Ago" column on every repaired row.

    Pinned here BOTH ways: the two are carried forward, and the pricing columns
    are still overwritten, including to NULL.
    """

    def _apply(self, computed, stored):
        """Run the carry-forward helper with one computed row and one stored row."""
        target = {'ASIN': 'CARRY001'}
        target.update({'stored_{}'.format(k): v for k, v in stored.items()})
        row = dict(computed)
        R.carry_forward_deal_feed_columns(row, target)
        return row

    def test_a_dash_from_the_repair_is_replaced_by_the_stored_value(self):
        row = self._apply({'Deal_found': '-', 'last_price_change': '-'},
                          {'Deal_found': '2026-09-01T10:00:00-04:00',
                           'last_price_change': '2026-09-14 08:00:00'})
        self.assertEqual(row['Deal_found'], '2026-09-01T10:00:00-04:00')
        self.assertEqual(row['last_price_change'], '2026-09-14 08:00:00')

    def test_a_value_the_repair_did_compute_is_kept(self):
        """Carry-forward is a fallback, never an override."""
        row = self._apply({'Deal_found': 'FRESH', 'last_price_change': 'FRESH'},
                          {'Deal_found': 'STALE', 'last_price_change': 'STALE'})
        self.assertEqual(row['Deal_found'], 'FRESH')
        self.assertEqual(row['last_price_change'], 'FRESH')

    def test_nothing_stored_means_nothing_to_carry(self):
        row = self._apply({'Deal_found': '-'}, {'Deal_found': None})
        self.assertEqual(row['Deal_found'], '-')

    def test_the_allowlist_holds_only_non_pricing_columns(self):
        forbidden = {'List_at', '1yr_Avg', 'Deal_Trust', 'Inferred_Sale_Count',
                     PRICING_VERSION_COLUMN, 'Profit', 'Margin', 'Percent_Down',
                     'Total_AMZ_fees', 'All_in_Cost', 'Min_Listing_Price'}
        self.assertEqual(set(R.CARRY_FORWARD_COLUMNS) & forbidden, set(),
                         "Carrying forward a pricing column would make the whole "
                         "script an expensive no-op.")
        self.assertEqual(set(R.CARRY_FORWARD_COLUMNS),
                         {'Deal_found', 'last_price_change'},
                         "The audit found exactly these two. Adding to this list "
                         "needs the audit re-run, not a guess.")

    def test_pricing_columns_are_still_overwritten_even_to_null(self):
        """The carry-forward must not creep into the pricing columns.

        A zero-sale re-fetch produces List_at=None and no 1yr_Avg key at all; both
        must reach the database as NULL even though the stored row has values.
        """
        target = {'ASIN': 'CARRY001',
                  'stored_Deal_found': '2026-09-01T10:00:00-04:00',
                  'stored_last_price_change': '2026-09-14 08:00:00'}
        row = {'ASIN': 'CARRY001', 'List_at': None, 'Deal_Trust': '0%',
               'Inferred_Sale_Count': 0, 'Deal_found': '-',
               'last_price_change': '-'}
        R.carry_forward_deal_feed_columns(row, target)
        self.assertIsNone(row['List_at'])
        self.assertNotIn('1yr_Avg', row)
        self.assertEqual(row['Inferred_Sale_Count'], 0)
        self.assertEqual(row['Deal_found'], '2026-09-01T10:00:00-04:00')

    def test_the_target_query_selects_the_stored_values(self):
        """The helper cannot carry anything the query did not fetch."""
        _build_db(self.db, [_row('CARRY001', list_at='10.0',
                                 deal_found='2026-09-01T10:00:00-04:00',
                                 last_price_change='2026-09-14 08:00:00')])
        target = self._targets()[0]
        self.assertEqual(target['stored_Deal_found'],
                         '2026-09-01T10:00:00-04:00')
        self.assertEqual(target['stored_last_price_change'],
                         '2026-09-14 08:00:00')

    def test_end_to_end_a_repaired_row_keeps_both_and_loses_its_price(self):
        """The whole defect, through the real upsert."""
        from keepa_deals import db_utils
        with open(HEADERS_PATH) as fh:
            headers = json.load(fh)
        _build_db(self.db, [_row('CARRY001', list_at='999.0', yr_avg='999.0',
                                 count=7,
                                 deal_found='2026-09-01T10:00:00-04:00',
                                 last_price_change='2026-09-14 08:00:00')])
        target = self._targets()[0]

        # What the heavy path produces here: no deal feed, and zero sales now.
        row = {'ASIN': 'CARRY001', 'List_at': None, 'Deal_found': '-',
               'last_price_change': '-', 'Inferred_Sale_Count': 0,
               'Deal_Trust': '0%', PRICING_VERSION_COLUMN: PRICING_LOGIC_VERSION}
        R.carry_forward_deal_feed_columns(row, target)

        con = sqlite3.connect(self.db)
        cur = con.cursor()
        db_utils.upsert_deal_rows(cur, [row], headers)
        con.commit()
        got = cur.execute(
            'SELECT "Deal_found", "last_price_change", "List_at", "1yr_Avg", '
            '"Inferred_Sale_Count" FROM deals WHERE "ASIN" = ?',
            ('CARRY001',)).fetchone()
        con.close()

        self.assertEqual(got[0], '2026-09-01T10:00:00-04:00',
                         "Deal_found must survive the repair.")
        self.assertEqual(got[1], '2026-09-14 08:00:00',
                         "The Ago column must survive the repair.")
        self.assertIsNone(got[2], "List_at must still be overwritten to NULL.")
        self.assertIsNone(got[3], "1yr_Avg must still be overwritten to NULL.")
        self.assertEqual(got[4], 0)


class UnrepairableRowsAreAttemptedOncePerRun(_Silent):
    """A row Keepa never returns must not sort back to the top of every batch.

    Without the attempted set an unlimited `--apply` run re-fetches the same
    unrepairable rows forever at ~7 tokens a time, and a dry run with `--limit 20`
    previews the same 5 rows four times.
    """

    def test_an_attempted_asin_is_excluded_from_the_next_batch(self):
        _build_db(self.db, [_row('STUCK001', list_at='900.0'),
                            _row('GOOD0001', list_at='100.0')])
        first = [t['ASIN'] for t in self._targets(limit=1)]
        self.assertEqual(first, ['STUCK001'])

        sql = R.build_target_sql(STALE_PRICING_PREDICATE)
        second = [t['ASIN'] for t in
                  R.fetch_targets(self.db, sql, 1, attempted=set(first))]
        self.assertEqual(second, ['GOOD0001'],
                         "A stuck row must not be re-selected within the run.")

    def test_the_run_ends_when_only_attempted_rows_remain(self):
        _build_db(self.db, [_row('STUCK001', list_at='900.0'),
                            _row('STUCK002', list_at='800.0')])
        sql = R.build_target_sql(STALE_PRICING_PREDICATE)
        rest = R.fetch_targets(self.db, sql, 50,
                               attempted={'STUCK001', 'STUCK002'})
        self.assertEqual(rest, [],
                         "With every stale row attempted, the loop must end "
                         "rather than spin.")

    def test_a_dry_run_previews_distinct_rows_across_batches(self):
        """`--limit 2*batch` must preview 2*batch DISTINCT rows, not one batch twice."""
        batch = 5
        _build_db(self.db, [_row('ASIN%05d' % i, list_at=str(1000 - i))
                            for i in range(batch * 2)])
        sql = R.build_target_sql(STALE_PRICING_PREDICATE)
        attempted, seen = set(), []
        for _ in range(2):
            got = R.fetch_targets(self.db, sql, batch, attempted)
            seen.extend(t['ASIN'] for t in got)
            attempted.update(t['ASIN'] for t in got)
        self.assertEqual(len(seen), batch * 2)
        self.assertEqual(len(set(seen)), batch * 2,
                         "A dry run must not re-preview the same rows: {}"
                         .format(seen))

    def test_the_exclusion_scales_past_the_bound_parameter_ceiling(self):
        """The attempted set can reach every row in the table if Keepa is down.

        A `NOT IN (?,?,...)` list would hit SQLITE_MAX_VARIABLE_NUMBER; the temp
        table does not.
        """
        _build_db(self.db, [_row('ASIN%05d' % i, list_at='10.0')
                            for i in range(50)])
        sql = R.build_target_sql(STALE_PRICING_PREDICATE)
        attempted = {'ASIN%05d' % i for i in range(49)}
        got = R.fetch_targets(self.db, sql, 50, attempted)
        self.assertEqual([t['ASIN'] for t in got], ['ASIN00049'])

    def test_skipped_asins_are_written_to_their_own_manifest(self):
        path = R.write_skip_manifest(
            self.tmp, '20260917000000', 'apply',
            [('STUCK001', 'not returned by Keepa'),
             ('STUCK002', 'heavy processing returned nothing')])
        body = open(path).read()
        self.assertIn('STUCK001\tnot returned by Keepa', body)
        self.assertIn('STUCK002\t', body)
        self.assertIn('skipped', os.path.basename(path))

    def test_no_skip_manifest_is_written_when_nothing_was_skipped(self):
        self.assertIsNone(R.write_skip_manifest(self.tmp, '1', 'apply', []))

    def test_repair_batch_itself_applies_the_carry_forward(self):
        """Wiring check: the helper is called from repair_batch, not just testable.

        The other carry-forward tests drive the helper directly. This one proves
        `repair_batch` invokes it, which is what the production path depends on.
        """
        _build_db(self.db, [_row('CARRY001', list_at='999.0',
                                 deal_found='2026-09-01T10:00:00-04:00',
                                 last_price_change='2026-09-14 08:00:00')])
        targets = self._targets()

        class _TM:
            REFILL_RATE_PER_MINUTE = 25.0

            def request_permission_for_call(self, cost):
                pass

            def update_after_call(self, left):
                pass

        # The heavy path's real output when the deal feed is missing.
        heavy_row = {'ASIN': 'CARRY001', 'List_at': 42.0, 'Deal_found': '-',
                     'last_price_change': '-', 'Inferred_Sale_Count': 3}

        with patch('keepa_deals.keepa_api.fetch_product_batch') as fetch, \
             patch('keepa_deals.processing._process_single_deal') as heavy, \
             patch('keepa_deals.processing.clean_numeric_values',
                   side_effect=lambda r: r), \
             patch('keepa_deals.db_utils.to_db_keys', side_effect=lambda r: r), \
             patch('keepa_deals.seller_info.get_seller_info_for_single_deal',
                   return_value={}), \
             patch('keepa_deals.db_utils.DB_PATH', self.db):
            fetch.return_value = ({'products': [{'asin': 'CARRY001'}]}, {}, 0, 100)
            heavy.return_value = dict(heavy_row)
            rows, _, skipped = R.repair_batch(targets, 'key', None, _TM(), 10,
                                             False)

        self.assertEqual(skipped, [])
        self.assertEqual(rows[0]['Deal_found'], '2026-09-01T10:00:00-04:00',
                         "repair_batch must apply the carry-forward.")
        self.assertEqual(rows[0]['last_price_change'], '2026-09-14 08:00:00')
        self.assertEqual(rows[0]['List_at'], 42.0,
                         "The recomputed price must survive untouched.")

    def test_a_row_keepa_does_not_return_is_reported_as_skipped(self):
        _build_db(self.db, [_row('MISSING1', list_at='900.0')])
        targets = self._targets()

        class _TM:
            REFILL_RATE_PER_MINUTE = 25.0

            def request_permission_for_call(self, cost):
                pass

            def update_after_call(self, left):
                pass

        with patch('keepa_deals.keepa_api.fetch_product_batch') as fetch, \
             patch('keepa_deals.db_utils.DB_PATH', self.db):
            fetch.return_value = ({'products': []}, {}, 0, 100)
            rows, outcomes, skipped = R.repair_batch(targets, 'key', None, _TM(),
                                                    10, False)

        self.assertEqual(rows, [])
        self.assertEqual(outcomes, [])
        self.assertEqual([a for a, _ in skipped], ['MISSING1'])
        self.assertIn('not returned by Keepa', skipped[0][1])


class AnUnboundedDryRunIsRefused(unittest.TestCase):
    """A dry run with no --limit is the one invocation with no upside.

    It heavy-fetches every stale row - ~32,000 Keepa tokens at the 2026-09-16
    sizing - and writes nothing. Maximum spend, zero effect.

    It used to be survivable by accident: the dry run stopped after one batch.
    That workaround existed only to paper over the stuck-row loop, and once the
    attempted set fixed that properly the dry run began walking the whole table.
    So the guard has to be explicit, and it has to fire BEFORE preflight - before
    anything is read, and before a single token can be spent.

    `--apply` without --limit is the INTENDED full sweep and stays allowed.
    """

    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def _main(self, argv):
        """Run main() with preflight stubbed, so only the guard can stop it.

        Preflight always fails in the sandbox (not www-data), which would mask the
        difference between "refused by the guard" and "refused by preflight".
        Stubbing it means `pf.called` cleanly separates the two.
        """
        with patch.object(R, 'preflight') as pf, \
             patch.object(R, 'load_dotenv'), \
             patch.dict(os.environ, {'XAI_TOKEN': 'x'}):
            pf.side_effect = R.RepairAbort('preflight stub')
            return R.main(argv + ['--log-file', os.path.join(self.tmp, 'r.log')]), pf

    def test_a_dry_run_without_limit_exits_one_before_preflight(self):
        code, pf = self._main([])
        self.assertEqual(code, 1)
        pf.assert_not_called()

    def test_the_message_tells_the_operator_what_to_do(self):
        logging.disable(logging.NOTSET)
        with self.assertLogs('repair_pricing', level='ERROR') as caught:
            self._main([])
        body = '\n'.join(caught.output)
        self.assertIn('REFUSED', body)
        self.assertIn('--limit', body)
        self.assertIn('--apply', body)

    def test_a_dry_run_with_limit_is_allowed_through_to_preflight(self):
        _, pf = self._main(['--limit', '10'])
        pf.assert_called_once()

    def test_apply_without_limit_is_allowed_through_to_preflight(self):
        """The full sweep is the intended invocation and must not be blocked."""
        _, pf = self._main(['--apply'])
        pf.assert_called_once()

    def test_the_estimate_does_not_touch_the_database(self):
        """The refusal fires before preflight has validated the database."""
        self.assertIsInstance(R._estimated_full_sweep_tokens(), int)
        self.assertGreater(R._estimated_full_sweep_tokens(), 1000)


class TheSweepStopsBeforeTheXaiCapIsHit(_Silent):
    """The 2026-09-17 blocker: past the cap, the price check used to silently pass.

    `_query_xai_for_reasonableness` returned True when the daily cap denied
    permission, so a price was accepted unchecked AND stamped current, and the
    sweep never revisited it. Since Pricing Logic Version 3 (Trello #144) it fails
    CLOSED - see tests/test_xai_fail_closed.py - which ends the laundering but not
    the case for stopping: past the cap every row would be written unpriced and
    hidden, its Keepa tokens spent for nothing until a later run retries it.

    Measured on the 10-row dry run: ~15 xAI calls for 9 rows, most FORCED by the
    3x-of-current-used rule, which fires on precisely the rows being repaired.
    """

    def _with_counter(self, calls_today, limit=1000, reset_today=True):
        """Patch the in-process manager AND its on-disk state to a known count."""
        from keepa_deals import stable_calculations as sc
        state_path = os.path.join(self.tmp, 'xai_token_state.json')
        with open(state_path, 'w') as fh:
            json.dump({'last_reset_date': (str(R.date.today()) if reset_today
                                           else '1970-01-01'),
                       'calls_today': calls_today}, fh)
        manager = sc.xai_token_manager
        return patch.multiple(manager, daily_limit=limit, state_path=state_path,
                              state={'last_reset_date': str(R.date.today()),
                                     'calls_today': calls_today})

    def test_remaining_is_reported_against_the_real_limit(self):
        with self._with_counter(900):
            spare, used, limit = R.xai_calls_remaining()
        self.assertEqual((spare, used, limit), (100, 900, 1000))

    def test_the_on_disk_count_is_used_when_it_is_higher(self):
        """Ingestion burns calls this process cannot see in its own counter.

        Under-reporting would make the guard fire LATE, which is the dangerous
        direction, so the on-disk value is a floor.
        """
        from keepa_deals import stable_calculations as sc
        state_path = os.path.join(self.tmp, 'xai_token_state.json')
        with open(state_path, 'w') as fh:
            json.dump({'last_reset_date': str(R.date.today()),
                       'calls_today': 980}, fh)
        with patch.multiple(sc.xai_token_manager, daily_limit=1000,
                            state_path=state_path,
                            state={'last_reset_date': str(R.date.today()),
                                   'calls_today': 10}):
            spare, used, _ = R.xai_calls_remaining()
        self.assertEqual(used, 980, "The higher of the two counts must win.")
        self.assertEqual(spare, 20)

    def test_a_stale_on_disk_count_from_a_previous_day_is_ignored(self):
        """The counter resets on the local date change; yesterday's total is not ours."""
        from keepa_deals import stable_calculations as sc
        state_path = os.path.join(self.tmp, 'xai_token_state.json')
        with open(state_path, 'w') as fh:
            json.dump({'last_reset_date': '1970-01-01', 'calls_today': 999}, fh)
        with patch.multiple(sc.xai_token_manager, daily_limit=1000,
                            state_path=state_path,
                            state={'last_reset_date': str(R.date.today()),
                                   'calls_today': 4}):
            spare, used, _ = R.xai_calls_remaining()
        self.assertEqual(used, 4)
        self.assertEqual(spare, 996)

    def test_a_missing_state_file_is_not_fatal(self):
        from keepa_deals import stable_calculations as sc
        with patch.multiple(sc.xai_token_manager, daily_limit=1000,
                            state_path=os.path.join(self.tmp, 'nope.json'),
                            state={'last_reset_date': str(R.date.today()),
                                   'calls_today': 7}):
            spare, used, _ = R.xai_calls_remaining()
        self.assertEqual((spare, used), (993, 7))

    def _run_main(self, argv, spare):
        """Drive main() to the loop with everything but the headroom check stubbed."""
        with patch.object(R, 'preflight'), \
             patch.object(R, 'load_dotenv'), \
             patch.object(R, 'backup_database'), \
             patch.object(R, '_scalar', return_value=100), \
             patch.object(R, 'xai_calls_remaining',
                          return_value=(spare, 1000 - spare, 1000)), \
             patch.object(R, 'fetch_targets') as targets, \
             patch.object(R, 'repair_batch') as batch, \
             patch('keepa_deals.token_manager.TokenManager') as tm, \
             patch.dict(os.environ, {'KEEPA_API_KEY': 'k', 'XAI_TOKEN': 'x'}):
            tm.return_value.REFILL_RATE_PER_MINUTE = 25.0
            tm.return_value.tokens = 300.0
            tm.return_value.should_skip_sync.return_value = True
            # One batch, then empty. `fetch_targets` is patched, so it cannot
            # honour the attempted set - without a terminating side_effect the
            # --apply loop, which has no --limit, would spin forever.
            targets.side_effect = [
                [{'ASIN': 'AAAAAAAA', 'tier': 0, 'old_list_at': 900.0,
                  'old_1yr_avg': '900', 'old_count': None, 'old_trust': '50%'}],
                [],
            ]
            batch.return_value = ([], [], [])
            code = R.main(argv + ['--log-file',
                                  os.path.join(self.tmp, 'r.log')])
        return code, targets, batch

    def test_no_batch_runs_when_headroom_is_insufficient(self):
        """The whole point: nothing is fetched and nothing is written."""
        code, targets, batch = self._run_main(['--apply'], spare=10)
        batch.assert_not_called()
        targets.assert_not_called()
        self.assertEqual(code, 0,
                         "A headroom stop is a clean, resumable pause, not a "
                         "failure - exit 0 so a wrapper does not treat it as one.")

    def test_a_batch_runs_when_headroom_is_sufficient(self):
        _, targets, batch = self._run_main(['--apply'], spare=500)
        batch.assert_called()
        targets.assert_called()

    def test_the_headroom_is_configurable(self):
        _, _, batch = self._run_main(['--apply', '--xai-headroom', '5'], spare=10)
        batch.assert_called()

    def test_the_stop_message_names_the_reset_and_the_reason(self):
        logging.disable(logging.NOTSET)
        with self.assertLogs('repair_pricing', level='WARNING') as caught:
            self._run_main(['--apply'], spare=10)
        body = '\n'.join(caught.output)
        self.assertIn('xAI daily limit nearly reached', body)
        self.assertIn('Re-run the same command after the daily reset', body)
        self.assertIn('fails closed', body,
                      "The operator needs to know WHY continuing is worse than "
                      "stopping, not just that it stopped.")
        self.assertIn('UNPRICED', body)

    def test_the_default_headroom_covers_a_batch_plus_ingestion(self):
        self.assertGreaterEqual(
            R.DEFAULT_XAI_HEADROOM,
            R.DEFAULT_BATCH_SIZE * R.XAI_CALLS_PER_ROW,
            "Headroom below one batch's worth of calls would let the batch in "
            "flight cross the cap.")


class ARechargeIsWaitedOutNotStopped(_Silent):
    """The 2026-09-17 stop: a 130-second token dip ended a multi-day sweep.

        ERROR Batch failed (Recharge needed: 130s). Stopping; nothing in this
        batch was written.

    That is a `TokenRechargeError` out of `token_manager.py`, which raises rather
    than sleeping whenever the calculated wait exceeds 60s. Correct for the Smart
    Ingestor - it runs every 5 minutes under a lock, so exiting frees the worker -
    and wrong for this script, which holds no lock, has nothing else to do, and has
    no scheduler to bring it back. xAI was nowhere near its cap (79 of 5000 calls
    used), so nothing but the dip ended the run.

    Keepa refills at 25/min into a bucket SHARED with ingestion, so these dips
    recur every run. The sweep now waits them out. Every other exception still
    stops it, and every pre-existing stop condition still applies between retries.
    """

    def setUp(self):
        super().setUp()
        self.fetch_calls = []
        self.slept = []

    # -- the wait itself ---------------------------------------------------

    def test_the_wait_comes_from_the_exception_the_manager_raises(self):
        """Both raise sites embed the figure in the message, not on the exception."""
        from keepa_deals.token_manager import TokenRechargeError
        self.assertEqual(
            R.recharge_wait_seconds(TokenRechargeError('Recharge needed: 130s')),
            130 + R.RECHARGE_WAIT_MARGIN_SECONDS)
        self.assertEqual(
            R.recharge_wait_seconds(
                TokenRechargeError('Insufficient tokens: wait 130s')),
            130 + R.RECHARGE_WAIT_MARGIN_SECONDS)

    def test_a_margin_is_added_so_the_retry_does_not_arrive_empty(self):
        """The manager's wait reaches BURST_THRESHOLD exactly - no slack."""
        self.assertGreater(R.RECHARGE_WAIT_MARGIN_SECONDS, 0)
        self.assertGreater(R.recharge_wait_seconds(Exception('wait 10s')), 10)

    def test_an_unparsable_message_still_waits_instead_of_stopping(self):
        """The wording belongs to token_manager.py; a reword must not stop the sweep."""
        self.assertEqual(
            R.recharge_wait_seconds(Exception('tokens are low, come back later')),
            R.DEFAULT_RECHARGE_WAIT_SECONDS + R.RECHARGE_WAIT_MARGIN_SECONDS)

    def test_a_nonsense_figure_is_clamped(self):
        self.assertEqual(R.recharge_wait_seconds(Exception('wait 999999s')),
                         R.MAX_RECHARGE_WAIT_SECONDS)

    def test_the_wait_is_sliced_so_sigterm_is_still_noticed(self):
        """`pkill -f repair_pricing.py` is the documented clean stop."""
        calls = []
        done = R.sleep_through_recharge(12, stop=None, sleep=calls.append)
        self.assertTrue(done)
        self.assertEqual(sum(calls), 12)
        self.assertTrue(all(c <= R.RECHARGE_POLL_SECONDS for c in calls))

    def test_a_stop_during_the_wait_cuts_it_short(self):
        class _Stop:
            requested = False
        stop = _Stop()
        calls = []

        def _sleep(seconds):
            calls.append(seconds)
            stop.requested = True

        self.assertFalse(R.sleep_through_recharge(600, stop=stop, sleep=_sleep))
        self.assertEqual(len(calls), 1, "It must not sleep out the full wait.")

    # -- the retry ---------------------------------------------------------

    def _fetch_targets_honouring_attempted(self, batches):
        """A `fetch_targets` stub that excludes attempted ASINs, as the real one does.

        This is what makes the retry assertions mean something. The real selection
        excludes `attempted_this_run` in SQL, and a batch's ASINs are added to that
        set BEFORE the fetch - so a retry routed back through selection would find
        nothing and the batch would silently vanish.
        """
        queue = [list(b) for b in batches]

        def _fetch(db_path, sql, limit, attempted=()):
            self.fetch_calls.append(set(attempted))
            while queue:
                batch = [t for t in queue.pop(0) if t['ASIN'] not in attempted]
                if batch:
                    return batch
            return []

        return _fetch

    @staticmethod
    def _target(asin):
        return {'ASIN': asin, 'tier': 0, 'old_list_at': 900.0,
                'old_1yr_avg': '900', 'old_count': None, 'old_trust': '50%'}

    def _run(self, argv, batch_side_effect, batches=(('AAAAAAAA',),),
             spare=500, refill=25.0):
        """Drive main() to the batch loop with only the recharge path live."""
        targets = [[self._target(a) for a in b] for b in batches]
        with patch.object(R, 'preflight'), \
             patch.object(R, 'load_dotenv'), \
             patch.object(R, 'backup_database'), \
             patch.object(R, '_scalar', return_value=100), \
             patch.object(R, 'xai_calls_remaining',
                          side_effect=(spare if callable(spare)
                                       else lambda: (spare, 1000 - spare, 1000))), \
             patch.object(R, 'sleep_through_recharge',
                          side_effect=lambda s, stop=None: (self.slept.append(s)
                                                            or True)), \
             patch.object(R, 'fetch_targets',
                          side_effect=self._fetch_targets_honouring_attempted(
                              targets)), \
             patch.object(R, 'repair_batch') as batch, \
             patch('keepa_deals.token_manager.TokenManager') as tm, \
             patch.dict(os.environ, {'KEEPA_API_KEY': 'k', 'XAI_TOKEN': 'x'}):
            tm.return_value.REFILL_RATE_PER_MINUTE = refill
            tm.return_value.tokens = 300.0
            tm.return_value.should_skip_sync.return_value = True
            batch.side_effect = batch_side_effect
            code = R.main(argv + ['--log-file', os.path.join(self.tmp, 'r.log')])
        return code, batch

    def test_a_recharge_is_waited_out_and_the_batch_retried(self):
        from keepa_deals.token_manager import TokenRechargeError
        code, batch = self._run(
            ['--apply'],
            [TokenRechargeError('Recharge needed: 130s'), ([], [], [])])
        self.assertEqual(code, 0)
        self.assertEqual(batch.call_count, 2,
                         "The batch must be retried, not abandoned.")
        self.assertEqual(self.slept, [130 + R.RECHARGE_WAIT_MARGIN_SECONDS])

    def test_the_retry_gets_the_same_asins(self):
        from keepa_deals.token_manager import TokenRechargeError
        _, batch = self._run(
            ['--apply'],
            [TokenRechargeError('Recharge needed: 130s'), ([], [], [])],
            batches=(('AAAAAAAA', 'BBBBBBBB'),))
        first, second = [c.args[0] for c in batch.call_args_list]
        self.assertEqual([t['ASIN'] for t in first], ['AAAAAAAA', 'BBBBBBBB'])
        self.assertEqual([t['ASIN'] for t in second], ['AAAAAAAA', 'BBBBBBBB'])

    def test_the_retry_is_not_re_selected_past_the_attempted_set(self):
        """Requirement 3. The rows are already in `attempted` when the retry runs.

        `attempted` is updated BEFORE the fetch, so re-selecting after a recharge
        would exclude the exact rows being retried and the batch would disappear
        without a trace. The retry therefore uses the target list already in hand.
        """
        from keepa_deals.token_manager import TokenRechargeError
        _, batch = self._run(
            ['--apply'],
            [TokenRechargeError('Recharge needed: 130s'), ([], [], [])])
        self.assertEqual(batch.call_count, 2)
        # Selection ran once for the batch and once afterwards (finding nothing
        # left) - NOT a third time for the retry.
        self.assertEqual(len(self.fetch_calls), 2)
        self.assertIn('AAAAAAAA', self.fetch_calls[1],
                      "The retried ASIN is in the attempted set by then, which is "
                      "exactly why the retry must not go back through selection.")

    def test_each_wait_is_logged(self):
        from keepa_deals.token_manager import TokenRechargeError
        logging.disable(logging.NOTSET)
        with self.assertLogs('repair_pricing', level='WARNING') as caught:
            self._run(['--apply'],
                      [TokenRechargeError('Recharge needed: 130s'),
                       ([], [], [])])
        body = '\n'.join(caught.output)
        self.assertIn('Recharge needed: 130s', body)
        self.assertIn('Waiting 145s', body)
        self.assertIn('retrying the same batch', body)

    def test_the_counter_resets_after_a_batch_gets_through(self):
        """It bounds a STALL, not a long run. A dip an hour must never accumulate."""
        from keepa_deals.token_manager import TokenRechargeError
        recharge = TokenRechargeError('Recharge needed: 130s')
        code, batch = self._run(
            ['--apply', '--max-recharge-retries', '1'],
            [recharge, ([], [], []), recharge, ([], [], [])],
            batches=(('AAAAAAAA',), ('BBBBBBBB',)))
        self.assertEqual(code, 0)
        self.assertEqual(batch.call_count, 4,
                         "Two batches, each waiting out one recharge, must both "
                         "complete under a cap of 1.")

    # -- the cap -----------------------------------------------------------

    def test_consecutive_retries_are_capped(self):
        from keepa_deals.token_manager import TokenRechargeError
        recharge = TokenRechargeError('Recharge needed: 130s')
        code, batch = self._run(['--apply', '--max-recharge-retries', '3'],
                                [recharge] * 20)
        self.assertEqual(batch.call_count, 4, "One attempt plus three retries.")
        self.assertEqual(len(self.slept), 3)
        self.assertEqual(code, 0,
                         "Hitting the cap is a clean, resumable pause - exit 0, "
                         "like the xAI headroom stop, so a wrapper does not treat "
                         "it as a failure.")

    def test_the_cap_stop_says_it_is_resumable(self):
        from keepa_deals.token_manager import TokenRechargeError
        logging.disable(logging.NOTSET)
        with self.assertLogs('repair_pricing', level='WARNING') as caught:
            self._run(['--apply', '--max-recharge-retries', '1'],
                      [TokenRechargeError('Recharge needed: 130s')] * 5)
        body = '\n'.join(caught.output)
        self.assertIn('STOPPING', body)
        self.assertIn('consecutive Keepa recharge waits', body)
        self.assertIn('re-run the same command', body.lower())

    def test_the_default_cap_is_a_stall_not_a_hair_trigger(self):
        self.assertGreaterEqual(R.DEFAULT_MAX_RECHARGE_RETRIES, 3)

    # -- everything else still stops ---------------------------------------

    def test_any_other_exception_still_stops_the_run(self):
        code, batch = self._run(['--apply'],
                                [RuntimeError('Keepa returned 500'),
                                 ([], [], [])])
        self.assertEqual(batch.call_count, 1,
                         "Only a TokenRechargeError is retried.")
        self.assertEqual(self.slept, [])
        self.assertEqual(code, 0)

    def test_the_xai_headroom_stop_still_applies_between_retries(self):
        """Requirement 4. The wait returns to the TOP of the loop, not past it."""
        from keepa_deals.token_manager import TokenRechargeError
        spares = iter([(500, 500, 1000), (10, 990, 1000), (10, 990, 1000)])
        code, batch = self._run(
            ['--apply'],
            [TokenRechargeError('Recharge needed: 130s'), ([], [], [])],
            spare=lambda: next(spares))
        self.assertEqual(batch.call_count, 1,
                         "The retry must not run once xAI headroom is gone.")
        self.assertEqual(code, 0)

    def test_the_refill_floor_still_applies_between_retries(self):
        """The 20/min floor is re-checked before the retry, like every other batch."""
        from keepa_deals.token_manager import TokenRechargeError
        recharge = TokenRechargeError('Recharge needed: 130s')
        code, batch = self._run(['--apply'], [recharge] * 5, refill=5.0)
        self.assertEqual(batch.call_count, 0,
                         "Below the floor nothing runs at all - unchanged.")
        self.assertEqual(code, 0)

    # -- a recharge mid-batch is not a skipped row -------------------------

    def test_a_recharge_inside_the_batch_is_not_recorded_as_unrepairable(self):
        """`get_seller_info_for_single_deal` reserves tokens of its own (:45).

        Swallowed by the per-row handler, a recharge there would mark a perfectly
        repairable row as failed AND keep it out of every later batch this run.
        Once recharges are waited out rather than ending the run, that would happen
        on every dip instead of once, so it must reach the batch retry instead.
        """
        from keepa_deals.token_manager import TokenRechargeError

        class _TM:
            REFILL_RATE_PER_MINUTE = 25.0

            def request_permission_for_call(self, cost):
                pass

            def update_after_call(self, left):
                pass

        with patch('keepa_deals.keepa_api.fetch_product_batch',
                   return_value=({'products': [{'asin': 'AAAAAAAA'}]},
                                 None, None, 100.0)), \
             patch('keepa_deals.seller_info.get_seller_info_for_single_deal',
                   side_effect=TokenRechargeError('Recharge needed: 130s')):
            with self.assertRaises(TokenRechargeError):
                R.repair_batch([self._target('AAAAAAAA')], 'k', 'x', _TM(),
                               10, False)


class ItRefusesToRunWithoutAnXaiKey(unittest.TestCase):
    """Owner decision 2026-09-22 (Pricing Logic Version 3).

    Without XAI_TOKEN the AI Reasonableness Check fails closed, so a sweep would
    write every checked row UNPRICED and hidden - including rows visible today -
    for ~7 Keepa tokens each. It must refuse before reading or fetching anything.
    """

    def setUp(self):
        logging.disable(logging.CRITICAL)
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        logging.disable(logging.NOTSET)

    def _main(self, argv, env):
        with patch.object(R, 'preflight') as pf, \
             patch.object(R, 'load_dotenv'), \
             patch.object(R, 'backup_database') as backup, \
             patch('keepa_deals.token_manager.TokenManager') as tm, \
             patch.dict(os.environ, env):
            if 'XAI_TOKEN' not in env:
                os.environ.pop('XAI_TOKEN', None)
            code = R.main(argv + ['--log-file', os.path.join(self.tmp, 'r.log')])
        return code, pf, backup, tm

    def test_no_key_exits_non_zero_before_anything_is_touched(self):
        for argv in (['--apply'], ['--limit', '10']):
            code, pf, backup, tm = self._main(argv, {'KEEPA_API_KEY': 'k'})
            self.assertNotEqual(code, 0, argv)
            pf.assert_not_called()
            backup.assert_not_called()
            tm.assert_not_called()

    def test_an_empty_key_is_no_key(self):
        code, pf, _, _ = self._main(['--apply'], {'KEEPA_API_KEY': 'k', 'XAI_TOKEN': ''})
        self.assertNotEqual(code, 0)
        pf.assert_not_called()

    def test_the_message_says_why_and_what_to_do(self):
        logging.disable(logging.NOTSET)
        with self.assertLogs('repair_pricing', level='ERROR') as caught:
            self._main(['--apply'], {'KEEPA_API_KEY': 'k'})
        body = '\n'.join(caught.output)
        self.assertIn('REFUSED', body)
        self.assertIn('XAI_TOKEN', body)
        self.assertIn('UNPRICED', body)

    def test_with_a_key_it_proceeds_to_preflight(self):
        with patch.object(R, 'preflight') as pf, \
             patch.object(R, 'load_dotenv'), \
             patch.dict(os.environ, {'KEEPA_API_KEY': 'k', 'XAI_TOKEN': 'x'}):
            pf.side_effect = R.RepairAbort('preflight stub')
            R.main(['--apply', '--log-file', os.path.join(self.tmp, 'r.log')])
        pf.assert_called_once()


class TheWithheldReasonIsLogged(unittest.TestCase):
    """Pricing Logic Version 4: every withheld price says why, in the sweep's log.

    Nothing else records it: the reason is not a column (owner decision), and a
    thin season and an AI "No" otherwise leave identical rows.
    """

    def setUp(self):
        from keepa_deals import stable_calculations
        self.sc = stable_calculations
        self.sc.clear_analysis_cache()

    def tearDown(self):
        self.sc.clear_analysis_cache()

    def test_the_reason_is_read_from_the_memoised_analysis(self):
        self.sc._analysis_cache['WHY0000001'] = {'withheld_reason': 'ai_rejected'}
        self.assertEqual(R.withheld_reason('WHY0000001'), 'ai_rejected')

    def test_it_never_recomputes_an_analysis(self):
        with patch.object(self.sc, '_get_analysis') as get:
            self.assertIsNone(R.withheld_reason('NOTCACHED1'))
        get.assert_not_called()

    def test_the_log_line_names_the_reason(self):
        outcome = {'ASIN': 'WHY0000002', 'tier': 0, 'old_list_at': 300.0,
                   'new_list_at': None, 'old_1yr_avg': '100', 'new_1yr_avg': '100',
                   'old_count': 5, 'new_count': 5, 'old_trust': '50%',
                   'new_trust': '50%', 'withheld': 'thin'}
        with self.assertLogs('repair_pricing', level='INFO') as caught:
            R.print_outcomes([outcome], True)
        self.assertIn('withheld: thin', caught.output[0])

    def test_a_priced_row_says_nothing_extra(self):
        outcome = {'ASIN': 'WHY0000003', 'tier': 0, 'old_list_at': 300.0,
                   'new_list_at': 250.0, 'old_1yr_avg': '100', 'new_1yr_avg': '100',
                   'old_count': 5, 'new_count': 5, 'old_trust': '50%',
                   'new_trust': '50%', 'withheld': None}
        with self.assertLogs('repair_pricing', level='INFO') as caught:
            R.print_outcomes([outcome], True)
        self.assertNotIn('withheld', caught.output[0])
