#!/usr/bin/env python3
"""
recover_damaged_deals.py

One-time recovery script for the A-7 damaged rows in deals.db.

WHY DELETING IS THE RECOVERY
----------------------------
The A-7 light-update upsert defect (PR #330, dev log 2026-09-09) wrote 215 of 246
columns as NULL on every light update, including 1yr_Avg and List_at. Those rows
cannot be healed in place: while a row exists the Smart Ingestor always routes its
ASIN to the light path, because existing_asins_set is rebuilt from a live SELECT
every run and the Zombie Data Defense heavy re-fetch is commented out. Stale Rescue
is light-only, and recalculator.py is API-free and cannot rebuild List_at (it derives
from infer_sale_events, which needs the Keepa csv history that deals.db never stores).

Deleting the row is therefore not the cheaper option, it is the only mechanism that
routes the ASIN back through the heavy path, where 1yr_Avg and List_at are computed
from scratch. Re-acquisition is passive and not guaranteed: an ASIN only returns if
Keepa still surfaces it in the deal feed. That is why the target ASIN list is written
to db_backups/ - so the return rate can be measured later.

The damaged rows are invisible on the dashboard already. /api/deals and
/api/deal-count both append "1yr_Avg" IS NOT NULL on every branch, and that clause is
not user-filterable, so deleting these rows removes zero visible deals.

USAGE
-----
Run from the application root (/var/www/agentarbitrage on the AA box), as www-data,
with all Celery services stopped.

    # Dry run - reports only, deletes nothing:
    sudo -u www-data venv/bin/python recover_damaged_deals.py

    # Apply - deletes the damaged rows in one transaction:
    sudo -u www-data venv/bin/python recover_damaged_deals.py --apply

There is no --force flag. Every safety check is mandatory; if one fails, fix the
cause and re-run.

WHAT IT TOUCHES
---------------
The deals table only. user_restrictions, prime_picks, confirmed_buys,
confirmed_buy_units, inventory_ledger and the system_state watermark are never read
for writing and never modified. No VACUUM is run: the Janitor already VACUUMs on
large deletions and doing it here would rewrite the whole file outside the
transaction.

FILES IT WRITES
---------------
Both go into db_backups/, which is covered by .gitignore, so nothing this script
writes can end up tracked by git:
  db_backups/deals.db.recovery-<timestamp>.bak    - consistent SQLite backup
  db_backups/damaged_asins_<mode>_<timestamp>.txt - one target ASIN per line
"""

import argparse
import glob
import os
import pwd
import sqlite3
import subprocess
import sys
from datetime import datetime

# Add project root to sys.path (mirrors run_deals_migration.py)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BACKUP_DIR = os.path.join(REPO_ROOT, 'db_backups')
TABLE_NAME = 'deals'
EXPECTED_USER = 'www-data'
REDIS_LOCK_KEY = 'smart_ingestor_lock'
REDIS_URL = 'redis://127.0.0.1:6379/0'  # celery_config.broker_url

# The recovery predicate, settled in Dev_Logs/2026-09-10 §7. Narrow on purpose:
#   1yr_Avg IS NULL  - the reliable A-7 fingerprint. The heavy path wrote 1yr_Avg on
#                      295 of 295 rows, so a NULL here means the row was never
#                      completed by a heavy pass or was blanked by the light path.
#   List_at IS NULL  - the row carries no list price either, so it is already
#                      invisible to /api/deals and worth nothing as it stands.
#   source != 'smart_ingestor' - never delete a heavy-path row. The heavy path
#                      legitimately persists rows with no determinable list price
#                      (159 of 295 at the A-7 baseline); those are a deliberate
#                      "Missing List at" persistence, not damage. Note this also
#                      leaves rows with a NULL source untouched, since NULL != 'x'
#                      is NULL in SQL rather than true. That is the conservative
#                      direction and is intentional.
DAMAGED_PREDICATE = (
    '"1yr_Avg" IS NULL AND "List_at" IS NULL AND source != \'smart_ingestor\''
)

# Must be 0 before anything is deleted. A row with a list price but no 1yr_Avg would
# mean 1yr_Avg IS NULL is no longer a safe fingerprint for the damage, and the
# predicate above could not be trusted.
INVARIANT_SQL = (
    'SELECT COUNT(*) FROM {table} '
    'WHERE "1yr_Avg" IS NULL AND "List_at" IS NOT NULL'
).format(table=TABLE_NAME)


class RecoveryAbort(Exception):
    """Raised when a safety check fails. Nothing has been deleted."""


