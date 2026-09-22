# Dev Log Entry: Pricing Logic Version 3 — the Thin Peak Season, the New Cap, and a Fail-Closed AI Check

**STATUS BLOCK**
- **Shipped:** PR **#355**, merged as **`827025e`**, and deployed with `deploy_update.sh` at about 21:57 UTC on 2026-09-22. `PRICING_LOGIC_VERSION` went from 2 to 3.
- **What changed for subscribers:**
  - `List at` is now estimated over the peak season: the peak month ±1 month, pooled across years.
  - A season with fewer than 2 distinct price points has no price and is hidden.
  - `List at` is capped at the median of the lowest New price in each peak-season window, plus $3.99.
  - An AI check that cannot run now hides the price. It used to pass it.
- **Repair sweep:** started at 21:59 UTC against **5,159 stale rows**, about 8 days at 1000 xAI calls/day. Agent's Choice emptied at deploy and refills as the sweep reprices rows.
- **Closed:** Trello **#144**. **Open:** Trello **#152**, the follow-up gap. The 7-token cost of re-trying the skip backlog each run (§7.1) is still open.

**Date:** September 22, 2026
**Files:** see §9
**Status:** SHIPPED and live. The sweep is in progress.

---

## 1. Task Overview

This is Phase 2 of the 2026-09-22 `List at` audit (`Dev_Logs/2026-09-22_Prime_Picks_Guard_And_The_Thin_Peak_Month.md` §6). Every item ships under **one** version bump, so the ~8-day re-sweep is paid for only once.

| # | item | outcome |
| :--- | :--- | :--- |
| 6 | Sales priced by the same price point count once in the mode | built first |
| 1–3 | Pool the peak season; hide a season that is too thin; choose the minimum from measurement | measured first, then built on the owner's choice |
| 4 | Peak-window New cap | built |
| 5 | Amazon ceiling reads today's price only in the peak month | built; ships only together with 4 |
| 7 | #144: an unverifiable AI check fails closed | built, and widened twice (§2c, §2d) |

## 2. Premises That Turned Out Wrong

**(a) "Pool the peak month across years" as new behaviour.** The code already pooled across years. `analyze_sales_performance` groups sales by `df['event_timestamp'].dt.month`, so every September in the history is already one group. The audit counts peak-month sales the same way (`audit_list_at_sources.py`, `classify_list_at`). That means "41 of 43 median-set rows have ≤3 sales in the peak month, median 1" was **already the pooled count**, and pooling by month could add nothing. I stopped and reported this. The owner then redefined pooling as a **wider window, the peak month ±1**, pooled across years.

**(b) Scope of "pool".** I read pooling as applying to the **price** (the mode/median is taken over the whole season), not only to the sale count. The owner confirmed that reading after the build.

**(c) Missing API key.** The brief scoped #144 to the daily cap and xAI errors. `_query_xai_for_reasonableness` returned `True` on a third path, the missing key. The owner ruled it the same failure, and it now fails closed too.

**(d) Consequence of (c).** A sweep run without `XAI_TOKEN` would write every row it checked as unpriced. `repair_pricing.py` now refuses to start without the key (owner request).

## 3. Hypotheses Raised and Discarded

- **"The Amazon ceiling mainly clips on today's price."** Killed by the random audit: **10 clips, all on trailing averages, 0 on today's price**. The gate in item 5 is correct, but it moves almost nothing.
- **"Shared price points are still an exposure."** Section (a) of the random audit found **0 mode-shared rows** once item 6 was in. The duplicate problem is closed. Do not re-measure it.
- **"The minimum can be applied to the peak month alone."** Killed by section (d): with a minimum of 2, the single month hides **65 of 100** rows and ±1 month hides **28**. A single-month rule would have erased the slow inventory the product exists to find.

## 4. Root Cause

The peak month is chosen by `idxmax` over up to twelve monthly medians, and on the median row that month held **one** sale. `List at` was therefore the highest single sale in three years. The prices themselves were not wrong; the way one of them was selected was. Three smaller defects sat on top of this:
- A price point that priced two sales won the mode as a pair.
- The Amazon ceiling used today's (trough-time) price.
- An AI check that could not run passed the price and stamped the row current.

## 5. The Fix, With Measured Before/After

**Thin-season minimum**, measured on 100 **random** visible rows (650 Keepa tokens). Figures are rows hidden, with sparse rows in brackets:

| minimum | peak month only | **peak month ±1** |
| :--- | :--- | :--- |
| **2** | 65 [7] | **28 [6] ← chosen** |
| 3 | 85 [7] | 53 [7] |
| 4 | 92 [7] | 64 [7] |

The owner applied the rule to Sparse Sales Rescue rows too. A sparse row below the minimum is kept in the database unpriced and never deleted (AGENTS.md §7.8 updated).

