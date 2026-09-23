# Dev Log Entry: Pricing Logic Version 4 — Why v3 Hid Books, and Pricing Them Again

**STATUS BLOCK**
- **Shipped:** PR **#360**, merged as **`3ff10ae`**, deployed via backup + `git pull` + `deploy_update.sh` on 2026-09-23 at about 01:57 UTC. `PRICING_LOGIC_VERSION` is 4. Measurement tooling came first, in PRs #357, #358 and #359.
- **What changed for subscribers:**
  - The peak season is now the best-supported ±1-month window, not the single highest month.
  - `List at` is capped at 2× the book's 1-year median sale price.
  - The AI check is skipped when the price is at or below 1.25× that median.
  - Every hidden price records why in the sweep log.
  - Thin rows are re-checked on each sweep (#152).
- **SWEEP STILL RUNNING.** At 14:19 UTC: 950 of 5,202 attempted, 879 repaired, 71 skipped. Withheld so far: 68 AI rejected, 61 thin. About 78 rows/hour, so completion is expected around Sep 25–26. Output goes to `Diagnostics/repair_pricing.out`.
- **Open:** Trello **#153** (check ai_rejected rows against their 1-year median once the sweep ends). **Next task:** Trello **#146**.

**Date:** September 23, 2026
**Files:** see §9
**Status:** SHIPPED and live. The re-sweep is in progress.

---

## 1. Task Overview

Version 3 (2026-09-22, see that day's log) hid more books than expected. This session measured why, then built and shipped version 4.

| step | what | PR |
| :--- | :--- | :--- |
| 1 | Separate thin-season hides from AI "No" hides. The pricing path recorded no reason. | #357 `--hidden-v3` |
| 2 | Classify the thin rows: steady seller, lone spike, or genuinely thin. | #358 sale counts per season |
| 3 | Measure the proposed v4 rules on the hidden rows before building them. | #359 v4 candidate columns |
| 4 | Build v4. | #360 |

## 2. Premises That Turned Out Wrong

**(a) "9652204986 was hidden by the thin-season rule."** It was an **AI "No"**. The version stamp was 3, not NULL, which ruled out the fail-closed path. The audit found 6 price points in its peak ±1 window, so it was not thin. Recomputed with the AI stubbed, it priced at $24.82 against a stored 1-year average of $148.60. My two proposed thin-season mechanisms (steady seller, lone spike) did not apply to this row.

**(b) "A new column would need a manual schema migration."** Wrong. I said this, and the owner repeated it back. `create_deals_table_if_not_exists` adds any new `headers.json` column automatically on the next ingestor cycle (`db_utils.py:238`).

**(c) The audit's tie-break (earliest month) was not usable in production.** Where one month's sales fill three overlapping windows, the tie-break reported the peak one month early: an all-May book showed "Apr". That breaks the guarded `test_stable_calculations.py`. v4 adds one step before "earliest month": more distinct price points in the centre month itself. The owner confirmed it.

## 3. Hypotheses Raised and Discarded

- **"The AI check rejects prices far *above* the average."** Killed by the data. It rejected prices at the book's own 1-year average: 1936164116 at $398.99 vs $398.99, and 1942707754 at $415.79 vs $402.83. The prompt (`stable_calculations.py:293`) is given the 3-year mean, rank and title, never the book's own sale prices or 1-year figures. It answers in 10 tokens, so its reason cannot be recovered.
- **"Separate thin from AI-No using the xAI cache for free."** Killed. The cache split came out 1 AI No to 59 thin, which is useless. Every process holds its own copy of the cache and rewrites the whole file on save (`xai_cache.py:29–33`), so entries get overwritten.
- **"Recover the reason from the sweep log."** Killed. `setup_logging` turns the pricing modules' logging down to warnings (`repair_pricing.py:879`). The launch sent stdout and stderr to `/dev/null`, so even the warnings were lost.
- **"Choosing the window with the highest median solves inflation."** Killed by the v4 candidate: 15 of 61 priced rows came out above 2× their 1-year median, the worst 5–20× (1586404431 at $284.52 vs $13.89), all on 2–3-point windows. It is still a maximum over thin estimates. That led to the median cap.

## 4. Root Cause

Two separate mechanisms hid books under v3. The `--hidden-v3` split of 60 rows:

| cause | rows | detail |
| :--- | :--- | :--- |
| thin season | 31 | **27 lone spikes** (e.g. 142249151X: 23 sales, 1 in its "season"), 4 steady sellers, 0 genuinely thin |
| AI "No" | 28 | 20 of them priced above `Price_Now`, so they would have been deals |
| other | 1 | 157747015X, inferred to be over $1,500 |

A **lone spike** is a single high sale that wins the highest-single-month vote. That month's ±1 season then holds one price point, so the book is hidden even with many sales elsewhere.

## 5. The Fix, With Measured Before/After

The v4 candidate, run on the 63 hidden rows: **61 priced, 2 unpriced.** Thin rows 33 of 34 priced; AI No rows 28 of 28 priced. The AI check would be skipped for 40 rows under the 1-year mean and 35 under the median. The owner chose the median, because a mean is inflated by the same lone spikes.

Median-cap re-score on the 61 priced rows (zero tokens, from the detail file); 26 are still AI-checked at every k:

| k | capped | above `Price_Now` |
| :--- | :--- | :--- |
| 1.5 | 22 | 44 |
| **2 (chosen)** | **15** | **46** |
| 3 | 11 | 48 |

**What v4 does** (`stable_calculations.py`, named constants):
- **Peak window:** of the twelve ±1-month windows pooled across years, those with at least 2 distinct points are eligible, and the highest median wins. Ties go to more points, then more points in the centre month, then the earlier month. No eligible window: hidden. (`_best_peak_window`)
- **Caps, in order:** branch price → New cap → `PEAK_MEDIAN_CAP_RATIO` 2.0 × 1-year median (no median, no cap) → Amazon ceiling → $1,500.
- **AI skip:** skipped when List at ≤ `AI_SKIP_MEDIAN_RATIO` 1.25 × the 1-year median. **This overrides the 3×-of-current-used rule** (owner confirmed). Above it the check runs and fails closed.
- **Reasons:** `withheld_reason` is one of thin / ai_rejected / unverifiable / over_1500 / no_sales. `repair_pricing.py` logs `| withheld: …` for each row, reading the cached analysis and never recomputing it. No database column.
- **#152:** thin rows are written with a NULL version, so each sweep re-checks them (sorted last, about 7 Keepa tokens each, no xAI call).
- **Audit:** the `v4_*` columns now read production's analysis. The audit's own copy of the rules is deleted.

**Tests:** 419 → **438 passed**. `tests/test_pricing_v4.py` (16) and `TheWithheldReasonIsLogged` (4) are new; 20 cases fail on the parent. Seven existing tests changed:
- Five checked v3 behaviour that v4 replaces.
- Two used sales from the last year, which the median skip now pre-empts, so their sale dates moved back beyond a year.

The guarded pricing tests are unchanged.

## 6. Deployment Result

- Deployed `3ff10ae` on 2026-09-23 at about 01:57 UTC (backup, `git pull`, `deploy_update.sh`). The v3 sweep had been paused at 22:22 UTC on 2026-09-22, about 23 minutes after it started.
- The sweep was relaunched with output to `Diagnostics/repair_pricing.out`. The script's own log stays in `repair_pricing.log`; writing both to one file would duplicate every line.
- At 14:19 UTC: 950 of 5,202 attempted, 879 repaired, 71 skipped; withheld 68 ai_rejected, 61 thin; about 78 rows/hour.
- That rate is faster than my 900–1,200 rows/day estimate. At about 1,870 rows/day it is about 3× v3's rate (about 650 rows/day: 5,159 rows in about 8 days), and it finishes around Sep 25–26.

## 7. Infrastructure Findings

- **The sweep's log never records the pricing reason unless the code puts it there.** `repair_pricing.py:879` sets the `keepa_deals` logger to WARNING. A `nohup … > /dev/null 2>&1` launch then loses even the warnings. Hence the `withheld:` field, and hence launching with output to `Diagnostics/repair_pricing.out`.
- **`xai_cache.json` is not reliable across processes.** Each process loads the file once and rewrites the whole file on every save (`xai_cache.py:29–33`). The workers and the sweep overwrite each other's entries.
- **New `headers.json` columns need no migration.** `create_deals_table_if_not_exists` runs `ALTER TABLE ... ADD COLUMN` for each missing header (`db_utils.py:238`). It still needs `deploy_update.sh` if the workers write the column.
- **The AI prompt never sees the book's own sale prices** (`stable_calculations.py:293–349`). That is why v4 skips the check where the price is backed by the book's own 1-year median, instead of changing the prompt.

## 8. Open Items

1. **Trello #153:** once the sweep ends, check the ai_rejected rows against their 1-year median. Example: 0857457217, with 40 sales, is hidden by the AI. The 26 rows still AI-checked at every k are the pool to look at.
2. **Next task:** Trello **#146** (`backup_db.sh` is a plain `cp` of a WAL database).
3. Carried forward: the skip backlog re-sorts to the top of each run (§7.1 of the prior logs); #143 (racy xAI counter); #145 (Keepa key rotation); #151 (main-grid flag and stale-rescue age).

## 9. Files Modified

| PR | files |
| :--- | :--- |
| #357 | `audit_list_at_sources.py` (`--hidden-v3`, WITHHELD SPLIT), tests, `System_State.md` |
| #358 | `audit_list_at_sources.py` (season sale counts), tests, `System_State.md` |
| #359 | `audit_list_at_sources.py` (v4 candidate columns), tests, `System_State.md` |
| #360 | `keepa_deals/stable_calculations.py`, `keepa_deals/processing.py`, `keepa_deals/pricing_version.py`, `repair_pricing.py`, `audit_list_at_sources.py`, `tests/test_pricing_v4.py` (new), updated `test_thin_peak_season`, `test_xai_fail_closed`, `test_1yr_avg_no_fallback`, `test_pricing_logic_version`, `test_repair_pricing`, `test_audit_list_at_sources`; `AGENTS.md` §7.15 note and new §7.16; `INFERRED_PRICE_LOGIC.md`, `Data_Logic.md`, `System_State.md`, `System_Architecture.md` |
| this PR | this log; `System_State.md` corrected to say v4 is live, and the v3 pause date corrected from 2026-09-23 to 2026-09-22 |
