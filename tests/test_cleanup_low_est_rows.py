"""Tests for cleanup_low_est_rows.py and for the Inferred_Sale_Count column.

Every test builds its schema from `headers.json` through the production
`sanitize_col_name` / `create_deals_table_if_not_exists` / `upsert_deal_rows`, in a
temp database. None of them can be satisfied by a fixture that encodes the wrong
convention, which is the property that made
`tests/test_lightweight_upsert_preservation.py` worth having.

`deals.db` is never touched: DB_PATH is monkeypatched to a tempfile for the duration
of each test.
"""

import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime as real_datetime
from unittest.mock import patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.append(os.path.dirname(os.path.abspath(__file__)))



from _real_module import load as _load_real  # noqa: E402

# The real db_utils, not the MagicMock that tests/test_approve_dedup.py leaves in
# sys.modules for the whole pytest session. See tests/_real_module.py.
db_utils = _load_real('keepa_deals.db_utils')

from cleanup_low_est_rows import (  # noqa: E402
    CLEANUP_PREDICATE,
    INVARIANT_SQL,
    LOW_EST_MARKER,
    VISIBLE_SQL,
    CleanupAbort,
    check_invariant,
    count_visible,
    run_cleanup,
    select_target_asins,
)

HEADERS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'keepa_deals', 'headers.json')


def _load_headers():
    with open(HEADERS_PATH) as fh:
        return json.load(fh)


def _build_table(db_path, headers=None, omit=()):
    """Create the deals table the way recreate_deals_table() does.

    `omit` drops columns, so a test can simulate a live table that predates a
    headers.json addition.
    """
    headers = headers or _load_headers()
    explicit_real = ["Price", "Cost", "Fee", "Fees", "Profit", "Margin", "List at",
                     "Total AMZ fees", "Total_AMZ_fees"]
    cols = []
    for header in headers:
        if header in omit:
            continue
        col = db_utils.sanitize_col_name(header)
        if any(k.lower() in header.lower() for k in explicit_real):
            col_type = 'REAL'
        elif "Rank" in header or "Count" in header or "Drops" in header:
            col_type = 'INTEGER'
        else:
            col_type = 'TEXT'
        cols.append('"{}" TEXT NOT NULL UNIQUE'.format(col) if col == 'ASIN'
                    else '"{}" {}'.format(col, col_type))
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE deals (id INTEGER PRIMARY KEY AUTOINCREMENT, {})"
                 .format(', '.join(cols)))
    conn.execute("CREATE UNIQUE INDEX idx_asin_unique ON deals(ASIN)")
    conn.commit()
    conn.close()


def _insert(db_path, asin, deal_trust=None, yr_avg=None, list_at=None,
            source='smart_ingestor'):
    conn = sqlite3.connect(db_path)
    conn.execute(
        'INSERT INTO deals (ASIN, "Deal_Trust", "1yr_Avg", "List_at", source) '
        'VALUES (?, ?, ?, ?, ?)', (asin, deal_trust, yr_avg, list_at, source))
    conn.commit()
    conn.close()


class TempDealsDb(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.tmpdir, 'test_deals.db')
        self.backup_dir = os.path.join(self.tmpdir, 'db_backups')
        self._orig_db_path = db_utils.DB_PATH

    def tearDown(self):
        db_utils.DB_PATH = self._orig_db_path
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _conn(self):
        return sqlite3.connect(self.db_path)


