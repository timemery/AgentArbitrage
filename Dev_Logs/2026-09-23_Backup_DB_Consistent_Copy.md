# Dev Log Entry: backup_db.sh — A Consistent, Verified Backup of the Live WAL Database (#146)

**STATUS BLOCK**
- **Shipped:** PR **#362**, merged as **`ba659fe`** on 2026-09-23. Deployed by `git pull` only, with no restart, while the v4 repair sweep kept running. Trello **#146** is closed.
- **What changed:** `./backup_db.sh` now copies `deals.db` read-only through SQLite's backup API and checks the copy: `integrity_check` must be ok, and `deals` and `system_state` must have rows. A failed backup exits non-zero and leaves nothing in `db_backups/`.
- **First live run:** `db_backups/deals.db.20260923145603.bak`, 12M, integrity_check ok, 5,206 deals, 5 system_state rows. All `deals.db*` files stayed owned by www-data.
- **Also fixed:** the v4 dev log §6 said ~1,870 rows/day was "slower" than the estimate. It is faster, and about 3× v3's rate, not 2×.
- **Open:** Trello **#154** (`restore_db.sh`). Stale comments in `repair_pricing.py` and `cleanup_low_est_rows.py`. The live row-count check in `repair_pricing.py`'s own backup (§7).

**Date:** September 23, 2026
**Files:** see §8
**Status:** SHIPPED and live.

---

## 1. Task Overview

Trello #146: `backup_db.sh` was `cp "$DB_FILE" "$BACKUP_FILE"`. `deals.db` runs in WAL mode (`keepa_deals/db_utils.py:26` sets `journal_mode=WAL`), so committed transactions not yet checkpointed live in `deals.db-wal`, and a copy of the main file alone is short. The brief asked for the smallest fix: a consistent copy of a live database, plus a check that the backup is complete. It had to be deployable by `git pull` alone, with no restart, because the repair sweep is running.

The owner added three constraints mid-task, before the first report:
1. The live database is opened **read-only**. The box runs the script as root against a www-data database.
2. There is **no exact row-count match against the live database**, because the sweep writes during the copy. The check is `integrity_check` plus the expected tables being present and non-empty.
3. The backup is written to a **temp name and renamed only after the check passes**. A failure exits non-zero and leaves no file that looks like a good backup.

Same PR: a one-line correction to `Dev_Logs/2026-09-23_Pricing_Logic_Version_4.md` §6.

## 2. Premises That Turned Out Wrong

**None in the brief.** Two figures were checked rather than taken on trust:
- **"~1,870 rows/day is slower than 900–1,200."** It is faster: 78 rows/hour × 24 = 1,872.
- **"About 2× v3's rate."** The 2026-09-22 log's status block gives 5,159 rows in about 8 days, which is ~645/day. 1,870 / 645 = 2.9, so the log now says about 3×.

**The Trello card's suggested fix did not survive.** It proposed `sqlite3 deals.db ".backup …"` plus a row-count check. The row-count check was ruled out by constraint 2. The `sqlite3` CLI is not installed in the sandbox (`which sqlite3` returned nothing), and I did not confirm it on the box. `python3` and its standard `sqlite3` module are on the box, because the live run used them.

## 3. Hypotheses Raised and Discarded

- **"Verify the backup by row count against the live DB"** (the card, and the pattern in both existing private backups). Killed by measurement. In the sandbox, three backups taken a few seconds apart during a www-data writer held 57,044, 65,104 and 75,372 rows. A live count moves between the copy and the comparison. The check now reads only the backup.
- **"A read-only connection creates nothing next to the live DB."** Wrong in one case. With the app stopped (no `-wal`/`-shm` present), a root `mode=ro` connection created an empty `deals.db-wal` and `deals.db-shm` and left them after closing. SQLite gave them to the database owner (www-data), and www-data wrote normally afterwards. With the app running, those files already exist. On the live box, all `deals.db*` files stayed www-data-owned. Don't re-investigate this as a permissions bug.
- **"Use `mktemp` for the temp file."** Dropped before the PR. `mktemp` creates the file mode 0600, where `cp` gave backups 0644 (umask). The temp name is now `db_backups/.incomplete.<pid>.<timestamp>`, created by SQLite, so backups keep the old permissions. The name is hidden and does not contain `deals.db`, so `restore_db.sh`'s `grep` never sees it.
- **Adding `user_credentials` to the expected tables.** Owner decision after the first report: no. `deals` and `system_state` prove the copy is complete, and if `user_credentials` were ever legitimately empty, every backup would fail.

## 4. Root Cause

