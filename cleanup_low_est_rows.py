#!/usr/bin/env python3
"""
cleanup_low_est_rows.py

One-time cleanup for the rows whose `1yr_Avg` came from the Keepa listing-average
fallback that was removed from `get_1yr_avg_sale_price` on 2026-09-11 (audit B-6).

WHAT THESE ROWS ARE
-------------------
Until this PR, `get_1yr_avg_sale_price` fell through to
`max(stats.avg365[2, 19, 20, 21, 22])` - the most expensive of five Keepa
listing-average condition tiers - whenever no inferred sale landed inside the last
365 days. When that fired, `processing.py` overwrote `Deal Trust` with the literal
string "Low (Est.)".

So `Deal_Trust = 'Low (Est.)'` is the fingerprint, and it is the ONLY one. The
`price_source` flag that drove it is computed but never persisted: it is not in
`headers.json`, so `upsert_deal_rows` drops it. There is no other stored trace.

WHY DELETING IS THE CLEANUP
---------------------------
Same mechanism as `recover_damaged_deals.py` (dev log 2026-09-11). While a row
exists the Smart Ingestor always routes its ASIN to the light path, because
`existing_asins_set` is rebuilt from a live `SELECT` every run and the Zombie Data
Defense heavy re-fetch is commented out. The light path preserves `1yr_Avg` rather
than recomputing it, Stale Rescue is light-only, and `recalculator.py` is API-free
and cannot rebuild the value - it derives from `infer_sale_events`, which needs the
Keepa `csv` history that `deals.db` never stores.

Deleting is therefore not the cheaper option, it is the only mechanism that routes
the ASIN back through the heavy path, where `1yr_Avg` is recomputed from inferred
sales alone. Re-acquisition is passive and not guaranteed: an ASIN only returns if
Keepa still surfaces it in the deal feed.

WHAT THIS DOES NOT FIND
-----------------------
Rows that used the fallback but escaped the mark. In `processing.py` the
"Low (Est.)" write was the last statement of a `try` block that also ran
`get_trend`, `get_percent_discount`, `recent_inferred_sale_price` and
`analyze_sales_rank_trends`. Any exception in those four was swallowed, leaving the
fallback value stored with a normal numeric `Deal_Trust`. Those rows are
indistinguishable in SQL and this script cannot reach them. They are bounded: a
leaked row that is also dashboard-visible needs every one of its inferred sales to
be older than 365 days. Recorded as an open item; not this PR's scope.

USAGE
-----
Run from the application root (/var/www/agentarbitrage on the AA box), as www-data,
with all Celery services stopped.

    # Dry run - reports only, deletes nothing:
    sudo -u www-data venv/bin/python cleanup_low_est_rows.py

    # Apply - deletes the matching rows in one transaction:
    sudo -u www-data venv/bin/python cleanup_low_est_rows.py --apply

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
Both go into db_backups/, which is covered by .gitignore:
  db_backups/deals.db.low-est-<timestamp>.bak    - consistent SQLite backup
  db_backups/low_est_asins_<mode>_<timestamp>.txt - one target ASIN per line
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

# The marker string, exactly as processing.py wrote it before this PR removed the
# branch. An exact match on purpose: it cannot collide with a real Deal Trust
# score, which is always a "NN%" string coerced to a REAL by clean_numeric_values,
# and it cannot collide with the other non-numeric state, '-', which deal_trust()
# returns when total_offer_drops == 0 (the XAI "no offer drops" rescue). Those '-'
# rows are NOT fallback rows and must survive.
LOW_EST_MARKER = 'Low (Est.)'

CLEANUP_PREDICATE = '"Deal_Trust" = \'{}\''.format(LOW_EST_MARKER)

# Must be 0 before anything is deleted.
#
# The claim behind the predicate is that "Low (Est.)" marks a row whose stored
# `1yr_Avg` IS the listing-average fallback value. The mark was only ever written
# on the branch where the fallback had just returned a number, so a marked row with
# no `1yr_Avg` would mean the mark is tracking something other than that value -
# either another writer exists, or the value was blanked after the fact - and the
# predicate could not be trusted to mean what this script says it means.
#
# Chosen to stay true after the fallback removal, unlike the invariant in
# recover_damaged_deals.py. That one asserted no row has `1yr_Avg IS NULL AND
# List_at IS NOT NULL`, a combination this PR makes legal: a book whose inferred
# sales are all older than 365 days now gets a valid List_at from the 3-year window
# and a NULL 1yr_Avg. This invariant is unaffected by that, and once no code path
# writes the marker it holds vacuously forever.
INVARIANT_SQL = (
    'SELECT COUNT(*) FROM {table} '
    'WHERE "Deal_Trust" = \'{marker}\' AND "1yr_Avg" IS NULL'
).format(table=TABLE_NAME, marker=LOW_EST_MARKER)

# Reported, never aborted on: how many target rows are actually visible on the
# dashboard right now. /api/deals requires List_at NOT NULL and 1yr_Avg NOT NULL on
# every branch, so the rest are already invisible and deleting them removes nothing
# the user can see.
VISIBLE_SQL = (
    'SELECT COUNT(*) FROM {table} '
    'WHERE {pred} AND "List_at" IS NOT NULL AND "1yr_Avg" IS NOT NULL'
).format(table=TABLE_NAME, pred=CLEANUP_PREDICATE)


class CleanupAbort(Exception):
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
        raise CleanupAbort(
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
        raise CleanupAbort(
            "This script is running as '{actual}', not '{expected}'.\n"
            "Everything on the box that touches deals.db runs as {expected}, and a "
            "run as another user leaves the database, its -wal and its -shm files "
            "owned by that user, which silently breaks Celery and Apache after the "
            "restart.\n"
            "Re-run it as:  sudo -u {expected} venv/bin/python cleanup_low_est_rows.py"
            .format(actual=user, expected=EXPECTED_USER)
        )
    print("  Running as: {} - OK".format(user))

    for pattern, label in (('celery', 'Celery'),
                           ('monitor_and_restart', 'the Celery watchdog')):
        hits = _matching_processes(pattern)
        if hits:
            raise CleanupAbort(
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
        raise CleanupAbort(
            "The 'redis' package is not importable, so the Smart Ingestor lock "
            "cannot be checked. Run this from the application virtualenv:\n"
            "    sudo -u www-data venv/bin/python cleanup_low_est_rows.py"
        )

    try:
        client = redis.Redis.from_url(REDIS_URL)
        lock_held = client.exists(REDIS_LOCK_KEY)
    except Exception as exc:
        raise CleanupAbort(
            "Could not reach Redis at {url} to check the Smart Ingestor lock ({exc}).\n"
            "If Redis is genuinely down then nothing is ingesting, but confirm that "
            "by hand rather than assuming it - re-run once Redis is reachable."
            .format(url=REDIS_URL, exc=exc)
        )

    if lock_held:
        raise CleanupAbort(
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
        raise CleanupAbort(
            "Could not create the backup directory '{dir}' ({exc}). It must exist "
            "and be writable by {user} before this script can run."
            .format(dir=backup_dir, exc=exc, user=EXPECTED_USER)
        )

    backup_path = os.path.join(
        backup_dir, '{name}.low-est-{ts}.bak'.format(
            name=os.path.basename(db_path), ts=timestamp)
    )
    if os.path.exists(backup_path):
        raise CleanupAbort(
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
        raise CleanupAbort(
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
        raise CleanupAbort(
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
    Returns [(source, total, low_est, low_est_visible), ...] ordered by source.

    Read these with the caveat from the dev logs: the light path rewrites `source`,
    so rows migrate between cohorts. A falling stale_rescue count is not deletion.
    """
    rows = conn.execute(
        'SELECT source, COUNT(*), '
        'SUM("Deal_Trust" = \'{marker}\'), '
        'SUM("Deal_Trust" = \'{marker}\' AND "List_at" IS NOT NULL '
        '    AND "1yr_Avg" IS NOT NULL) '
        'FROM {table} GROUP BY source ORDER BY source'
        .format(table=TABLE_NAME, marker=LOW_EST_MARKER)
    ).fetchall()
    return [(r[0], r[1], r[2] or 0, r[3] or 0) for r in rows]