class CleanupPredicate(TempDealsDb):
    """The predicate must hit the fallback rows and nothing else."""

    def setUp(self):
        super().setUp()
        _build_table(self.db_path)
        # Targets: the fallback marker, both invisible and visible.
        _insert(self.db_path, 'LOWEST0001', deal_trust=LOW_EST_MARKER, yr_avg='88.0')
        _insert(self.db_path, 'LOWEST0002', deal_trust=LOW_EST_MARKER, yr_avg='88.0',
                list_at=12.0)
        # Must survive: a normal numeric trust.
        _insert(self.db_path, 'NORMAL0001', deal_trust='33', yr_avg='20.0',
                list_at=40.0)
        # Must survive: the OTHER non-numeric trust state. deal_trust() returns '-'
        # when total_offer_drops == 0, the XAI "no offer drops" rescue. Those are
        # real inferred-sale rows and are not what this cleanup is for.
        _insert(self.db_path, 'DASHONLY01', deal_trust='-', yr_avg='20.0',
                list_at=40.0)
        # Must survive: no trust recorded at all.
        _insert(self.db_path, 'NULLTRST01', deal_trust=None, yr_avg='20.0',
                list_at=40.0)

    def test_predicate_selects_only_the_marked_rows(self):
        with self._conn() as conn:
            self.assertEqual(select_target_asins(conn), ['LOWEST0001', 'LOWEST0002'])

    def test_predicate_spares_the_dash_trust_state(self):
        """The regression that would matter most: deleting the XAI-rescue rows."""
        with self._conn() as conn:
            targets = select_target_asins(conn)
        self.assertNotIn('DASHONLY01', targets,
                         "Deal Trust '-' is the XAI no-offer-drops rescue, not the "
                         "listing-average fallback. It must never be deleted here.")

    def test_predicate_and_queries_are_the_documented_ones(self):
        """Pins the SQL strings so a silent widening shows up as a test change."""
        self.assertEqual(CLEANUP_PREDICATE, '"Deal_Trust" = \'Low (Est.)\'')
        self.assertIn('"Deal_Trust" = \'Low (Est.)\'', INVARIANT_SQL)
        self.assertIn('"1yr_Avg" IS NULL', INVARIANT_SQL)
        self.assertIn('"List_at" IS NOT NULL', VISIBLE_SQL)

    def test_predicate_is_an_exact_string_match(self):
        """Guards against a LIKE or a prefix match creeping in."""
        _insert(self.db_path, 'LOOKALIKE1', deal_trust='Low (Est.) 2', yr_avg='1.0')
        _insert(self.db_path, 'LOOKALIKE2', deal_trust='low (est.)', yr_avg='1.0')
        with self._conn() as conn:
            targets = select_target_asins(conn)
        self.assertEqual(targets, ['LOWEST0001', 'LOWEST0002'])

    def test_visible_count_is_reported_not_enforced(self):
        with self._conn() as conn:
            self.assertEqual(count_visible(conn), 1)


class CleanupInvariant(TempDealsDb):
    """The invariant must hold after the fallback removal, unlike the old one."""

    def setUp(self):
        super().setUp()
        _build_table(self.db_path)

    def test_invariant_passes_on_a_healthy_database(self):
        _insert(self.db_path, 'LOWEST0001', deal_trust=LOW_EST_MARKER, yr_avg='88.0')
        _insert(self.db_path, 'NORMAL0001', deal_trust='33', yr_avg='20.0',
                list_at=40.0)
        with self._conn() as conn:
            self.assertEqual(check_invariant(conn), 0)

    def test_invariant_survives_the_state_the_old_one_could_not(self):
        """The whole reason recover_damaged_deals.py was archived.

        Its invariant asserted zero rows with `1yr_Avg IS NULL AND List_at IS NOT
        NULL`. Removing the fallback makes exactly that state legal: a book whose
        inferred sales are all older than 365 days gets a valid List_at from the
        3-year window and a NULL 1yr_Avg. This invariant must not trip on it.
        """
        _insert(self.db_path, 'OLDSALES01', deal_trust='50', yr_avg=None,
                list_at=42.0)
        with self._conn() as conn:
            self.assertEqual(
                check_invariant(conn), 0,
                "A valid List_at with a NULL 1yr_Avg is the expected post-B-6 "
                "state and must not abort the cleanup.")
            # And prove the archived invariant WOULD have tripped on it.
            old_invariant = conn.execute(
                'SELECT COUNT(*) FROM deals '
                'WHERE "1yr_Avg" IS NULL AND "List_at" IS NOT NULL').fetchone()[0]
        self.assertEqual(old_invariant, 1,
                         "Fixture should reproduce the state that retired the old "
                         "invariant.")

    def test_invariant_trips_when_the_marker_stops_tracking_the_value(self):
        _insert(self.db_path, 'BROKEN0001', deal_trust=LOW_EST_MARKER, yr_avg=None)
        with self._conn() as conn:
            self.assertEqual(check_invariant(conn), 1)

    def test_run_cleanup_aborts_and_deletes_nothing_when_the_invariant_trips(self):
        _insert(self.db_path, 'BROKEN0001', deal_trust=LOW_EST_MARKER, yr_avg=None)
        _insert(self.db_path, 'LOWEST0001', deal_trust=LOW_EST_MARKER, yr_avg='88.0')
        with self.assertRaises(CleanupAbort):
            run_cleanup(self.db_path, self.backup_dir, apply_mode=True)
        with self._conn() as conn:
            remaining = conn.execute('SELECT COUNT(*) FROM deals').fetchone()[0]
        self.assertEqual(remaining, 2, "An aborted run must delete nothing.")


