# Dev Log Entry: Q2 — Recovery Script for the A-7 Damaged Rows

**STATUS BLOCK**
- **Shipped:** `recover_damaged_deals.py` — the one-time recovery that deletes the A-7 damaged rows so the heavy path can re-acquire them. Plus one temp-DB test file and a `System_Architecture.md` §3.E note.
- **Live:** PR #334 merged, main fast-forwarded `b71423b → bdf04b2`, run on the box 2026-09-11 16:08 UTC, `deploy_update.sh` 16:09 UTC. Pull only — the script is not imported by the app.
- **Ran:** 1,543 rows deleted in one transaction. `1yr_Avg IS NULL` is now **0 on every source**. Backup and target ASIN list saved in `db_backups/`.
- **User-visible:** Nothing lost. Dashboard 888 deals against 891 on 09-10; these rows were already excluded by `/api/deals`.
- **Verified:** 18:04 UTC — 7 of the 1,543 deleted ASINs already re-acquired, newest row 4 min old, oldest 45.2h.
- **Gate correction:** the brief's "nothing in any web route writes to the deals table" is wrong. `POST /api/run-janitor` deletes in the Apache process, gated on `logged_in` and not on admin.
- **Next decision (owner, 09-11):** remove the `avg365` fallback (audit B-6). That retires `1yr_Avg IS NULL` as a damage fingerprint and invalidates §3.E's predicate rationale.
- **Still open:** single-sale pricing (400 rows with `1yr_Avg = List_at` exactly), 893 blank-**Ago** rows, 1,671 non-damaged `List_at`-NULL rows.

