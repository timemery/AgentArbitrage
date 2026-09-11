# Dev Log Entry: Stale Rescue — No-Data Sentinel Overwrite, and the Cutoff Format Mismatch

**STATUS BLOCK**
- **Shipped:** Two Stale Rescue defects. (1) Field functions report failure in-band as the string `-`; the rescue persisted that over good stored values. (2) Both rescue cutoffs compared an isoformat column against a space-separated SQLite timestamp, so rows were skipped for up to a day.
- **Live:** PR #332 merged, main fast-forwarded `d01c42a → d2056d5`, `deploy_update.sh` run 2026-09-10 ~20:11 UTC.
- **User-visible:** The **Ago** column stops going blank on rescued rows, and rank / offers / Drops keep their last good reading instead of blanking. Rescue eligibility is now 48h to the second, so stale deals are refreshed before the Janitor's 72h deletion instead of racing it.
- **Verified:** 25 min post-deploy — 60-72h backlog 1,507 → 1,393, oldest 68.3h, none past 72h. `lpc_dash` flat at 1,948 across ~100 rescues (was growing), `rank_null` 14, `drops_dash` 0.
- **Pending:** Overnight Janitor-loss check. 687 listed deals unseen 48h+ captured to `/root/at_risk_2026-09-10.txt` on the box.
- **Still open:** The 1,543 damaged rows (`1yr_Avg IS NULL`) are untouched — Q2 recovery script is a separate PR, decisions settled (see §7).
- **Also open:** No boot-time Celery supervision. Audit Batch 1 unstarted. `test_smart_ingestor_batching` still fails identically on main.
- **Do not repeat:** Damaged rows cannot heal in place — see §3.1. The rescue pool is not the `stale_rescue` cohort — see §2(c).

