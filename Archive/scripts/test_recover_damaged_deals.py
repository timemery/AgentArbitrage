import contextlib
import io
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from recover_damaged_deals import (  # noqa: E402
    DAMAGED_PREDICATE,
    RecoveryAbort,
    check_invariant,
    run_recovery,
    select_damaged_asins,
)


class RecoverDamagedDealsTest(unittest.TestCase):
    """
    Covers the three properties the recovery script must not lose:
      1. the predicate selects only damaged non-heavy rows,
      2. the invariant aborts when a damaged row still carries a List_at,
      3. a dry run deletes nothing.
    """

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.test_dir, 'test_deals.db')
        self.backup_dir = os.path.join(self.test_dir, 'db_backups')
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            'CREATE TABLE deals ('
            'id INTEGER PRIMARY KEY, ASIN TEXT UNIQUE, '
            '"1yr_Avg" TEXT, "List_at" REAL, source TEXT)'
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _insert(self, rows):
        conn = sqlite3.connect(self.db_path)
        conn.executemany(
            'INSERT INTO deals (ASIN, "1yr_Avg", "List_at", source) '
            'VALUES (?, ?, ?, ?)', rows
        )
        conn.commit()
        conn.close()

    def _run_quiet(self, **kwargs):
        """run_recovery is chatty by design; the suite does not need its report."""
        with contextlib.redirect_stdout(io.StringIO()):
            return run_recovery(self.db_path, self.backup_dir, **kwargs)

    def _asins(self):
        conn = sqlite3.connect(self.db_path)
        try:
            return sorted(r[0] for r in conn.execute('SELECT ASIN FROM deals'))
        finally:
            conn.close()

    def _seed_mixed(self):
        """One row per case the predicate has to separate."""
        self._insert([
            # Damaged: nulled by the light path. Must be selected.
            ('DAMAGED_LIGHT', None, None, 'smart_ingestor_light'),
            # Damaged: nulled on the stale rescue path. Must be selected.
            ('DAMAGED_RESCUE', None, None, 'stale_rescue'),
            # Heavy path row with no determinable list price. Deliberate
            # persistence, not damage - must NOT be selected.
            ('HEAVY_NO_LIST', None, None, 'smart_ingestor'),
            # Healthy light row. Must NOT be selected.
            ('HEALTHY_LIGHT', '12.34', 25.0, 'smart_ingestor_light'),
            # Light row with a list price but no 1yr_Avg would break the
            # invariant, so it is tested separately, not here.
            # Row with a NULL source: predicate leaves it alone (NULL != 'x'
            # is NULL in SQL). Conservative on purpose.
            ('NULL_SOURCE', None, None, None),
        ])

    def test_predicate_selects_only_damaged_non_heavy_rows(self):
        self._seed_mixed()
        conn = sqlite3.connect(self.db_path)
        try:
            self.assertEqual(
                select_damaged_asins(conn),
                ['DAMAGED_LIGHT', 'DAMAGED_RESCUE'],
                'Predicate must select the damaged light and rescue rows only: '
                + DAMAGED_PREDICATE
            )
        finally:
            conn.close()

    def test_invariant_aborts_when_damaged_row_has_list_at(self):
        self._seed_mixed()
        self._insert([('BROKEN_FINGERPRINT', None, 41.5, 'stale_rescue')])

        conn = sqlite3.connect(self.db_path)
        try:
            self.assertEqual(check_invariant(conn), 1)
        finally:
            conn.close()

        before = self._asins()
        with self.assertRaises(RecoveryAbort) as ctx:
            self._run_quiet(apply_mode=True)
        self.assertIn('1yr_Avg', str(ctx.exception))
        self.assertEqual(self._asins(), before,
                         'An aborted run must delete nothing.')

    def test_dry_run_deletes_nothing(self):
        self._seed_mixed()
        before = self._asins()

        deleted = self._run_quiet(apply_mode=False)

        self.assertEqual(deleted, 0)
        self.assertEqual(self._asins(), before,
                         'A dry run must leave every row in place.')
        written = os.listdir(self.backup_dir)
        self.assertTrue(any(f.startswith('damaged_asins_dryrun_') for f in written),
                        'Dry run must still write the target ASIN list.')

    def test_apply_deletes_exactly_the_damaged_rows(self):
        self._seed_mixed()

        deleted = self._run_quiet(apply_mode=True)

        self.assertEqual(deleted, 2)
        self.assertEqual(
            self._asins(),
            ['HEALTHY_LIGHT', 'HEAVY_NO_LIST', 'NULL_SOURCE']
        )


if __name__ == '__main__':
    unittest.main()
