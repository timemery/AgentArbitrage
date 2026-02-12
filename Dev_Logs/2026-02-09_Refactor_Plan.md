

# Refactoring Plan: The "Smart Upserter"

## Executive Summary
This task involves consolidating our deal ingestion pipeline into a single, efficient process. We will decommission the legacy `Backfiller` (`backfiller.py`) and upgrade the existing `Upserter` (`simple_task.py`) to handle all data ingestion duties. The new component will be renamed to **`Smart_Ingestor`** to reflect its expanded role.

The goal is to increase market velocity capture (the "275 Deal Ceiling") by eliminating token starvation caused by the backfiller's heavy historical scans, while preserving the critical safety nets the backfiller provided.

## 1. Archival Strategy
Before making any changes, we must preserve the current state for reference:
1.  **Archive `backfiller.py`**: Move to `Archive/backfiller_legacy.py`.
2.  **Archive `simple_task.py`**: Move to `Archive/simple_task_legacy.py`.
3.  **Create New File**: `keepa_deals/smart_ingestor.py` (The new home for the refactored code).

## 2. Core Architecture: The "Smart Ingestor"
The new `Smart_Ingestor` will be a single Celery task running every minute (or as tokens allow). It must implement the following pipeline:

### A. Hardcoded Safety
*   **Enforce Sort Type 4**: The ingestion loop *must* hardcode `sortType=4` (Last Update) in the API call, overriding any user-pasted queries. This ensures chronological processing for the watermark.

### B. The "Peek Strategy" (Ported from Backfiller)
Do not fetch full history (20 tokens) for every new deal.
1.  **Stage 1: The Peek (2 Tokens)**
    *   **Fetch `stats=365` (Not 90)**: Use the `stats=365` parameter. This costs the same as `stats=90` (approx 2 tokens) because we are *not* requesting the CSV history (`history=0`).
    *   **Benefit**: This provides the 365-day average price/rank, allowing us to detect seasonal items that look bad on a 90-day view but good on a yearly view.
    *   **Action**: Apply heuristic filters (Profit > $0, ROI > 20%, Current Price < 365-Day Avg, etc.).
2.  **Stage 2: The Commit (20 Tokens)**
    *   Only for deals that pass Stage 1.
    *   Fetch `stats=365` + `offers=20` + `history=1` for full analysis and CSV data.

### C. The "Watermark Ratchet" (Critical Fix)
*   **Incremental Saves**: Do *not* wait for the end of the run to update the watermark. Update it after every successful batch (e.g., every 10 deals).
*   **Scan vs. Save**: The watermark must track the timestamp of deals **scanned**, not just deals **saved**. If we scan 100 bad deals and reject them all, the watermark *must* still advance past them to prevent an infinite loop.

### D. Price Validation & AI Logic (New Requirement)
*   **Trust the Amazon Ceiling (Bypass AI)**:
    *   Modify `keepa_deals/stable_calculations.py` or the ingestion logic.
    *   **Logic:** If the calculated "List at" price is capped by the "Amazon Ceiling", consider it inherently "market-validated" and **skip the AI Reasonableness Check** (`_query_xai_for_reasonableness`).
    *   **Definition of "Amazon Ceiling":** Calculate the MINIMUM of:
        1.  **Current Amazon Price** (`stats.current[0]`)
        2.  **180-Day Average** (`stats.avg180[0]`)
        3.  **365-Day Average** (`stats.avg365[0]`)
    *   **CRITICAL WARNING:** Do **NOT** use `stats.min` (Keepa's Lifetime Lowest Price). That field often refers to ancient pricing (e.g., from 5+ years ago) and is irrelevant to current market value. Only use the **Current** and **Recent Averages** listed above.

## 3. "Past Demons" to Port (Missing Protections)
The following features exist in the Backfiller and *must* be ported to prevent regression:

1.  **Zombie Data Defense (Self-Healing)**
    *   **Logic:** If the `Smart_Ingestor` encounters a deal with missing critical fields (`List Price` or `1yr Avg`), it must trigger an immediate, one-time retry with full history.
    *   **Fallback:** If the retry fails, *log it and ignore it*. Do not save "Zombie" rows (Null/Zero values) to the DB.

2.  **Ghost Restriction Sweeper**
    *   **Logic:** The current Upserter triggers a background task to check Amazon restrictions. If this task crashes silently, the deal stays "Pending".
    *   **New Feature:** Add a small routine (or separate cron) that finds deals stuck in `Pending` for > 1 hour and re-queues them.

3.  **Livelock Protection**
    *   **Logic:** Ensure `TokenManager` integration is robust. The task should sleep/wait efficiently if tokens are low, but *never* hang indefinitely. Use the `request_permission_for_call` pattern with timeouts.

## 4. Implementation Steps
1.  **Duplicate & Rename**: Copy `simple_task.py` to `smart_ingestor.py`.
2.  **Integrate Peek**: Replace the simple fetch loop with the 2-Stage "Peek & Commit" logic from `backfiller.py`, using `stats=365`.
3.  **Harden Watermark**: Modify the loop to update the watermark timestamp progressively.
4.  **Add Self-Healing**: Insert the "Zombie Check" logic before the final DB upsert.
5.  **Implement AI Bypass**: Update `stable_calculations.py` to skip XAI checks if `peak_price_mode_cents` was capped by `ceiling_price_cents`. Ensure `ceiling_price_cents` uses only current/recent metrics, NOT `stats.min`.
6.  **Update Celery Config**: Point the beat schedule to `smart_ingestor.run` instead of `simple_task`.
7.  **Decommission**: Disable the `backfill_deals` task in Celery.

## 5. Known "Gotchas"
*   **User Sort Chaos**: Users might paste `sort=3` (Sales Rank) into settings. The code *already* handles this by forcing `sort=4`, but verify this protection remains in the new file.
*   **Database Bloat**: Do NOT save rejected deals. Rely on the Watermark to know we've "seen" them.
*   **365-Day Blind Spot Resolved**: By switching the Peek to `stats=365`, we have eliminated the "90-Day Blind Spot" risk.

## 6. Success Criteria
*   **Velocity**: Deal processing speed increases > 5x (due to lower token cost per deal).
*   **Stability**: No "stuck" states (Livelocks or Loops).
*   **Integrity**: No "Zombie" rows in the DB.
*   **Continuity**: Watermark advances steadily even when finding no profitable deals.