# --------------------------------------------------------------------------
# Preflight
# --------------------------------------------------------------------------

def _running_user():
    return pwd.getpwuid(os.geteuid()).pw_name


def _matching_processes(pattern):
    """Returns 'pid command' lines matching pattern, excluding this process."""
    try:
        out = subprocess.run(
            ['pgrep', '-af', pattern],
            capture_output=True, text=True, check=False
        ).stdout
    except FileNotFoundError:
        raise RecoveryAbort(
            "Could not run 'pgrep', so it is impossible to confirm that the "
            "background services are stopped. Install procps or check by hand "
            "before re-running."
        )
    own_pid = str(os.getpid())
    hits = []
    for line in out.splitlines():
        pid, _, cmd = line.partition(' ')
        if pid == own_pid:
            continue
        if os.path.basename(__file__) in cmd:
            continue
        hits.append(line)
    return hits


def preflight():
    """Aborts unless it is safe to touch deals.db. Nothing here writes anything."""
    print("=" * 70)
    print("PREFLIGHT")
    print("=" * 70)

    user = _running_user()
    if user != EXPECTED_USER:
        raise RecoveryAbort(
            "This script is running as '{actual}', not '{expected}'.\n"
            "Everything on the box that touches deals.db runs as {expected}, and a "
            "run as another user leaves the database, its -wal and its -shm files "
            "owned by that user, which silently breaks Celery and Apache after the "
            "restart.\n"
            "Re-run it as:  sudo -u {expected} venv/bin/python recover_damaged_deals.py"
            .format(actual=user, expected=EXPECTED_USER)
        )
    print("  Running as: {} - OK".format(user))

    for pattern, label in (('celery', 'Celery'),
                           ('monitor_and_restart', 'the Celery watchdog')):
        hits = _matching_processes(pattern)
        if hits:
            raise RecoveryAbort(
                "{label} is still running, so something can write to deals.db while "
                "this script deletes from it.\n"
                "Found:\n    {hits}\n"
                "Stop everything first with:  ./kill_everything_force.sh"
                .format(label=label, hits="\n    ".join(hits))
            )
        print("  No {} process running - OK".format(label))

    try:
        import redis  # imported lazily so the module stays importable in tests
    except ImportError:
        raise RecoveryAbort(
            "The 'redis' package is not importable, so the Smart Ingestor lock "
            "cannot be checked. Run this from the application virtualenv:\n"
            "    sudo -u www-data venv/bin/python recover_damaged_deals.py"
        )

    try:
        client = redis.Redis.from_url(REDIS_URL)
        lock_held = client.exists(REDIS_LOCK_KEY)
    except Exception as exc:
        raise RecoveryAbort(
            "Could not reach Redis at {url} to check the Smart Ingestor lock ({exc}).\n"
            "If Redis is genuinely down then nothing is ingesting, but confirm that "
            "by hand rather than assuming it - re-run once Redis is reachable."
            .format(url=REDIS_URL, exc=exc)
        )

    if lock_held:
        raise RecoveryAbort(
            "The Smart Ingestor lock '{key}' is still held in Redis. Either an "
            "ingestion run is in progress, or a crashed run left the key behind.\n"
            "./kill_everything_force.sh normally clears it - it wipes Redis, deletes "
            "dump.rdb and restarts the server. A lock can still survive that if the "
            "wipe step failed (it only warns, it does not abort) or if Redis was "
            "restarted from a dump the sweep did not find.\n"
            "One command clears it:\n"
            "    redis-cli -h 127.0.0.1 -n 0 DEL {key}"
            .format(key=REDIS_LOCK_KEY)
        )
    print("  Redis lock '{}' not held - OK".format(REDIS_LOCK_KEY))
    print()


# --------------------------------------------------------------------------
# Backup
# --------------------------------------------------------------------------

