#!/bin/bash
# Consistent, verified backup of the live WAL-mode SQLite database (Trello #146).
#
# This used to be a plain `cp`, which misses committed transactions still sitting in
# deals.db-wal and so can produce a backup that is silently short. It now uses SQLite's
# online backup API, which reads through the WAL and copies one consistent snapshot
# while the app and the repair sweep keep writing.
#
# - The live database is opened READ-ONLY (mode=ro). This runs as root against a
#   www-data-owned deals.db; a read-write connection can checkpoint it or leave
#   root-owned -wal/-shm files behind and break the app's write access.
# - The backup is checked on its own, not against the live row counts (those move
#   during the copy): PRAGMA integrity_check must return ok, and every table in
#   EXPECTED_TABLES must exist and have rows.
# - It is written to a hidden temp name and renamed to its timestamped name only after
#   that check passes. On any failure the temp file is removed and the exit is non-zero.
#
# Needs only python3 and its standard sqlite3 module. Nothing to restart.

DB_FILE=${DATABASE_URL:-deals.db}
BACKUP_DIR="db_backups"
TIMESTAMP=$(date +"%Y%m%d%H%M%S")
BACKUP_FILE="$BACKUP_DIR/${DB_FILE##*/}.$TIMESTAMP.bak"
EXPECTED_TABLES="deals system_state"

if [ ! -f "$DB_FILE" ]; then
    echo "ERROR: database '$DB_FILE' not found. No backup written." >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR" || exit 1

# Hidden and without the database name in it, so restore_db.sh (newest name containing
# the database name) can never pick up a half-written file. Created by SQLite, so it gets
# the same permissions `cp` used to give a backup.
TMP_FILE="$BACKUP_DIR/.incomplete.$$.$TIMESTAMP"
trap 'rm -f "$TMP_FILE" "$TMP_FILE-journal"' EXIT
trap 'exit 1' INT TERM HUP

SUMMARY=$(python3 - "$DB_FILE" "$TMP_FILE" $EXPECTED_TABLES <<'PY'
import os
import sqlite3
import sys
from urllib.parse import quote

src_path, tmp_path, expected = sys.argv[1], sys.argv[2], sys.argv[3:]


def uri(path, flag):
    return 'file:{}?{}'.format(quote(os.path.abspath(path)), flag)


def fail(message):
    sys.stderr.write('ERROR: {}\n'.format(message))
    sys.exit(1)


# Copy. Read-only on the live file: no checkpoint, nothing created or rewritten by us.
# backup() with its default pages=-1 copies everything in one step inside one read
# transaction, so the copy is a single consistent snapshot; in WAL mode that read does
# not block the app's writers.
try:
    src = sqlite3.connect(uri(src_path, 'mode=ro'), uri=True, timeout=60)
    try:
        dst = sqlite3.connect(tmp_path)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()
except sqlite3.Error as exc:
    fail('the copy failed: {}'.format(exc))

# Check the backup file alone. immutable=1 reads only the main file (no -wal, no -shm),
# so whatever it finds is in the backup itself.
counts = []
try:
    chk = sqlite3.connect(uri(tmp_path, 'immutable=1'), uri=True)
    try:
        try:
            result = [row[0] for row in chk.execute('PRAGMA integrity_check')]
        except sqlite3.Error as exc:
            result = [str(exc)]
        if result != ['ok']:
            fail('integrity_check on the backup did not return ok: {}'
                 .format('; '.join(result[:5])))
        tables = {row[0] for row in
                  chk.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        for table in expected:
            if table not in tables:
                fail("expected table '{}' is missing from the backup".format(table))
            rows = chk.execute('SELECT COUNT(*) FROM "{}"'.format(table)).fetchone()[0]
            if rows == 0:
                fail("expected table '{}' is empty in the backup".format(table))
            counts.append('{} {:,} rows'.format(table, rows))
    finally:
        chk.close()
except sqlite3.Error as exc:
    fail('could not check the backup: {}'.format(exc))

print('integrity_check ok; ' + ', '.join(counts))
PY
)
if [ $? -ne 0 ]; then
    echo "ERROR: backup of '$DB_FILE' failed. No backup written." >&2
    exit 1
fi

mv "$TMP_FILE" "$BACKUP_FILE" || exit 1

echo "Database backed up to $BACKUP_FILE"
echo "  $(du -h "$BACKUP_FILE" | cut -f1), $SUMMARY"
