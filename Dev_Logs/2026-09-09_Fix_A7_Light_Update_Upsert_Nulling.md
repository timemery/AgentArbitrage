# Dev Log Entry: Fix A-7 — Light-Update Upsert Nulling 215 of 246 Deals Columns

**STATUS BLOCK**
- **Shipped:** A-7 fixed. The light-update upsert no longer NULLs 215 columns; Stale Rescue no longer discards fresh values. Plus one regression test and doc updates.
- **Live:** PR #330 merged, main fast-forwarded `c0a0810 → d01c42a`, `deploy_update.sh` run 2026-09-09 20:47 UTC.
- **User-visible:** New light-path rows now write complete, so they stay on the Deals Dashboard instead of silently dropping out. Stale-rescued rows now show live rank, offer counts and all-in cost.
- **Verified:** First post-deploy cycle — light cohort 404 → 406 rows, NULL counts flat at 404. The 2 new rows wrote complete. Correct signal, small sample.
- **Still open:** 1,551 already-damaged rows are still NULL on disk. This stopped the bleeding; it did not heal it. Recovery decision pending tomorrow's overnight re-check.
- **Also open:** No boot-time supervision for Celery (crash-safe, not reboot-safe). Batch 1 of the audit unstarted. `test_smart_ingestor_batching` still fails identically on main.