def backup_database(db_path, backup_dir, timestamp):
    """
    Takes a consistent copy of deals.db using SQLite's own backup API and verifies
    it by row count. Returns the backup path.

    backup_db.sh is deliberately not used here. It is a plain `cp` of a WAL-mode
    database, and after kill_everything_force.sh commits can still be sitting in
    deals.db-wal that a cp of deals.db alone would not capture. The backup API reads
    through the WAL and writes a single self-contained file.
    """
    print("=" * 70)
    print("BACKUP")
    print("=" * 70)

    try:
        os.makedirs(backup_dir, exist_ok=True)
    except OSError as exc:
        raise RecoveryAbort(
            "Could not create the backup directory '{dir}' ({exc}). It must exist "
            "and be writable by {user} before this script can run."
            .format(dir=backup_dir, exc=exc, user=EXPECTED_USER)
        )

    backup_path = os.path.join(
        backup_dir, '{name}.recovery-{ts}.bak'.format(
            name=os.path.basename(db_path), ts=timestamp)
    )
    if os.path.exists(backup_path):
        raise RecoveryAbort(
            "A backup already exists at '{path}'. Refusing to overwrite it."
            .format(path=backup_path)
        )

    src = dst = None
    try:
        src = sqlite3.connect(db_path)
        dst = sqlite3.connect(backup_path)
        src.backup(dst)
        dst.commit()
    except Exception as exc:
        raise RecoveryAbort(
            "The database backup failed ({exc}). Nothing has been deleted. Check "
            "that '{dir}' is writable by {user} and that there is free disk space."
            .format(exc=exc, dir=backup_dir, user=EXPECTED_USER)
        )
    finally:
        if dst is not None:
            dst.close()
        if src is not None:
            src.close()

    live_count = _scalar(db_path, 'SELECT COUNT(*) FROM {}'.format(TABLE_NAME))
    backup_count = _scalar(backup_path, 'SELECT COUNT(*) FROM {}'.format(TABLE_NAME))
    if live_count != backup_count:
        raise RecoveryAbort(
            "The backup is not a faithful copy: the live database holds {live} deals "
            "but the backup holds {backup}. Nothing has been deleted. Do not re-run "
            "until this is understood - a writer is probably still active."
            .format(live=live_count, backup=backup_count)
        )

    print("  Backup written to: {}".format(backup_path))
    print("  Size: {:,} bytes".format(os.path.getsize(backup_path)))
    print("  Row count verified: {:,} deals in both live DB and backup - OK"
          .format(live_count))
    print()
    return backup_path


def _scalar(db_path, sql):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql).fetchone()[0]
    finally:
        conn.close()


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def count_by_source(conn):
    """
    Returns [(source, total, yr_avg_null, list_at_null), ...] ordered by source.

    Read these with the caveat from the dev logs: the light path rewrites `source`,
    so rows migrate between cohorts. A falling stale_rescue count is not deletion.
    """
    rows = conn.execute(
        'SELECT source, COUNT(*), '
        'SUM("1yr_Avg" IS NULL), SUM("List_at" IS NULL) '
        'FROM {table} GROUP BY source ORDER BY source'.format(table=TABLE_NAME)
    ).fetchall()
    return [(r[0], r[1], r[2] or 0, r[3] or 0) for r in rows]


def print_counts(conn, label):
    print("-" * 70)
    print(label)
    print("-" * 70)
    print("  {:<24} {:>10} {:>14} {:>14}".format(
        "source", "total", "1yr_Avg NULL", "List_at NULL"))
    totals = [0, 0, 0]
    for source, total, yr_null, list_null in count_by_source(conn):
        print("  {:<24} {:>10,} {:>14,} {:>14,}".format(
            str(source), total, yr_null, list_null))
        totals[0] += total
        totals[1] += yr_null
        totals[2] += list_null
    print("  {:<24} {:>10,} {:>14,} {:>14,}".format(
        "ALL", totals[0], totals[1], totals[2]))
    print()


def check_invariant(conn):
    """Returns the offending row count. Caller aborts if it is not 0."""
    return conn.execute(INVARIANT_SQL).fetchone()[0]


def select_damaged_asins(conn):
    rows = conn.execute(
        'SELECT ASIN FROM {table} WHERE {pred} ORDER BY ASIN'
        .format(table=TABLE_NAME, pred=DAMAGED_PREDICATE)
    ).fetchall()
    return [r[0] for r in rows]


def write_asin_list(asins, backup_dir, timestamp, apply_mode):
    """Writes one ASIN per line so the return rate can be measured later."""
    os.makedirs(backup_dir, exist_ok=True)
    path = os.path.join(
        backup_dir, 'damaged_asins_{mode}_{ts}.txt'.format(
            mode='applied' if apply_mode else 'dryrun', ts=timestamp)
    )
    with open(path, 'w') as fh:
        for asin in asins:
            fh.write('{}\n'.format(asin))
    return path


# --------------------------------------------------------------------------
# Main recovery
# --------------------------------------------------------------------------