**What the code does now** (all in `stable_calculations.py`):
- **Distinct price points.** `infer_sale_events` carries `price_point`, which is (series, timestamp of the matched price point). The mode and median count distinct points. Identity is the point's timestamp, never an equal price.
- **Thin season.** The peak season is `PEAK_SEASON_HALF_WIDTH_MONTHS = 1` month either side of the peak, and December wraps into January. With fewer than `PEAK_SEASON_MIN_PRICE_POINTS = 2` distinct points, the price is withheld. The row is stamped with the current version (a real answer, not a retry) and no AI call is made.
- **New cap.** The cap is the median of the per-window New floors + `PEAK_NEW_CAP_ALLOWANCE_CENTS = 399`. `peak_window_new_floor` moved out of the audit into production, and the audit now calls it. When a row has no New price in its window it stays uncapped, and the analysis records that the cap was unavailable (no database column, owner decision).
- **Amazon ceiling.** It uses `stats.current` only when today's month equals the peak month. Sparse rows never use it.
- **Fail-closed check.** `_query_xai_for_reasonableness` returns `None` for a missing key, the daily cap, or an error. `_process_single_deal` then writes `Pricing_Logic_Version` NULL, read from the cached analysis that produced `List at` (`processing.py:189`). It deliberately does not read the second `analyze_sales_performance` call at line 148, whose check can succeed where the first one failed.

**First writes live:**
- `B008YSVCSE`: $499.71 → **NULL** (hidden).
- `1437707467`: $499.00 → **$276.36**.

**Tests:** 352 → **409 passed**. Four new test files (`test_distinct_price_points`, `test_pricing_v3_caps`, `test_xai_fail_closed`, `test_thin_peak_season`); each behaviour has cases that fail on the parent commit.

Iterations after the first "done":
- 8 audit tests that pinned the pre-fix mode were rewritten to pin the fix.
- One sparse test went from 1 sale to 2.
- The audit test fixture's months changed from 60-day offsets to whole calendar months. On some dates, 60-day offsets fall in adjacent months, which pooling would merge (flaky by date).

## 6. Deployment Result

- Merged `827025e`, deployed with `deploy_update.sh` at about 21:57 UTC. The workers have to restart to load `stable_calculations.py` and `processing.py`; `git pull` alone would leave them pricing with version 2.
- The preview (`--limit 10`) previewed 3 rows and skipped 7. The skips were the skip backlog sorting back to the top, as expected (§7.1).
- The sweep launched at 21:59 UTC against 5,159 stale rows.
- No manual schema or `settings.json` change was needed.

## 7. Infrastructure Findings

- **The analysis cache is never cleared in production.** `_analysis_cache` (`stable_calculations.py:1019`) is only cleared by `clear_analysis_cache` (`:1021`), and only the audit calls that. If a worker prices the same ASIN twice, the second fetch reuses the first analysis, including an unverified one. The owner accepted this as low-risk, because the full pricing path rarely repeats an ASIN.
- **`_process_single_deal` runs the analysis twice.** The first run goes through `FUNCTION_LIST` → `get_list_at_price` → `_get_analysis` (cached, `processing.py:124`). The second is a direct `analyze_sales_performance` call at `processing.py:148`. On a cache miss that costs a second xAI call.
- **The light-update Amazon ceiling is off.** `ENABLE_LIGHTWEIGHT_CEILING_CLAMP = False` (`processing.py:31`). AGENTS.md §7.8 and Data_Logic.md said it was active; both were corrected in this PR.
- **The Zombie Data Defense re-fetch is disabled** (`smart_ingestor.py:465`, `is_zombie = False`). Nothing on the ingestion paths re-prices an existing row. `repair_pricing.py` is the **only** retry for an unverified price, and it sorts such a row **last** (tier 2, `repair_pricing.py:383-384`).
- **`XaiCache` and `XaiTokenManager` read `xai_cache.json` and `settings.json` from the current working directory** (`xai_cache.py:11`, `xai_token_manager.py:12`). The audit's `load_dotenv()` (`audit_list_at_sources.py:1076`) searches upward from the script's own directory, so a worktree run needs `.env` linked into it. That is how the audit ran from `/tmp/aa-v3` without merging.
- **`deploy_update.sh` restarts the services but does not pull** (`deploy_update.sh:4`, `:59`).

## 8. Open Items

1. **Trello #152**, the follow-up gap filed at deploy.
2. **The skip backlog re-sorts to the top of every run** (§7.1 of the prior logs): 7 of the 10 preview rows were skips.
3. **A hidden thin row stays hidden** until a later version bump or a new full pricing fetch; the light path never re-prices.
4. Carried forward: #143 (racy xAI counter), #145 (Keepa key rotation), #146 (`backup_db.sh` is a plain `cp`), #151 (main-grid flag and stale-rescue age).

## 9. Files Modified (PR #355)

| file | change |
| :--- | :--- |
| `keepa_deals/stable_calculations.py` | price-point identity; distinct-point mode/median; peak season and minimum; `peak_window_new_floor` and the cap; gated Amazon ceiling; fail-closed check |
| `keepa_deals/processing.py` | `Pricing_Logic_Version` NULL when the price is unverified |
| `keepa_deals/pricing_version.py` | version 2 → 3 |
| `repair_pricing.py` | refuses to start without `XAI_TOKEN`; headroom rationale rewritten |
| `audit_list_at_sources.py` | section (d); `--order random`; reuses production's season, cap and distinct-point helpers |
| `tests/` | 4 new files; updated `test_audit_list_at_sources`, `test_repair_pricing`, `test_1yr_avg_no_fallback`, `test_pricing_logic_version`, `test_stable_calculations_sparse_rescue` |
| `AGENTS.md` | §7.8 (sparse rule; light-path ceiling corrected), §7.13, new §7.15 |
| `Documentation/` | `INFERRED_PRICE_LOGIC.md` §4.A, `Data_Logic.md`, `System_State.md`, `System_Architecture.md` |