class CleanupRun(TempDealsDb):
    def setUp(self):
        super().setUp()
        _build_table(self.db_path)
        _insert(self.db_path, 'LOWEST0001', deal_trust=LOW_EST_MARKER, yr_avg='88.0')
        _insert(self.db_path, 'LOWEST0002', deal_trust=LOW_EST_MARKER, yr_avg='88.0',
                list_at=12.0)
        _insert(self.db_path, 'NORMAL0001', deal_trust='33', yr_avg='20.0',
                list_at=40.0)

    def test_dry_run_deletes_nothing_and_still_writes_the_asin_list(self):
        deleted = run_cleanup(self.db_path, self.backup_dir, apply_mode=False)
        self.assertEqual(deleted, 0)
        with self._conn() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM deals').fetchone()[0], 3)
        listed = [f for f in os.listdir(self.backup_dir)
                  if f.startswith('low_est_asins_dryrun_')]
        self.assertEqual(len(listed), 1)
        with open(os.path.join(self.backup_dir, listed[0])) as fh:
            self.assertEqual(fh.read().split(), ['LOWEST0001', 'LOWEST0002'])

    def test_dry_run_takes_a_real_backup(self):
        """Deliberate: the apply run must not be the first time the backup path runs."""
        run_cleanup(self.db_path, self.backup_dir, apply_mode=False)
        backups = [f for f in os.listdir(self.backup_dir) if f.endswith('.bak')]
        self.assertEqual(len(backups), 1)
        count = sqlite3.connect(os.path.join(self.backup_dir, backups[0])) \
            .execute('SELECT COUNT(*) FROM deals').fetchone()[0]
        self.assertEqual(count, 3, "Backup must be a faithful copy.")

    def test_apply_deletes_only_the_targets(self):
        deleted = run_cleanup(self.db_path, self.backup_dir, apply_mode=True)
        self.assertEqual(deleted, 2)
        with self._conn() as conn:
            remaining = [r[0] for r in conn.execute('SELECT ASIN FROM deals')]
        self.assertEqual(remaining, ['NORMAL0001'])

    def test_apply_is_idempotent(self):
        """A second apply finds nothing and changes nothing.

        The second run gets its own backup directory on purpose. The backup
        filename carries a whole-second timestamp and the script refuses to
        overwrite an existing backup, so two runs inside the same second collide -
        which is the guard working, not a defect, and is covered separately below.
        A human typing two commands cannot hit it.
        """
        run_cleanup(self.db_path, self.backup_dir, apply_mode=True)
        second_dir = os.path.join(self.tmpdir, 'db_backups_2')
        deleted = run_cleanup(self.db_path, second_dir, apply_mode=True)
        self.assertEqual(deleted, 0)
        with self._conn() as conn:
            remaining = [r[0] for r in conn.execute('SELECT ASIN FROM deals')]
        self.assertEqual(remaining, ['NORMAL0001'])

    def test_refuses_to_overwrite_an_existing_backup(self):
        """The backup is the only way back; it must never be clobbered."""
        run_cleanup(self.db_path, self.backup_dir, apply_mode=False)
        with patch('cleanup_low_est_rows.datetime') as mock_dt:
            mock_dt.now.return_value = self._first_backup_time()
            with self.assertRaises(CleanupAbort) as ctx:
                run_cleanup(self.db_path, self.backup_dir, apply_mode=False)
        self.assertIn('already exists', str(ctx.exception))

    def _first_backup_time(self):
        name = [f for f in os.listdir(self.backup_dir) if f.endswith('.bak')][0]
        stamp = name.rsplit('.low-est-', 1)[1][:-len('.bak')]
        return real_datetime.strptime(stamp, '%Y%m%d-%H%M%S')