def run_recovery(db_path, backup_dir, apply_mode):
    """
    Backs up, checks the invariant, reports, and (only with apply_mode) deletes.
    Returns the number of rows deleted (0 on a dry run).
    Raises RecoveryAbort on any failed check, having deleted nothing.
    """
    if not os.path.exists(db_path):
        raise RecoveryAbort("Database file not found at '{}'.".format(db_path))

    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    print("Database: {}".format(db_path))
    print("Mode:     {}".format(
        "APPLY (rows will be deleted)" if apply_mode
        else "DRY RUN (nothing will be deleted)"))
    print()

    backup_database(db_path, backup_dir, timestamp)

    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.isolation_level = None  # explicit transaction control
    try:
        conn.execute('PRAGMA busy_timeout=30000')

        print("=" * 70)
        print("INVARIANT CHECK")
        print("=" * 70)
        offenders = check_invariant(conn)
        if offenders != 0:
            raise RecoveryAbort(
                "{n} row(s) have no 1yr_Avg but do have a List_at.\n"
                "That should be impossible, and it means '1yr_Avg IS NULL' is no "
                "longer a safe fingerprint for the A-7 damage. The delete predicate "
                "cannot be trusted, so nothing has been deleted. Investigate those "
                "rows before running this script again:\n"
                "    SELECT ASIN, source FROM deals "
                "WHERE \"1yr_Avg\" IS NULL AND \"List_at\" IS NOT NULL;"
                .format(n=offenders)
            )
        print("  0 rows with 1yr_Avg NULL and List_at NOT NULL - OK")
        print()

        print("=" * 70)
        print("BEFORE")
        print("=" * 70)
        print_counts(conn, "Counts by source")

        asins = select_damaged_asins(conn)
        asin_path = write_asin_list(asins, backup_dir, timestamp, apply_mode)
        print("  Target rows matching the recovery predicate: {:,}".format(len(asins)))
        print("  Predicate: {}".format(DAMAGED_PREDICATE))
        print("  Target ASIN list written to: {}".format(asin_path))
        print()

        deleted = 0
        if not apply_mode:
            print("=" * 70)
            print("DRY RUN - NOTHING DELETED")
            print("=" * 70)
            print("  Re-run with --apply to delete the {:,} rows listed above."
                  .format(len(asins)))
            print()
        elif not asins:
            print("=" * 70)
            print("NOTHING TO DO")
            print("=" * 70)
            print("  No rows match the recovery predicate. Database untouched.")
            print()
        else:
            print("=" * 70)
            print("APPLYING DELETE (single transaction)")
            print("=" * 70)
            try:
                conn.execute('BEGIN IMMEDIATE')
                cursor = conn.execute(
                    'DELETE FROM {table} WHERE {pred}'
                    .format(table=TABLE_NAME, pred=DAMAGED_PREDICATE)
                )
                deleted = cursor.rowcount
                conn.execute('COMMIT')
            except Exception as exc:
                conn.execute('ROLLBACK')
                raise RecoveryAbort(
                    "The delete failed and was rolled back ({exc}). The database is "
                    "unchanged. The backup taken above is still valid."
                    .format(exc=exc)
                )
            print("  Deleted {:,} rows from {}.".format(deleted, TABLE_NAME))
            print("  No VACUUM run, by design.")
            print()

            print("=" * 70)
            print("AFTER")
            print("=" * 70)
            print_counts(conn, "Counts by source")
    finally:
        conn.close()

    print_db_file_listing(db_path)
    return deleted


def print_db_file_listing(db_path):
    """Shows ownership of deals.db and its WAL/SHM siblings before the restart."""
    print("=" * 70)
    print("DATABASE FILE OWNERSHIP (ls -l deals.db*)")
    print("=" * 70)
    files = sorted(glob.glob(db_path + '*'))
    if not files:
        print("  No files matched '{}*'.".format(db_path))
        return
    subprocess.run(['ls', '-l'] + files, check=False)
    print()
    print("  Every file above must be owned by {user}:{user} before services are "
          "restarted.".format(user=EXPECTED_USER))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Delete the A-7 damaged deals rows so the Smart Ingestor can '
                    're-acquire them via the heavy path. Dry run by default.'
    )
    parser.add_argument(
        '--apply', action='store_true',
        help='Actually delete the matching rows. Without this the script only reports.'
    )
    args = parser.parse_args(argv)

    db_path = os.getenv('DATABASE_URL', os.path.join(REPO_ROOT, 'deals.db'))

    try:
        preflight()
        run_recovery(db_path, DEFAULT_BACKUP_DIR, args.apply)
    except RecoveryAbort as exc:
        print()
        print("ABORTED - nothing was deleted.")
        print()
        print(str(exc))
        return 1

    print()
    print("Done.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