def print_counts(conn, label):
    print("-" * 70)
    print(label)
    print("-" * 70)
    print("  {:<24} {:>10} {:>14} {:>14}".format(
        "source", "total", "Low (Est.)", "of those, shown"))
    totals = [0, 0, 0]
    for source, total, low_est, visible in count_by_source(conn):
        print("  {:<24} {:>10,} {:>14,} {:>14,}".format(
            str(source), total, low_est, visible))
        totals[0] += total
        totals[1] += low_est
        totals[2] += visible
    print("  {:<24} {:>10,} {:>14,} {:>14,}".format(
        "ALL", totals[0], totals[1], totals[2]))
    print()


def check_invariant(conn):
    """Returns the offending row count. Caller aborts if it is not 0."""
    return conn.execute(INVARIANT_SQL).fetchone()[0]


def count_visible(conn):
    """Target rows currently visible on the dashboard. Reported, never aborted on."""
    return conn.execute(VISIBLE_SQL).fetchone()[0]


def select_target_asins(conn):
    return [r[0] for r in conn.execute(
        'SELECT ASIN FROM {table} WHERE {pred} ORDER BY ASIN'
        .format(table=TABLE_NAME, pred=CLEANUP_PREDICATE)
    ).fetchall()]


def write_asin_list(asins, backup_dir, timestamp, apply_mode):
    """Writes one ASIN per line so the return rate can be measured later."""
    os.makedirs(backup_dir, exist_ok=True)
    path = os.path.join(
        backup_dir, 'low_est_asins_{mode}_{ts}.txt'.format(
            mode='applied' if apply_mode else 'dryrun', ts=timestamp)
    )
    with open(path, 'w') as fh:
        for asin in asins:
            fh.write('{}\n'.format(asin))
    return path


