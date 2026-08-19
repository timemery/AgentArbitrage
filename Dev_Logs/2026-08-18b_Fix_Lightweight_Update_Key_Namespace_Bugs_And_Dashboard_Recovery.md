# Dev Log Entry: Fix Lightweight-Update Key-Namespace Bugs & Recover Hidden Deals

**Date:** August 18, 2026 (evening session)
**Files:** `keepa_deals/processing.py`, `keepa_deals/smart_ingestor.py`, `tests/test_seller_name_logic.py`
**Status:** SUCCESS — SIX KEY-NAMESPACE BUGS FIXED, MERGED TO MAIN (PR #323), DEPLOYED, RECOMPUTE RECOVERED +241 DEALS (572 → 813)
**Tooling note:** This was the first task completed via **Claude Code (web)**, replacing Jules. Fixes were committed to a branch, merged via GitHub PR #323, pulled to the VPS, and deployed.

---

## 1. Task Overview

Following the daytime token-livelock fixes (see `2026-08-18_Fix_Token_Livelock_Regression_And_Batch_Deficit.md`), the dashboard was still stale and the visible deal count was decaying. The investigation set out to find why viable deals were disappearing, initially suspecting the peak-price/XAI reasonableness logic. That hypothesis was disproven; the true cause was a class of key-namespace mismatches in the lightweight-update path that silently zeroed prices and manufactured fake losses.

---

## 2. Investigation Arc (hypotheses raised and discarded, with evidence)

This is recorded deliberately so the same dead ends aren't re-run.

1. **"XAI is over-rejecting good deals."** DISPROVEN. `grep -c "XAI REJECTED" celery_worker.log` = **0**. The AI rejected nothing in the log window. The four sample rejected ASINs from the morning diagnostic were all rejected for unrelated reasons (never ingested, correct economics, or died before the peak-price stage).
2. **"The `$`-string `List_at` corruption is the staleness cause."** DISPROVEN. Every code path that reads `List_at` already sanitizes the `$` (`_parse_currency_to_float`, `recalculator.py:97`, dashboard `CAST(REPLACE(...))`). Fixing the string type would restore **zero** deals. It is a latent landmine (one future unsanitized query = silent zero), not the active cause. All 610 then-visible profitable deals were `text`-typed rows.
3. **"`All_in_Cost` is inflated ~10x."** DISPROVEN. `SELECT COUNT(*) ... WHERE All_in_Cost > Price_Now * 3` = **0**. Costs were sane; the *Profit* values were stale/garbage, not the cost inputs.
4. **"The Amazon ceiling clamp is a destructive one-way ratchet."** DISPROVEN. `grep -c "Lightweight Update - Clamped"` = **0**. The clamp was unreachable *dead code* — because `list_at_price` was always `0.0` (see root cause), the `if list_at_price > ceiling` branch never fired.

---

## 3. Root Cause (confirmed)

A class of **header-name vs. DB-column-name key mismatches** in the lightweight-update path. `_process_lightweight_update` and the Stale-Deal-Rescue loop receive a `dict(sqlite3.Row)` keyed by **DB column names** (`List_at`, `1yr_Avg`, `Seller_ID`, `Price_Now`, `Percent_Down`), but the code read them using **display/header names with spaces** (`'List at'`, `'1yr. Avg.'`, `'Seller ID'`, `'Price Now'`).

Consequences, each matched to observed data:
- `row_data.get('List at')` → `None` → `list_at_price = 0.0` → `Profit = 0 − cost − fees` → **negative for every rescued row** (408/408 recomputed rows unprofitable; 1,602 deals hidden by Stale Rescue).
- Referral fee skipped when `list_at_price ≤ 0` → `Total_AMZ_fees == FBA_PickandPack_Fee` in affected rows (observed exactly).
- `r['List at']` on a raw `sqlite3.Row` raised **IndexError**, aborting the existing-ASIN check on the first row of every batch (**238** `Failed to check existing ASINs` events), which also skipped `conn_check.close()` → **238 leaked DB connections** (the §7.11 lock-contention hazard).
- `'1yr. Avg.'` mismatch → Percent Down never recalculated on lightweight updates.
- `'Seller ID'` mismatch → seller *name* overwritten with raw seller *ID* on every update (violated the §7.8 "Seller Name Preservation" rule).
- `'Price Now'` mismatch (latent) → fell back to `0.0` when no Used offer found, corrupting `all_in_cost`/Profit for that row.

Likely origin: the Aug 17 `List_at` storage fix introduced/exposed the DB-column-key contract, but the lightweight function was still reading display-name keys. A unit test (`test_seller_name_logic.py`) had encoded the *same* wrong key assumption, so it stayed green while production failed — masking the bug.

**Important recovery fact:** the real `List_at` values were **never destroyed** — only mis-read. So recovery required no Keepa tokens, just a recompute of derived columns.

---

## 4. Fixes Implemented (PR #323, commits e4cf1f9 → 7f5e25c)

All in `keepa_deals/processing.py` and `keepa_deals/smart_ingestor.py`:
1. `smart_ingestor.py:447–448` — `r['List at']`→`r['List_at']`, `r['1yr. Avg.']`→`r['1yr_Avg']`; `conn_check.close()` moved into a `finally` (leak fixed).
2. `processing.py` — `row_data.get('List at')`→`get('List_at')` (read + paired clamp write-back).
3. `processing.py` — `row_data.get('1yr. Avg.')`→`get('1yr_Avg')` (+ paired `Percent Down`→`Percent_Down` writes).
4. `processing.py` — `row_data.get('Seller ID')`→`get('Seller_ID')` (read + write; restores §7.8 seller-name preservation).
5. `processing.py` — `row_data.get('Price Now')`→`get('Price_Now')` with a DB fallback (not a bare rename) so a missing Used offer preserves the stored `Price_Now` instead of falling to `0.0`.
6. `tests/test_seller_name_logic.py` — fixture corrected to the real DB-column key model (no assertions weakened; now exercises the true contract).

The `_process_single_deal` (heavy) path was deliberately NOT touched — it correctly builds rows keyed by display names.

**Ceiling clamp intentionally gated OFF** (`ENABLE_LIGHTWEIGHT_CEILING_CLAMP = False`). Fixing the read makes the clamp reachable for the first time; activating it would impose unspecified peak-price semantics, so it waits for the seasonal spec (see doc update).

---

## 5. Deployment & Recovery

`deploy_update.sh` confirmed to contain **no git commands** — it only restarts services; code must be pulled to the VPS separately (the old Jules workflow used manual SFTP; the new flow is GitHub merge → `git pull origin main` on the box). PR #323 merged to `main`; VPS fast-forwarded `fe390b7 → d6f21e9` (clean, working tree empty); services restarted.

Recompute via existing `run_deals_migration.py` (derived columns only — `Profit`, `Margin`, `Total_AMZ_fees`, `Min_Listing_Price`, `Detailed_Seasonality`, `Sells`; reversible via `restore_db.sh`; own timestamped backup). Result:

- **Before: 572 visible.  After: 813 visible (`Profit > 0 AND List_at IS NOT NULL`).**
- +241 profitable deals recovered. Sample confirmations: `0856485837` +$161.60, `6052981032` +$98.48, `1368018734` +$74.81 — previously hidden as losses.
- Runtime ~3,542s (slow because the recompute also re-runs the XAI seasonality classifier per row; hit the 1,000/day XAI cap near the end — final rows defaulted to "Year-round").

---

## 6. Open Items / Follow-Ups

- **`ValueError: could not convert 'None' to float`** in the recompute when `List_at` holds the literal string `'None'` — non-fatal (all 2378 rows updated) but a one-line guard is warranted in `run_deals_migration.py` / `recalculator.py`.
- **Dashboard freshness still unresolved** — newest deal ~5 days old. Today's work recovered *hidden* deals; it did not fix *new-deal inflow*. The watermark was manually reset earlier (Aug 12 → Aug 17), but whether it advances on its own is unconfirmed. This is the next priority.
- **Ceiling clamp remains gated OFF** pending the seasonal-semantics spec (see `INFERRED_PRICE_LOGIC.md` update).
- **XAI daily cap (1000)** is hit by a full recompute — a full recompute should throttle or run in batches to avoid starving live classification.
- **`$`-string `List_at` landmine** persists (1,103 text rows) — harmless today, worth a one-time migration eventually, done carefully since the live dashboard depends on those rows.
- **`test_smart_ingestor_batching`** fails on clean HEAD (pre-existing, unrelated) — worth a separate look.
