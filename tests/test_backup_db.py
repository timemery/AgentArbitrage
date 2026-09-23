"""backup_db.sh must take a complete, verified copy of a live WAL-mode database.

Trello #146. The script used to be a plain `cp deals.db`. deals.db runs in WAL mode, so
committed transactions still sitting in deals.db-wal were missing from the copy: the
backup opened, restored and looked fine, and was short.

What these tests pin:

*   A commit that is only in the -wal file is in the backup.
*   The live database is opened read-only. On the box the script runs as root against a
    www-data-owned deals.db; a read-write connection that is the last one to close
    checkpoints the WAL into deals.db and deletes deals.db-wal. Here that shows up as
    the main file changing and the -wal file disappearing.
*   The check is on the backup itself (integrity_check, expected tables present and
    non-empty), never a row-count match against a database that is being written to.
*   A backup that fails the check exits non-zero and leaves nothing in db_backups/ - no
    half-written file that restore_db.sh, which takes the newest name containing
    "deals.db", could pick up.

Every case drives the real script with bash in a temp directory. Nothing here imports a
project module.
"""

import hashlib
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import textwrap
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO_ROOT, 'backup_db.sh')
FINAL_NAME = re.compile(r'^deals\.db\.\d{14}\.bak$')

CHECKPOINTED_DEALS = 5
WAL_ONLY_DEALS = 3


def _make_db(path, deals=CHECKPOINTED_DEALS, with_system_state=True):
    """A WAL-mode DB whose rows are all checkpointed into the main file."""
    conn = sqlite3.connect(path)
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('CREATE TABLE deals (id INTEGER PRIMARY KEY AUTOINCREMENT, ASIN TEXT UNIQUE)')
    conn.execute('CREATE INDEX idx_deals_asin ON deals (ASIN)')
    conn.executemany('INSERT INTO deals (ASIN) VALUES (?)',
                     [('A{:09d}'.format(i),) for i in range(deals)])
    if with_system_state:
        conn.execute('CREATE TABLE system_state (key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP)')
        conn.execute("INSERT INTO system_state VALUES ('watermark_iso', '2026-09-23T00:00:00+00:00', NULL)")
    conn.commit()
    conn.close()  # last connection: checkpoints and removes the -wal


def _commit_into_wal_and_die(path, rows=WAL_ONLY_DEALS):
    """Commit rows that reach deals.db-wal but never the main file.

    The writer exits without closing, as a killed worker would, so no checkpoint runs.
    """
    child = textwrap.dedent('''
        import os, sqlite3, sys
        conn = sqlite3.connect(sys.argv[1])
        conn.execute('PRAGMA wal_autocheckpoint=0')
        conn.executemany('INSERT INTO deals (ASIN) VALUES (?)',
                         [('W{:09d}'.format(i),) for i in range(int(sys.argv[2]))])
        conn.commit()
        os._exit(0)
    ''')
    subprocess.run([sys.executable, '-c', child, path, str(rows)], check=True)


def _sha256(path):
    with open(path, 'rb') as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def _count(path, table):
    uri = 'file:{}?immutable=1'.format(path)
    conn = sqlite3.connect(uri, uri=True)
    try:
        return conn.execute('SELECT COUNT(*) FROM {}'.format(table)).fetchone()[0]
    finally:
        conn.close()


class _ScriptCase(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.workdir = self._tmp.name
        self.db = os.path.join(self.workdir, 'deals.db')
        self.backup_dir = os.path.join(self.workdir, 'db_backups')

    def tearDown(self):
        self._tmp.cleanup()

    def run_script(self):
        env = dict(os.environ, DATABASE_URL=self.db)
        return subprocess.run(['bash', SCRIPT], cwd=self.workdir, env=env,
                              capture_output=True, text=True, timeout=120)

    def backup_dir_entries(self):
        if not os.path.isdir(self.backup_dir):
            return []
        return sorted(os.listdir(self.backup_dir))  # includes dotfiles


class ItCapturesCommitsStillInTheWal(_ScriptCase):

    def setUp(self):
        super().setUp()
        _make_db(self.db)
        _commit_into_wal_and_die(self.db)
        # Precondition: the main file alone is short. This is what `cp` copied.
        self.assertEqual(_count(self.db, 'deals'), CHECKPOINTED_DEALS)
        self.assertTrue(os.path.getsize(self.db + '-wal') > 0)

    def test_the_backup_holds_every_committed_row(self):
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        entries = self.backup_dir_entries()
        self.assertEqual(len(entries), 1, entries)
        self.assertRegex(entries[0], FINAL_NAME)
        backup = os.path.join(self.backup_dir, entries[0])
        self.assertEqual(_count(backup, 'deals'), CHECKPOINTED_DEALS + WAL_ONLY_DEALS)

    def test_the_backup_is_a_single_self_contained_file(self):
        self.assertEqual(self.run_script().returncode, 0)
        # No -wal/-shm/-journal next to the backup, and no leftover temp file.
        self.assertEqual(len(self.backup_dir_entries()), 1, self.backup_dir_entries())

    def test_the_live_database_is_opened_read_only(self):
        main_before = _sha256(self.db)
        wal_before = _sha256(self.db + '-wal')

        self.assertEqual(self.run_script().returncode, 0)

        # A read-write connection closing last would checkpoint the WAL into the main
        # file and delete the -wal. Read-only cannot.
        self.assertEqual(_sha256(self.db), main_before)
        self.assertTrue(os.path.exists(self.db + '-wal'))
        self.assertEqual(_sha256(self.db + '-wal'), wal_before)


class AFailedCheckLeavesNothingBehind(_ScriptCase):

    def assert_failed_cleanly(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.backup_dir_entries(), [])
        self.assertNotIn('Database backed up to', result.stdout)

    def test_an_empty_deals_table_fails(self):
        _make_db(self.db, deals=0)
        result = self.run_script()
        self.assert_failed_cleanly(result)
        self.assertIn('deals', result.stdout + result.stderr)

    def test_a_missing_expected_table_fails(self):
        _make_db(self.db, with_system_state=False)
        result = self.run_script()
        self.assert_failed_cleanly(result)
        self.assertIn('system_state', result.stdout + result.stderr)

    def test_a_corrupt_database_fails_integrity_check(self):
        _make_db(self.db, deals=2000)
        conn = sqlite3.connect(self.db)
        page_size = conn.execute('PRAGMA page_size').fetchone()[0]
        root = conn.execute(
            "SELECT rootpage FROM sqlite_master WHERE name = 'idx_deals_asin'").fetchone()[0]
        conn.close()
        # Overwrite the index root page's b-tree header (page type, cell count). The
        # backup API copies pages without parsing them, so only the integrity check
        # can notice.
        with open(self.db, 'r+b') as fh:
            fh.seek((root - 1) * page_size)
            fh.write(b'\xff' * 8)

        result = self.run_script()
        self.assert_failed_cleanly(result)
        self.assertIn('integrity', (result.stdout + result.stderr).lower())

    def test_a_missing_database_fails(self):
        result = self.run_script()
        self.assert_failed_cleanly(result)


if __name__ == '__main__':
    unittest.main()