# --------------------------------------------------------------------------
# Main cleanup
# --------------------------------------------------------------------------

def run_cleanup(db_path, backup_dir, apply_mode):
    """
    Backs up, checks the invariant, reports, and (only with apply_mode) deletes.
    Returns the number of rows deleted (0 on a dry run).
    Raises CleanupAbort on any failed check, having deleted nothing.
    """
    if not os.path.exists(db_path):
        raise CleanupAbort("Database file not found at '{}'.".format(db_path))

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
            raise CleanupAbort(
                "{n} row(s) are marked '{marker}' but have no 1yr_Avg.\n"
                "The marker was only ever written on the branch where the listing-"
                "average fallback had just produced a value, so this combination "
                "means the marker is no longer tracking that value and the delete "
                "predicate cannot be trusted. Nothing has been deleted. Investigate "
                "those rows before running this script again:\n"
                "    SELECT ASIN, source, \"List_at\" FROM deals "
                "WHERE \"Deal_Trust\" = '{marker}' AND \"1yr_Avg\" IS NULL;"
                .format(n=offenders, marker=LOW_EST_MARKER)
            )
        print("  0 rows marked '{}' with a NULL 1yr_Avg - OK".format(LOW_EST_MARKER))
        print()

        print("=" * 70)
        print("BEFORE")
        print("=" * 70)
        print_counts(conn, "Counts by source")

        asins = select_target_asins(conn)
        visible = count_visible(conn)
        asin_path = write_asin_list(asins, backup_dir, timestamp, apply_mode)
        print("  Target rows matching the cleanup predicate: {:,}".format(len(asins)))
        print("  Predicate: {}".format(CLEANUP_PREDICATE))
        print("  Of those, currently visible on the dashboard: {:,}".format(visible))
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
            print("  No rows match the cleanup predicate. Database untouched.")
            print()
        else:
            print("=" * 70)
            print("APPLYING DELETE (single transaction)")
            print("=" * 70)
            try:
                conn.execute('BEGIN IMMEDIATE')
                cursor = conn.execute(
                    'DELETE FROM {table} WHERE {pred}'
                    .format(table=TABLE_NAME, pred=CLEANUP_PREDICATE)
                )
                deleted = cursor.rowcount
                conn.execute('COMMIT')
            except Exception as exc:
                conn.execute('ROLLBACK')
                raise CleanupAbort(
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
        description="Delete the deals rows whose 1yr_Avg came from the removed "
                    "Keepa listing-average fallback, so the Smart Ingestor can "
                    "re-acquire them via the heavy path. Dry run by default."
    )
    parser.add_argument(
        '--apply', action='store_true',
        help='Actually delete the matching rows. Without this the script only reports.'
    )
    args = parser.parse_args(argv)

    db_path = os.getenv('DATABASE_URL', os.path.join(REPO_ROOT, 'deals.db'))

    try:
        preflight()
        run_cleanup(db_path, DEFAULT_BACKUP_DIR, args.apply)
    except CleanupAbort as exc:
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