**Date:** September 10, 2026
**Files:** `keepa_deals/processing.py`, `keepa_deals/smart_ingestor.py`, `tests/test_lightweight_upsert_preservation.py`, `tests/test_stale_cutoff_format.py` (new), `Documentation/Data_Logic.md`, `Documentation/System_Architecture.md`, `AGENTS.md`
**Status:** SUCCESS — MERGED TO MAIN (PR #332), DEPLOYED, EARLY POST-DEPLOY SIGNAL CORRECT

---

## 1. Task Overview

Follow-up to A-7 (`2026-09-09_Fix_A7_Light_Update_Upsert_Nulling.md`). Two questions, Phase 1 read-only first:

- **Q1:** the dashboard **Ago** column showed the trend arrow but `-` for the time on many rows, first noticed the morning after PR #330 deployed.
- **Q2:** a recovery plan for the 1,543 rows with `1yr_Avg IS NULL`.

Q1 shipped as PR #332 across three rounds. Q2 was answered but deliberately not built — it is a separate PR. A third defect, the cutoff format mismatch, was found by Tim from the Q2 analysis and folded into the same PR on the same night, because rows were converging on the Janitor's 72h deletion.

---

## 2. Premises That Turned Out Wrong

**(a) "Stale Rescue now persists the light path's fresh value instead of discarding it, and if that value is empty it overwrites a good timestamp."** — Tim's Q1 hypothesis. Right about the mechanism and about PR #330's role, wrong about scope: it is not light updates in general, it is Stale Rescue only. `last_price_change` (`stable_deals.py:189`) has two sources, the product's `csv` history and the deal object's `currentSince`. Both light fetches use `history=0`, so there is never a csv. The main Light Update merges the deal object into the product first (`smart_ingestor.py:550`, `product_data.update(deal)`), which supplies `currentSince`. The rescue cannot — its ASINs are precisely the ones the deal feed has stopped returning. So on that path the function has no source at all and returns `-` on **every** call. Live counts split exactly along that line: `smart_ingestor` 249 rows / 0 blank, `smart_ingestor_light` 371 / 0, `stale_rescue` 4985 / **1948**.

**(b) "The delete pays for itself in about nine days on tokens alone."** — mine, in the Q2 Phase 1 answer. Wrong, and Tim caught it. `rescue_stale_deals` takes a fixed `LIMIT 20` per run and reserves 3 tokens per ASIN regardless of pool size (`smart_ingestor.py:225`). Deleting rows redirects those tokens to healthy rows; it does not save them. The justification that survives is the one in §3.1, which does not depend on tokens.

**(c) "Pool 4,986 → 3,777, refresh cycle 21h → 16h."** — my replacement figures for (b). Also wrong, also caught. `rescue_stale_deals` selects rows unseen for 48h+ (`smart_ingestor.py:208`), so the rescue pool is rows past that threshold, not the `stale_rescue` **source** cohort. Both numbers withdrawn. The real pool was measured on the box: 1,554 rows.

**(d) "A stale reading is a few hours old."** — mine, in the first Data_Logic wording. Not true on the rescue path. These rows are ones the feed has stopped returning, and every rescue pass refreshes `last_seen_utc`, so a row the rescue keeps reaching can carry a rank, offer count and **Ago** from its last heavy pass, days old, presented as current. Corrected in the doc.

**(e) "The rescue keeps refreshing `last_seen_utc` so the Janitor never reaps them."** — mine, same paragraph. True only of rows the rescue actually reaches. Before the cutoff fix it missed them and the Janitor deleted them. Corrected.

---

## 3. Hypotheses Raised and Discarded

**3.1 "The damaged rows can be healed in place."** DISPROVEN, and this is the load-bearing finding for Q2. While a row exists, the ingestor always routes it to the light path: `existing_asins_set` is rebuilt from a live `SELECT` every run (`smart_ingestor.py:423`) and the Zombie Data Defense heavy re-fetch is commented out, so `is_zombie` is always `False` (`smart_ingestor.py:441`). Stale Rescue is light-only. The recalculator is API-free and cannot rebuild `1yr_Avg`. **No code path in the system can restore these rows.** Deleting is not the cheaper option, it is the only mechanism that routes the ASIN back to the heavy path.

**3.2 "`Offers_365` is always blank on light fetches, because both use `stats=180` and the function needs `stats.avg365`."** DISPROVEN by measurement, not argument. `o365_dash` is 0 on every cohort, so Keepa does populate `avg365` at a 180-day stats window. The stats window is not a defect; left untouched. Nobody needs to re-open this.

**3.3 "Guard the merge with `if not value`."** REJECTED before writing it. `0`, `0.0` and `'0'` are real readings — `get_offer_count_trend` returns the string `'0'` for a genuine zero offer count, not `-`. A falsiness test would discard those and freeze the stored count at its last non-zero value, a subtler version of the bug being fixed. `_is_no_data` checks the sentinel strings explicitly, and a test asserts `'0'` overwrites.

**3.4 "Deleting the damaged rows would orphan `prime_picks` or break tracking."** DISPROVEN. `prime_picks.asin` declares a foreign key to `deals(ASIN)`, but nothing anywhere enables `PRAGMA foreign_keys`, so it is decorative; the generator does delete-then-insert each run and its Pass 1 already excludes `1yr_Avg IS NULL`. `inventory_ledger` and `confirmed_buys` join with LEFT JOINs and read columns that are already NULL on these rows, and `confirmed_buys` carries its own title and `snapshot_*` financials. Redis holds no ASIN-keyed state. `xai_cache.json` is keyed by title/category/season/price, so a re-acquired ASIN hits the cache. Live overlap: `inventory_ledger` 0, `confirmed_buys` 1, `prime_picks` 0. The Janitor already bulk-deletes from `deals` alone every 4 hours and cleans nothing else, so this is established behaviour.

**3.5 "Wrap the column in `datetime(last_seen_utc)` to fix the cutoff comparison."** REJECTED. It normalises the mismatch instead of fixing it and forces a per-row function call. Build the cutoff in Python with `.isoformat()` instead, which is what `janitor.py` has always done.

---

## 4. Root Cause

**Defect 1 — the sentinel.** Every field function reports "I could not compute this" **in band**, by returning the string `-` (or `''`, `N/A`) under its normal key, rather than by omitting the key. `_merge_db_keyed` wrote that through unconditionally. PR #330 had correctly moved all seven light-path values onto sanitized DB column names, which is what made the rescue start *persisting* them — the unconditional `-` included. Before #330 the sentinel had been discarded along with the genuinely fresh values, which masked it.

**Defect 2 — the cutoff format.** Every `last_seen_utc` writer uses `datetime.now(timezone.utc).isoformat()`, which puts a `T` between date and time. Both selection queries built their cutoff with SQLite's `datetime('now', ...)`, which uses a space. SQLite compares them as TEXT; `T` is `0x54`, space is `0x20`, so any row whose UTC **date** equalled the cutoff's date compared greater and never satisfied the `<`, whatever time it carried. A row therefore became eligible at the first 00:00 UTC after its threshold — **at age 72h minus its last-seen UTC time of day** for the 48-hour rescue. `janitor.py:13` builds its cutoff with `.isoformat()` and so deletes at 72h to the second. The intended 24-hour rescue window was 4 to 24 hours depending on time of day, the 4-hour granularity coming from the Janitor's schedule.

Verified writers: three, all in `smart_ingestor.py` (`:254`, `:560`, `:574`), all identical. `save_deals_to_db` in `db_utils.py:526` could also write the column but has zero callers — dead code.

---

## 5. The Fix (PR #332)

**`processing.py`** — `NO_DATA_SENTINELS` and `_is_no_data()`; `_merge_db_keyed` skips a sentinel instead of writing it. The explicit `Drops` mapping bypasses the merge helper, so it applies the guard itself.

**`smart_ingestor.py`** — both cutoffs built in Python with `.isoformat()` and bound as parameters, at `:176` (sweeper, `-1 hour`) and `:208` (rescue, `-48 hours`). No new imports, no migration, no schema change.

Exposed columns, with live counts the morning of 09-10:

| column | how the sentinel lands | rows affected |
|---|---|---|
| `last_price_change` | stored as the literal `-` | 1948 |
| `Sales_Rank_Current` | `clean_numeric_values` casts `-` to int, fails, stores NULL | 14 |
| `Offers` | stored as the literal `-` | 7 |
| `Offers_180` / `Offers_365` | stored as the literal `-` | 0 / 0 |
| `Drops` | stored as the literal `-` | 0 |

`All_in_Cost` and `Min_Listing_Price` are **not** exposed: always computed floats, no sentinel path, written directly rather than merged.

Cutoff fix, measured at a pretend now of 13:00 UTC:

| row age | selected before | selected after |
|---|---|---|
| 48h | no | no |
| 50h | no | yes |
| 60h | no | yes |
| 62h | yes | yes |

**Trade-off, deliberate and documented:** when a lightweight fetch cannot compute a value the dashboard shows the last good reading rather than a blank. The alternative writes NULL into `Sales_Rank_Current`, which loses the last known value *and* drops the row out of the Max Sales Rank filter entirely.

**Recovery for Q1 is passive.** A blanked row heals the next time the deal feed surfaces it, which routes it through the main Light Update. No repair script needed.

**Tests.** `StaleRescueSentinelTest` in `test_lightweight_upsert_preservation.py` drives `_process_lightweight_update` with the **real** field functions and a bare `fetch_current_stats_batch`-shaped product. The pre-existing cases all patched in fresh values, so they only ever exercised the happy path — that gap is how this shipped. `test_stale_cutoff_format.py` pins the one case that separates the two timestamp formats. All reproduce their defect against the parent commit.

---

## 6. Deployment Result

PR #332 merged; main fast-forwarded `d01c42a → d2056d5`; `deploy_update.sh` run 2026-09-10 ~20:11 UTC.

Pre-deploy, 09-10 (rows unseen 48h+): **1,554** total — 47 at 48-60h, 1,507 at 60-72h, oldest 67.8h, none past 72h. 677 of the 60h+ rows were valid listed deals. The 1,507-row pile at 60-72h is the cutoff defect's shape: rows accumulating past the 48h threshold without being picked up, converging on the deletion deadline.

First reading, ~25 minutes later:

| metric | pre-deploy | +25 min |
|---|---|---|
| rows at 60-72h | 1,507 | **1,393** |
| oldest row | 67.8h | 68.3h |
| rows past 72h | 0 | 0 |
| `lpc_dash` | 1,948 | 1,948 (flat across ~100 rescues) |
| `rank_null` | 14 | 14 |
| `drops_dash` | 0 | 0 |

Both fixes correct. The backlog is draining and the sentinel counters stopped growing under live rescue traffic. Overnight Janitor-loss check pending against `/root/at_risk_2026-09-10.txt` (687 listed deals unseen 48h+).

> **Reading these counts later:** the light path rewrites `source`, so rows migrate between cohorts. A falling `stale_rescue` count is not deletion.

---

## 7. Open Items

- **Q2 recovery script.** Not written. Decisions settled: predicate stays narrow at `"1yr_Avg" IS NULL AND "List_at" IS NULL AND source != 'smart_ingestor'`; **no watermark rewind**; run with services stopped, watchdog killed first. Dry-run by default, `backup_db.sh` first, counts by source before and after, run as `www-data`. Next round must also state what must be writable by `www-data` and give one pre-flight check.
- **1,543 damaged rows (`1yr_Avg IS NULL`)** still NULL on disk. See §3.1 for why nothing heals them in place.
- **Non-damaged `List_at`-NULL stale rows** look unrepairable by the same logic. Separate decision, not folded into Q2.
- **No boot-time Celery supervision.** Crash-safe, not reboot-safe. Carried from the A-7 log.
- **Audit Batch 1** unstarted.
- **`test_smart_ingestor_batching`** still fails identically on main (`Peek batch 1 should have 50 ASINs: 15 != 50`). Pre-existing, untouched.

---

## 8. Infrastructure Findings

Established by reading source this session; none of it was written down.

- **`/api/deals` excludes the damaged rows by its own SQL, not just by luck.** `wsgi_handler.py` appends `"1yr_Avg" IS NOT NULL` on **both** branches, the normal one and Agent's Choice, and neither is user-filterable. `/api/deal-count` carries the identical clause, so the header badge cannot move either. Deleting them removes zero visible deals, provable without a live query.
- **`PRAGMA foreign_keys` is enabled nowhere in the codebase.** `get_db_connection` (`db_utils.py:17`) sets only `busy_timeout` and `journal_mode`. Every declared foreign key in the schema, including `prime_picks.asin → deals(ASIN)`, is inert.
- **`save_deals_to_db` (`db_utils.py:526`) has zero callers.** Dead code. It is the only other thing that could write `last_seen_utc` in a different format, which is what made the format audit conclusive.
- **`datetime('now')` appears at only two comparison sites**, both fixed here. The other occurrences (`db_utils.py:603`, `:604`, `:633`) are `DEFAULT` column values on `confirmed_buys` and `confirmed_buy_units`; they do write space-separated timestamps, but nothing ever compares them against an isoformat value, so they are not affected.
- **`.gitignore` line 22 is `deals.db*`, which does not match `test_deals.db*`.** Two stray WAL files from a test fixture shipped in PR #332 as a result. Pattern added.
- **`Documentation/Data_Logic.md` contradicts the code on `1yr. Avg.`** It says the function requires at least one inferred sale and otherwise returns None. `get_1yr_avg_sale_price` (`new_analytics.py:34`) also has a `stats.avg365` fallback before returning None, which `INFERRED_PRICE_LOGIC.md` does document. That fallback is a listing average, which reads against AGENTS.md §7.1 — though the March 2026 removal was scoped to `stable_calculations.py`, and `Deal Trust` has an explicit "Low (Est.)" state for it. Likely intended. **Owner decision, not fixed.** It is also the reason `1yr_Avg IS NULL` is rare enough to be a safe fingerprint for Q2.
- **`backup_db.sh` is a plain `cp` of a WAL-mode database.** Not a consistent snapshot while the app is live. Fine for the Q2 script, which runs with writers stopped. **Not changed.**

---

## 9. Files Modified

| File | Change |
|---|---|
| `keepa_deals/processing.py` | `NO_DATA_SENTINELS`, `_is_no_data()`; `_merge_db_keyed` skips sentinels; explicit `Drops` write guarded |
| `keepa_deals/smart_ingestor.py` | Both cutoffs (`:176`, `:208`) built in Python with `.isoformat()` and bound |
| `tests/test_lightweight_upsert_preservation.py` | `StaleRescueSentinelTest` driving real field functions; fixture split into `_DealsFixture` |
| `tests/test_stale_cutoff_format.py` | **New.** Pins the timestamp-format comparison at both sites |
| `Documentation/Data_Logic.md` | LIGHTWEIGHT PRESERVATION RULE; sentinel rule in the naming contract; `last_price_change` note |
| `Documentation/System_Architecture.md` | What Stage 0.5 can and cannot compute; eligibility now 48h to the second |
| `AGENTS.md` | §7.12 — the sentinel rule, and the warning against a falsiness rewrite |
| `.gitignore` | `test_deals.db*` (follow-up PR) |