`backup_db.sh:8` (old) copied only the main database file, so any committed pages still in `deals.db-wal` were silently missing. It also had no error handling: it printed `Database backed up to …` and exited 0 even when `cp` failed, for example when the database file was missing.

## 5. The Fix, With Measured Before/After

`backup_db.sh`, still a bash script, now runs an inline `python3` step (stdlib only):
- **Copy:** `sqlite3.connect('file:…?mode=ro', uri=True).backup(dst)`. The default `pages=-1` copies everything in one step inside one read transaction, so the copy is one consistent snapshot. In WAL mode that read does not block writers.
- **Check:** the backup is opened with `immutable=1`, which reads only the main file, so a pass proves the `.bak` alone is complete. `PRAGMA integrity_check` must return `ok`, and each name in `EXPECTED_TABLES="deals system_state"` must exist and have rows.
- **Commit:** `mv` to `db_backups/deals.db.<YYYYmmddHHMMSS>.bak` only after the check passes. A trap removes the temp file and its `-journal` on any exit, and on INT/TERM/HUP.

| | old `cp` | new |
| :--- | :--- | :--- |
| a commit only in `-wal` (`tests/test_backup_db.py`) | 5 of 8 rows backed up | 8 of 8 |
| database missing | exit 0, "Database backed up" | exit 1, nothing written |
| corrupt, empty or missing table | backed up anyway | exit 1, nothing written |
| new test file | 5 of 7 cases fail | 7 of 7 pass |

- The read-only case fails if the connection is switched to `mode=rw`, because a read-write connection closing last checkpoints the WAL and deletes it.
- Full suite: **438 → 445 passed**.
- Sandbox load test, run as root against a www-data database: 3 backups during 83,096 www-data commits. The writer saw no errors, every backup passed the check, and no root-owned files appeared.
- Docs updated in the same PR: `AGENTS.md` §5.3, `System_State.md` and `System_Architecture.md` §3.E, which had described `backup_db.sh` as a plain `cp`.

## 6. Deployment Result

- PR #362 merged as `ba659fe` and was deployed with `git pull` only. No service loads `backup_db.sh`, so no restart was needed, and the running sweep was unaffected.
- `./backup_db.sh` on the box produced `db_backups/deals.db.20260923145603.bak`: 12M, integrity_check ok, deals 5,206 rows, system_state 5 rows.
- Afterwards every `deals.db*` file was owned by www-data, with an empty `deals.db-wal`.
- Trello #146 is closed. The `restore_db.sh` findings are filed as Trello #154.

## 7. Infrastructure Findings and Open Items

1. **Trello #154: `restore_db.sh` does not restore "the most recent backup".**
   - It restores the name that sorts last among those containing `deals.db` (`restore_db.sh:5`, `ls -1 | grep | tail -n 1`). `deals.db.low-est-*` (`cleanup_low_est_rows.py:266-268`) and `deals.db.pricing-repair-*` (`repair_pricing.py:538-540`) both sort after `deals.db.2026…`, so either one wins over every timestamped backup. `AGENTS.md` §5.3's "Restores from the most recent backup" is therefore wrong whenever such a file exists.
   - It also `cp`s over `deals.db` (`restore_db.sh:12`) and leaves any existing `deals.db-wal`/`-shm` beside the restored file.
2. **`repair_pricing.py`'s own backup compares against a live count while Celery runs.** Its preflight says Celery need not be stopped (`repair_pricing.py:494`). Yet `backup_database` compares a live `COUNT(*)` taken *after* the copy with the backup's count (`repair_pricing.py:558-563`). An ingestor insert or a Janitor delete in between aborts the launch. The abort happens before any write, so it is safe but spurious. The source connection is also read-write (`repair_pricing.py:547`). It is fine today because the sweep runs as www-data. Not changed; owner decision.
3. **Stale comments.** `repair_pricing.py:93-94` and `:532-535`, and `cleanup_low_est_rows.py:248-251`, still say `backup_db.sh` is a plain `cp`. I left them alone rather than edit `repair_pricing.py` mid-sweep; the comments are wrong but harmless.
4. **Carried forward:** Trello #153 (ai_rejected rows vs their 1-year median, after the sweep), the skip backlog re-sorting to the top of each run, #143, #145, #151.

## 8. Files Modified

| PR | files |
| :--- | :--- |
| #362 | `backup_db.sh` (rewritten), `tests/test_backup_db.py` (new, 7 cases), `AGENTS.md` §5.3, `Documentation/System_State.md`, `Documentation/System_Architecture.md` §3.E, `Dev_Logs/2026-09-23_Pricing_Logic_Version_4.md` §6 |
| this PR | this log |