**Date:** September 9, 2026
**Files:** `keepa_deals/processing.py`, `keepa_deals/db_utils.py`, `keepa_deals/smart_ingestor.py`, `tests/test_lightweight_upsert_preservation.py` (new), `Documentation/Data_Logic.md`, `Documentation/System_Architecture.md`, `Documentation/Feature_Deals_Dashboard.md`, `AGENTS.md`
**Status:** SUCCESS — MERGED TO MAIN (PR #330), DEPLOYED, EARLY POST-DEPLOY SIGNAL CORRECT

---

## 1. Task Overview

Finding A-7 from `Diagnostics/2026-09-09_Calculation_Audit.md` — the two upsert sites in `smart_ingestor.py` key the same row shape through two different namespaces. The audit filed A-7 as CONFIRMED for the code shape but explicitly **not** for its live blast radius, deferring that to question B-1.

Tim settled B-1 with a live query before this session started:

```sql
SELECT source, COUNT(*), SUM(List_at IS NULL),
       SUM("1yr_Avg" IS NULL), SUM(Deal_Trust IS NULL) FROM deals GROUP BY source;

smart_ingestor       |  295 |  159 |    0 |    0
smart_ingestor_light |  404 |  404 |  404 |  404
stale_rescue         | 4859 | 2586 | 1147 | 1147
```

A-7 was live and total on the light path. 404/404. The session ran as Phase 1 (read-only analysis, four questions, STOP) then Phase 2 (implement, PR, do not merge).

---

## 2. Premises That Turned Out Wrong

Recorded because each cost real reasoning time, and two of them were mine.

**(a) "If `:596` were firing, the dashboard would empty."** — my own counter-argument in the audit. Sound reasoning, wrong conclusion. Nulled rows do not empty the grid; they drop out of it silently, because `/api/deals` filters `"List_at" IS NOT NULL` (`wsgi_handler.py:2237`, `:2255`). Absence of a visible symptom was treated as evidence of absence. Killed by the `GROUP BY source` query above.

**(b) "There is no `monitor*` file in the repo root, so the watchdog may not exist and the box may run unsupervised after every deploy."** — from the Phase 1 brief. Wrong. `monitor_and_restart` is a **bash function**, not a file: `start_celery.sh:12`. See §7.

**(c) "SQLite raises `duplicate column name` on a duplicate in an INSERT column list, so the duplicate I claimed cannot have been live."** — raised by Tim as a merge gate. The two contexts behave differently. Measured on SQLite 3.45.1:

```
CREATE TABLE t (a TEXT, b TEXT, a TEXT)              -> ERROR: duplicate column name: a
INSERT INTO deals (..,"last_seen_utc","source",
                      "last_seen_utc","source") ...
  ON CONFLICT(ASIN) DO UPDATE SET ...                -> ACCEPTED (insert and conflict branch)
```

The duplicate was real and live. `headers.json` carries `last_seen_utc` at index 244 and `source` at 245, and both sites then re-appended them (`smart_ingestor.py:267-268` and `:591-592` pre-fix). SQLite tolerated it, last write wins, both copies carried the same value. That is why upserts succeeded and 404 nulled light rows exist. The `duplicate column name` error surfaced only when the new test tried to `CREATE TABLE` from that list — which is how the duplicate was found at all.

**(d) "Recovery is a matter of re-deriving from what is still in `deals.db`."** Wrong, and this is the expensive one. See §4.

---

## 3. Hypotheses Raised and Discarded

Recorded so nobody re-runs them.

1. **"`recalculator.py` / `run_deals_migration.py` can repair the damaged rows."** DISPROVEN, and it is actively harmful. `recalculate_deals` gates on `list_at_price > 0 AND now_price > 0`; every row failing that gate takes the else-branch and has `Profit`, `Margin` and `Total_AMZ_fees` **explicitly written as NULL**. Running it on rows already missing `List_at` destroys what they still hold. It also cannot rebuild `List_at` under any circumstances: that value comes from `get_list_at_price` → `_get_analysis` → `infer_sale_events` (`stable_calculations.py:648`), which consumes the Keepa `csv` history arrays, and that history is never persisted. Worse, the light path also nulled `Price_Now`, `FBA Pick&Pack Fee`, `Referral Fee %`, `Shipping Included`, `Categories - Sub`, `Peak Season` and `Trough Season` — every input the recalculator reads. This is now a warning in `Feature_Deals_Dashboard.md`.

2. **"`List_at IS NULL` identifies the A-7 damage."** DISPROVEN by the live baseline. The heavy path legitimately persists rows with no determinable list price — 159 of 295 (`processing.py:138-141`, "Persisting deal with Missing List at"). The reliable fingerprint is **`1yr_Avg IS NULL`**, because the heavy path wrote `1yr_Avg` on 295 of 295. That reframes the damage from 3,149 rows to **1,551** (404 light + 1,147 stale_rescue), and the other 1,598 would most likely come back NULL again if re-fetched.

3. **"Fix `:596` to match `:272`."** The audit warned against this and was right, but the first implementation pass walked into a variant of it anyway. Switching `:596` to sanitized headers alone breaks the **heavy** path, because `smart_ingestor.run()` appends heavy and light rows to the *same* `rows_to_upsert` list, and heavy rows legitimately use display names (`processing.py:132`). Caught while re-reading my own diff before commit; measured at **221 columns** lost. Fixed with `to_db_keys()` and a test that fails without it.

4. **"Damaged rows will age out via the Janitor."** DISPROVEN. `janitor.py:25` deletes on `last_seen_utc` older than 72h, but `rescue_stale_deals` refreshes `last_seen_utc` every pass. The damaged rows are held alive indefinitely in their broken state.

5. **"The renames might break a downstream reader."** Checked rather than assumed, at Tim's insistence — the PR #323 bug class proves display-name reads exist in this file. Every `.py`, `.html` and `.js` grepped for all seven keys. The only readers of those keys off that dict are the two upsert sites. `prime_picks_task.py:185` reads `Offers`, but off a DB row, and `Offers` sanitizes to itself. Nothing broke.

---

## 4. Root Cause

`_process_lightweight_update` returns a dictionary in **two key namespaces at once**.

It starts as `dict(existing_row)` from `SELECT * FROM deals` (`smart_ingestor.py:455`), so it is keyed by **sanitized** DB column names (`List_at`, `1yr_Avg`). It then merges results from the field functions, which return their values under **display** names from `headers.json` — seven of them: `Sales Rank - Current`, `Offers`, `Offers 180`, `Offers 365`, `last price change`, `All-in Cost`, `Min. Listing Price`.

Neither upsert site could read that row whole:

- **`:596` (main Light Update)** read by display name. Of 246 headers, 221 sanitize to a different string; 6 of those were rewritten under display names, leaving exactly **215** that resolved to `None`. `ON CONFLICT DO UPDATE SET` then bound every one as NULL, every 5-minute cycle — including `List_at`, `Price_Now`, `1yr_Avg`, `Deal_Trust`, `Total_AMZ_fees`, `Peak_Season`, `Trough_Season`.
- **`:272` (Stale Rescue)** read by sanitized name, so the 6 fresh values written under display names were discarded and the **old** rank, offer counts and `All_in_Cost` were written back — alongside a **new** `Profit` and `Margin` computed from the new cost. Stored rows failed their own identity: `Profit ≠ List_at − All_in_Cost − Total_AMZ_fees`.

Same bug class as the six fixed in PR #323 (dev log `2026-08-18b`), which corrected the *reads* inside `_process_lightweight_update` and left both *writes* untouched. And masked the same way: `test_seller_name_logic.py` builds a fixture dict and asserts against it, so it can only confirm the key convention its own author chose.

---

## 5. The Fix (PR #330, commit `9c665b4`)

**`processing.py`** — new `_merge_db_keyed()` routes every field-function result through `sanitize_col_name`, so the light row stays in one namespace. `All-in Cost` and `Min. Listing Price` written as `All_in_Cost` and `Min_Listing_Price`. `Drops` keeps its explicit mapping; it is the DB column carrying the 30-day count, not a sanitization of the function's key.

**`db_utils.py`** — `build_deals_upsert()` and `upsert_deal_rows()` become the single builder for the deals upsert, deriving columns from `headers.json` via `sanitize_col_name`, the same transform `recreate_deals_table()` uses to CREATE the table. Plus `to_db_keys()` for re-keying heavy rows.

**`smart_ingestor.py`** — both sites call the shared helper; heavy rows re-keyed at `:573`, after `clean_numeric_values` (whose coercion rules key off column-name substrings) and before the append.

Measured, before → after:

| | before | after |
|---|---|---|
| columns NULLed per light update | 215 | 0 |
| fresh values discarded per stale rescue | 6 | 0 |
| columns at risk on the heavy path without `to_db_keys` | 221 | 0 |
| upsert column list length (2 duplicates) | 248 | 246 |
| columns dropped by the dedupe | — | none (`set(pre) == set(post)`) |

**Test.** `tests/test_lightweight_upsert_preservation.py`, 8 tests. Takes both contracts from production code — the schema from `headers.json` through `sanitize_col_name`, the SQL from `build_deals_upsert` — so a wrong key convention on either side cannot satisfy it. Against pre-fix code it reproduces the defect exactly: 215 nulled columns on the main path, stale rank on the rescue path, and the 6 offending display-name keys named. This is the specific counter to how PR #323's bug class stayed hidden.

Full suite passes except `test_smart_ingestor_batching`, which fails identically on clean HEAD (confirmed by stashing and re-running).

---

## 6. Deployment Result

PR #330 merged; main fast-forwarded `c0a0810 → d01c42a`; `deploy_update.sh` run 2026-09-09 20:47 UTC. Celery beat and the watchdog had been killed on the box during the investigation, so nothing was nulling and no new deals were arriving; `deploy_update.sh` restarts beat, which lifted the pause.

Pre-deploy baseline and first post-deploy reading (COUNT / `List_at` NULL / `1yr_Avg` NULL / `Deal_Trust` NULL):

| source | pre-deploy | first post-deploy |
|---|---|---|
| `smart_ingestor` | 295 / 159 / 0 / 0 | — |
| `smart_ingestor_light` | 404 / 404 / 404 / 404 | **406** / 404 / 404 / 404 |
| `stale_rescue` | 4859 / 2586 / 1147 / 1147 | fell by exactly 2 |

The light cohort gained 2 rows with NULL counts flat. **The two new light rows wrote complete.** Early but correct. Full confirmation is tomorrow's re-check after an overnight run.

> **Reading these counts later:** the light path rewrites `source`, so rows migrate between cohorts. `stale_rescue` fell by exactly 2 as light gained 2; total conserved at 5,263. **A falling `stale_rescue` count is not deletion.**

---

## 7. Infrastructure Findings (established this session, not previously written down)

Recorded so the next agent does not re-derive them.

- **`monitor_and_restart` is a bash function, not a file.** Defined `start_celery.sh:12`, exported with `export -f` at `:115`, launched detached at `:121` via `nohup bash -c 'monitor_and_restart'`. There is no `monitor*` file and never was — which is exactly why `diagnose_vps_outage.py:174` greps the process table for the string rather than looking for a script.
- **It supervises all three services.** Before entering its loop it starts Redis, purges, and launches worker and beat. It then loops every 60s re-checking all three and restarting whichever died.
- **`deploy_update.sh` re-establishes it.** Step 2 runs `kill_everything_force.sh`, which pkills the old monitor; step 3 runs `start_celery.sh`. So the already-running guard at `start_celery.sh:105` does not block the restart. **The box IS supervised after every deploy.**
- **Nothing starts it at boot.** No systemd unit, no cron entry anywhere in the repo. It survives a crash but not a reboot. Open, not fixed here.

---

## 8. Open Items / Follow-Ups

- **1,551 damaged rows (`1yr_Avg IS NULL`) are still NULL on disk.** This fix stopped the bleeding; it did not heal it. Recovery decision pending tomorrow's confirmation. Likely approach is to **DELETE** the damaged rows rather than re-fetch: deleting removes them from `existing_asins_set`, which lets normal heavy ingestion re-acquire them with no new code. **Caveat:** the ingestor discovers via Keepa's deal-finder, so a deleted ASIN only returns if Keepa still surfaces it as a deal. For reference, a re-fetch would cost ~20 tokens/ASIN — 31,020 tokens for the 1,551, or 62,980 for all 3,149 rows missing `List_at`.
- **The Aug 19 backup is not worth a merge script.** `db_backups/deals.db.20260819003804.bak` predates A-7 and holds intact `1yr_Avg`, but overlap with today's damage measured at **245 rows — 16% of 1,551**. Judged not worth the script. Recorded so nobody re-measures it.
- **No boot-time supervision.** See §7. Its own card.
- **Batch 1 from the audit remains unstarted**, deliberately — kept out so the A-7 diff stayed readable as the only pre-live check.
- **`test_smart_ingestor_batching`** still fails identically on main (`Peek batch 1 should have 50 ASINs: 15 != 50`, a batch-size-vs-refill-rate assertion). Pre-existing, unrelated, untouched.
- **`.gitignore` does not cover `test_deals.db*`** — line 22 matches only `deals.db*`, so stray test artifacts land in the repo root. Noted per §3 scope discipline, not acted on.

---

## 9. Files Modified

| File | Change |
|---|---|
| `keepa_deals/processing.py` | `_merge_db_keyed()`; seven display-name writes normalized to sanitized column names |
| `keepa_deals/db_utils.py` | `build_deals_upsert()`, `upsert_deal_rows()`, `to_db_keys()`; upsert column list deduped |
| `keepa_deals/smart_ingestor.py` | Both upsert sites use the shared helper; heavy rows re-keyed at `:573` |
| `tests/test_lightweight_upsert_preservation.py` | **New.** 8 tests locking the DB-column contract against production code |
| `Documentation/Data_Logic.md` | DB column naming contract; the incident |
| `Documentation/System_Architecture.md` | What Stage 0.5 and Stage 3 now persist; shared upsert; recovery caveat |
| `Documentation/Feature_Deals_Dashboard.md` | Warning: running the recalculator on NULL-`List_at` rows deepens the damage |
| `AGENTS.md` | New §7.12, DB Column Naming Contract |