class InferredSaleCountColumn(TempDealsDb):
    """The column must reach the live table before the first upsert binds it.

    An upsert against a table missing the column fails with "no such column" and
    takes the whole batch with it, which would stop ingestion. These tests prove the
    existing dynamic schema migration closes that gap with no manual step.
    """

    def test_header_and_function_list_stay_index_aligned(self):
        """processing.py pairs them by index: row_data[headers[i]] = val."""
        from keepa_deals.field_mappings import FUNCTION_LIST
        headers = _load_headers()
        self.assertEqual(
            len(headers), len(FUNCTION_LIST),
            "headers.json and FUNCTION_LIST must stay the same length; "
            "_process_single_deal writes row_data[headers[i]] for each function.")
        self.assertIn('Inferred Sale Count', headers)

    def test_column_sanitizes_as_expected(self):
        self.assertEqual(
            db_utils.sanitize_col_name('Inferred Sale Count'), 'Inferred_Sale_Count')

    def test_schema_migration_adds_the_column_to_an_existing_table(self):
        _build_table(self.db_path, omit=('Inferred Sale Count',))
        db_utils.DB_PATH = self.db_path

        conn = self._conn()
        before = db_utils.get_table_columns(conn.cursor(), 'deals')
        conn.close()
        self.assertNotIn('Inferred_Sale_Count', before,
                         "Fixture must start without the column.")

        db_utils.create_deals_table_if_not_exists()

        conn = self._conn()
        after = {r[1]: r[2] for r in conn.execute("PRAGMA table_info(deals)")}
        conn.close()
        self.assertIn('Inferred_Sale_Count', after,
                      "create_deals_table_if_not_exists must ALTER the column in. "
                      "It runs at smart_ingestor.py:311, before both upsert sites.")
        self.assertEqual(after['Inferred_Sale_Count'], 'INTEGER')

    def test_upsert_round_trips_the_count_after_migration(self):
        _build_table(self.db_path, omit=('Inferred Sale Count',))
        db_utils.DB_PATH = self.db_path
        db_utils.create_deals_table_if_not_exists()

        headers = _load_headers()
        row = {db_utils.sanitize_col_name(h): None for h in headers}
        row['ASIN'] = 'COUNTED001'
        row['Inferred_Sale_Count'] = 4

        conn = self._conn()
        cur = conn.cursor()
        db_utils.upsert_deal_rows(cur, [row], headers)
        conn.commit()
        stored = cur.execute(
            'SELECT "Inferred_Sale_Count" FROM deals WHERE ASIN = ?',
            ('COUNTED001',)).fetchone()[0]
        conn.close()
        self.assertEqual(stored, 4)

    def test_a_zero_count_is_stored_as_zero_not_null(self):
        """0 means "computed, none found". NULL means "never computed"."""
        _build_table(self.db_path)
        db_utils.DB_PATH = self.db_path
        headers = _load_headers()
        row = {db_utils.sanitize_col_name(h): None for h in headers}
        row['ASIN'] = 'ZEROCOUNT1'
        row['Inferred_Sale_Count'] = 0

        conn = self._conn()
        cur = conn.cursor()
        db_utils.upsert_deal_rows(cur, [row], headers)
        conn.commit()
        stored = cur.execute(
            'SELECT "Inferred_Sale_Count" FROM deals WHERE ASIN = ?',
            ('ZEROCOUNT1',)).fetchone()[0]
        conn.close()
        self.assertEqual(stored, 0)
        self.assertIsNotNone(stored)


if __name__ == '__main__':
    unittest.main()