**Date:** September 11, 2026
**Files:** `recover_damaged_deals.py` (new), `tests/test_recover_damaged_deals.py` (new), `Documentation/System_Architecture.md`
**Status:** SUCCESS — MERGED TO MAIN (PR #334), RUN ON THE BOX, VERIFIED AT +2h

---

## 1. Task Overview

Q2 from the 09-10 session, deferred there as a separate PR. The design was already settled in `2026-09-10_Fix_Stale_Rescue_Sentinel_And_Cutoff_Format.md` §3.1, §3.4, §7 and §8; this session only had to build it, and to re-confirm the three code facts the plan rests on before writing anything.

Three steps: a read-only gate, the script and its tests, and a numbered run procedure in the PR description for Tim to follow on the AA box. The script was not run by this session — Tim ran it.

**Carried forward from PR #332 (measured 09-11 ~14:53 UTC, before this run):**

| metric | result |
|---|---|
| Overnight Janitor loss | **0** of the 687 at-risk listed deals deleted |
| Rescue backlog | 0 rows at 48-60h, 0 at 60-72h, 0 past 72h, oldest 48.0h |
| `lpc_dash` | 1,948 → 1,944 — passive recovery under way, no new blanks |

Both PR #332 fixes are confirmed correct at 24 hours. The backlog is fully cleared and nothing was lost to the Janitor.

---

## 2. Premises That Turned Out Wrong

**(a) "Nothing in `wsgi_handler.py` or any web route writes to the deals table, so Apache can stay up during the run."** — the brief's third gate item. Wrong. `POST /api/run-janitor` (`wsgi_handler.py:2673`) calls `_clean_stale_deals_logic(grace_period_hours=72)` **synchronously in the Apache process** (`:2679`), which runs `DELETE FROM deals` and, above 1,000 rows, a `VACUUM` (`janitor.py:25`, `:30-33`). It is gated on `session.get('logged_in')` only (`:2675`), not on the admin role, and `grep` over `templates/` and `static/` finds no caller, so no button reaches it.

The conclusion still held: Apache stayed up. Nobody hits an endpoint with no UI by accident, and the only other deals-table write from Apache is `create_deals_table_if_not_exists()` on the first request after a restart (`wsgi_handler.py:2961`), which is idempotent DDL and never touches row data. Recorded because the premise itself was false, not because the decision changed.

**(b) "`lpc_dash` 1,948 → 1,944 is passive recovery under way."** — mine, in the PR #332 closing measurement. True as far as it went, but the scale was wrong. Post-run `lpc_dash` is **1,464**, so roughly 480 of the 1,543 deleted rows were carrying the blank **Ago**. The delete removed about 120× more blank-**Ago** rows than a day of passive recovery did. Passive recovery is real and it is slow; 893 dashboard-eligible rows still carry it.

Gate items one and two were unchanged and re-verified: `existing_asins_set` is still rebuilt from a live `SELECT` every run and the Zombie heavy re-fetch is still commented out (`smart_ingestor.py:443-474`), and `/api/deals` and `/api/deal-count` still append `"1yr_Avg" IS NOT NULL` on every branch (`wsgi_handler.py:2239`, `:2257`, `:2796`).

---

## 3. Hypotheses Raised and Discarded

**3.1 "Use `backup_db.sh` for the backup."** REJECTED before writing it, per the brief. It is a plain `cp` of a WAL-mode database (`backup_db.sh:8`), and after `kill_everything_force.sh` committed pages can still be sitting in `deals.db-wal` that a copy of `deals.db` alone would not capture. The script uses SQLite's own backup API, which reads through the WAL into one self-contained file, and verifies the result by row count.

**3.2 "Skip the backup on a dry run to avoid writing a full DB copy every time."** REJECTED. It would make the `--apply` run the first time the backup path was ever exercised — on the one run where a backup failure matters. The dry run is a faithful rehearsal instead. Cost: one 11.46 MB file per dry run, in a directory already gitignored.

**3.3 "Make the predicate handle a NULL `source`."** REJECTED. `source != 'smart_ingestor'` evaluates to NULL, not true, for a NULL source, so those rows are never selected. That is the conservative direction and the brief specified the predicate exactly. Documented in the script and pinned by a test row rather than silently changed.

**3.4 "Add a `--force` flag for the case where a stale Redis lock survives."** REJECTED — the brief excluded it, and the failure mode has a one-line answer instead. The lock lives in Redis db 0 (`celery_config.py:6`, `broker_url = 'redis://127.0.0.1:6379/0'`), so `redis-cli -h 127.0.0.1 -n 0 DEL smart_ingestor_lock` clears it. The preflight prints that command in its abort message.

**3.5 "Restart with `./start_celery.sh`."** REJECTED in favour of `./deploy_update.sh`, from reading both. `start_celery.sh` exits 1 without starting anything if any `monitor_and_restart` process survived the stop (`start_celery.sh:105-112`). `deploy_update.sh` re-runs `kill_everything_force.sh` first so a survivor cannot block it, runs `Diagnostics/force_clear_locks.py` as a lock safety net, runs `Diagnostics/force_pause.py` to force Recharge Mode — which matters here specifically, because the token bucket lives in the Redis that the stop step just wiped — and re-runs `chown -R www-data:www-data`. It does not pull.

---

## 4. Root Cause

Not a new defect. The rows were damaged by A-7 (PR #330, dev log 2026-09-09): the light-update upsert read 215 of 246 columns by `headers.json` display name off a row keyed by sanitized DB column names and wrote them as NULL on every 5-minute cycle, `1yr_Avg` and `List_at` among them.

What this session had to act on is why they could not be healed in place, established in the 09-10 log §3.1 and re-verified here. While a row exists the ingestor always routes its ASIN to the light path: `existing_asins_set` is rebuilt from a live `SELECT` every run and the Zombie Data Defense heavy re-fetch is commented out, so `is_zombie` is always `False` (`smart_ingestor.py:465-471`). Stale Rescue is light-only. The recalculator is API-free and cannot rebuild `List_at`, which derives from `infer_sale_events` and needs the Keepa `csv` history that `deals.db` never stores.

Deleting is therefore not the cheaper repair, it is the only mechanism that returns the ASIN to the heavy path.

---

## 5. The Fix (PR #334)

`recover_damaged_deals.py` at repo root, following the `run_deals_migration.py` convention. Dry run by default, `--apply` to delete, no `--force`.

| Guard | Behaviour |
|---|---|
| Preflight | Aborts if Celery or `monitor_and_restart` is running, if `smart_ingestor_lock` is held, or if not running as `www-data` |
| Backup | SQLite backup API into `db_backups/`, verified by row count, path printed; abort on any failure |
| Invariant | `COUNT(*) WHERE "1yr_Avg" IS NULL AND "List_at" IS NOT NULL` must be 0 |
| Predicate | `"1yr_Avg" IS NULL AND "List_at" IS NULL AND source != 'smart_ingestor'` |
| Transaction | One `BEGIN IMMEDIATE` … `COMMIT`, rollback on error, no `VACUUM` |
| Scope | `deals` only — `user_restrictions`, `prime_picks`, `confirmed_buys` and the watermark untouched, no rewind |
| Output | Counts by source before and after; target ASIN list to a timestamped file; closing `ls -l deals.db*` |

Both files it writes land in `db_backups/`, covered by `.gitignore:28`, so nothing it writes can become tracked.

**Measured on the box, 2026-09-11 16:08:42 UTC** (total / `1yr_Avg` NULL / `List_at` NULL):

| source | before | after |
|---|---|---|
| `smart_ingestor` | — | 140 / 0 / 79 |
| `smart_ingestor_light` | — | 69 / 0 / 35 |
| `stale_rescue` | — | 3,917 / 0 / 1,557 |
| **ALL** | 5,669 rows, 1,543 damaged | **4,126 / 0 / 1,671** |

Backup verified at 5,669 rows before the delete. 1,543 rows deleted, exactly the dry-run target count.

**Tests.** `tests/test_recover_damaged_deals.py`, 4 tests against a temp DB: the predicate selects only the damaged light and rescue rows and leaves the heavy path, the healthy rows and a NULL-source row alone; the invariant raises `RecoveryAbort` and deletes nothing when a damaged row carries a `List_at`; a dry run deletes nothing but still writes the ASIN list; `--apply` deletes exactly the two damaged fixtures. Full suite green except `test_smart_ingestor_batching`, which fails identically on main.

**No code changed after the first "I think this is done."** PR #334 merged as built, and the box run needed no correction to the script.

---

## 6. Deployment Result

PR #334 merged; main fast-forwarded `b71423b → bdf04b2`; pull only, since nothing in the app imports the script.

Preflight: `db_backups/` writable by `www-data`, `deals.db` 11.46 MB owned by `www-data`, 28 GB free.

- **16:08 UTC** — `kill_everything_force.sh`, then the dry run. Preflight all OK, backup verified at 5,669 rows, invariant 0, target 1,543.
- **16:08:42 UTC** — `--apply`. 1,543 rows deleted in one transaction. Backup at `db_backups/deals.db.recovery-20260911-160842.bak`, ASIN list at `db_backups/damaged_asins_applied_20260911-160842.txt`.
- **16:09 UTC** — `deploy_update.sh`, clean.

**Verification at 18:04 UTC, ~2 hours in:**

| metric | reading |
|---|---|
| `1yr_Avg IS NULL` | **0 on every source** (`smart_ingestor` 161, light 71, `stale_rescue` 3,915) |
| Deleted ASINs re-acquired | 7 of 1,543 |
| Newest row | 4 min |
| Oldest row | 45.2h — inside the 48h rescue threshold |
| `lpc_dash` | 1,464, of which 893 carry a `List_at` |
| Dashboard | 888 deals, against 891 on 09-10 |

The dashboard reading is the one that matters: 1,543 rows left the database and three deals left the grid. The `/api/deals` exclusion argument held exactly as predicted from source.

Re-acquisition is passive and depends on Keepa surfacing each ASIN in the deal feed again. 7 in two hours is a rate, not a total; the saved ASIN list is how the eventual return rate gets measured.

---

## 7. Open Items

- **`POST /api/run-janitor` is gated on `logged_in`, not admin,** and runs `DELETE FROM deals` plus a `VACUUM` in the web process. No UI calls it. Noted per §3 scope discipline, not acted on.
- **Owner decision, 09-11: `1yr Avg` and `List at` must come only from inferred sales.** The `stats.avg365` fallback in `get_1yr_avg_sale_price` (`new_analytics.py:34`) is to be removed — audit finding B-6, and the doc contradiction flagged in the 09-10 log §8. Live: **618 'Low (Est.)' rows, 2 of them with a `List_at`.** Consequence for this session's work: once the fallback is gone, `1yr_Avg IS NULL` stops being rare and stops being a safe damage fingerprint. `System_Architecture.md` §3.E says so in the predicate rationale and will need revisiting with that change, not before it.
- **Single-sale pricing.** 400 of 2,457 dashboard-eligible deals have `1yr_Avg = List_at` exactly. ASIN `1429097078`: `1yr_Avg` = `List_at` = 699.11, `Deal_Trust` 33.0, Price Now $28.99, presented as $553 profit. One inferred sale is setting both the average and the list price.
- **Blank `Ago`.** 893 dashboard-eligible rows still carry it. Passive recovery works but is slow — see §2(b).
- **Non-damaged `List_at`-NULL stale rows: 1,671.** Same unrepairable logic, different decision. Not folded into Q2.
- **No boot-time Celery supervision.** Crash-safe, not reboot-safe. Carried from 09-09.
- **Audit Batch 1** unstarted.
- **`backup_db.sh` is a plain `cp` of a WAL-mode database.** Unchanged, and now worked around rather than fixed — the recovery script carries its own backup. Anything else relying on it has the same gap.
- **`test_smart_ingestor_batching`** still fails identically on main (`Peek batch 1 should have 50 ASINs: 15 != 50`). Pre-existing, untouched.

---

## 8. Infrastructure & Environment Findings

Established by reading source or by working in the sandbox this session; none of it was written down.

- **`POST /api/run-janitor` is a synchronous deals-table writer inside Apache.** Route at `wsgi_handler.py:2673`, auth check at `:2675` (`session.get('logged_in')`, no role check), call at `:2679`. It runs `_clean_stale_deals_logic` in-process, which deletes at `janitor.py:25` and VACUUMs above 1,000 rows at `:30-33`. No template or JS references it. This is the only web route that writes to `deals`.
- **`create_deals_table_if_not_exists()` runs from `@app.before_request` on the first request after an Apache restart** (`wsgi_handler.py:2961`) and will `ALTER TABLE deals ADD COLUMN` for any header missing from the schema (`db_utils.py:236-258`). Idempotent DDL, no row data touched — which is what makes leaving Apache up during a deals-table operation safe.
- **`.gitignore:28` is `db_backups/`,** the whole directory, so every artifact the recovery script writes is untracked by construction. `:29` and `:30` are narrower redundant patterns underneath it.
- **`start_celery.sh:105-112` exits 1 without starting anything** if a `monitor_and_restart` process survived. This is why `deploy_update.sh` — which runs `kill_everything_force.sh` first — is the correct restart after a manual stop, and `start_celery.sh` alone is not.
- **The Smart Ingestor lock lives in Redis db 0.** `celery_config.py:6` sets `broker_url = 'redis://127.0.0.1:6379/0'` and `smart_ingestor.py:298` builds its client with `redis.Redis.from_url(celery.conf.broker_url)`, so the key is `smart_ingestor_lock` in db 0 and `redis-cli -h 127.0.0.1 -n 0 DEL smart_ingestor_lock` is the one command that clears it.
- **Agent sandbox: `pip install -r requirements.txt` fails on `blinker`** — "Cannot uninstall blinker 1.7.0, RECORD file not found. Hint: The package was installed by debian." Without the install, 26 of 30 test modules error out at import on missing `celery`, `pandas` or `dotenv`, which looks like a broken branch and is not. `pip install --ignore-installed blinker -r requirements.txt` succeeds and the suite then runs. Worth knowing before diagnosing a "failing" test run in a fresh agent environment.

---

## 9. Files Modified

| File | Change |
|---|---|
| `recover_damaged_deals.py` | **New.** One-time recovery script — preflight, verified backup, invariant, predicate, single-transaction delete, before/after counts, ASIN list, closing `ls -l` |
| `tests/test_recover_damaged_deals.py` | **New.** 4 temp-DB tests: predicate boundaries, invariant abort, dry run deletes nothing, apply deletes exactly the damaged rows |
| `Documentation/System_Architecture.md` | New §3.E — the script, why deleting is the repair, the predicate rationale, the safety envelope |
| `Dev_Logs/2026-09-11_Q2_Recover_A7_Damaged_Rows.md` | **New.** This entry |
