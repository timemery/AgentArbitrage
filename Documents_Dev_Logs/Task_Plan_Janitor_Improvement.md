# Task Plan: Janitor Improvements

## Problem
The Janitor is aggressively deleting deals (older than 24 hours), often emptying the dashboard. The `backfiller` and `simple_task` (upserter) may not be "touching" (updating `last_seen_utc`) valid deals frequently enough, causing them to be falsely identified as stale.

## Analysis
1.  **Current Logic:** `keepa_deals/janitor.py` deletes any record where `last_seen_utc < NOW - 24 hours`.
2.  **Backfill Cycle:** The backfiller processes sequentially. If the total number of deals is large, or if it restarts often, it might take > 24 hours to cycle back to a deal.
3.  **Upserter (Delta) Logic:** `simple_task.py` fetches *modified* deals (`sort_type=4`, Last Update). If a deal is valid but *static* (price/rank hasn't changed), it won't appear in the delta feed.
4.  **The Gap:** Valid, static deals are ignored by the Upserter (correctly, to save tokens) but are then killed by the Janitor because the Backfiller is too slow to "refresh" their `last_seen_utc`.

## Proposed Solution (Token-Free)

### 1. "Soft Delete" Strategy
Instead of physically deleting records immediately, mark them as "possibly stale" or use a much longer physical deletion window.
-   **Action:** Increase default `grace_period_hours` in `keepa_deals/janitor.py` from **24 hours** to **72 hours (3 days)**. This gives the backfiller/upserter ample time to cycle through.

### 2. "Touch" Logic Verification
Ensure that *any* time a deal is seen (even if skipped for processing), its `last_seen_utc` is updated.
-   **Check:** Verify `simple_task.py` and `backfiller.py`. Currently, they update `last_seen_utc` inside `_process_single_deal` or right before upserting.
-   **Improvement:** Even if a deal is skipped due to "no change" (if we had such logic, though currently we rely on Keepa's delta), we should "touch" it.
    - *Correction:* `simple_task.py` fetches `lastUpdate` sorted deals. If a deal isn't in that list, we *don't see it*. So we can't "touch" it without fetching it.
    - *Conclusion:* The only way to "touch" static deals is via the Backfiller (pagination). Therefore, the Janitor's timeout *must* be longer than the Backfiller's full cycle time.

### 3. Adaptive Janitor (Brainstorming)
-   **Idea:** Could the Janitor check the *total count* of deals in DB vs Keepa's total count? (Keepa API `deal` response includes `totalCount`?)
-   **Idea:** Only delete if `last_seen_utc` is old AND `source == 'backfiller'`. If `source == 'simple_task'`, maybe we treat it differently? (Unlikely to help).

## Recommended Task
**Task:** Tune Janitor and Verify "Touch" Rate
1.  **Modify `keepa_deals/janitor.py`:** Increase default grace period to **72 hours**.
2.  **Monitor:** Watch the "Total Processed" vs "Total Rejected" logs. With the new Rejection Logic (from the previous task), we expect far more deals to be "Successfully Saved" (updated `last_seen_utc`).
    - *Hypothesis:* The "aggressive" deletion was partly because 98% of backfilled items were REJECTED, so their `last_seen_utc` in the DB (if they existed) wasn't being updated?
    - *Wait:* If a deal exists in DB, and Backfiller finds it but *rejects* it (e.g. "Missing List at"), does it update `last_seen_utc`?
    - *Critical Check:* Look at `backfiller.py`.
        - `processed_row = _process_single_deal(...)`
        - `if processed_row: ... upsert ...`
    - *Finding:* **If a deal is rejected (returns None), `last_seen_utc` is NOT updated.**
    - *Root Cause:* The 98% rejection rate meant 98% of deals were effectively invisible to the "refresh" mechanism. The Janitor then deleted them.
    - *Solution:* The fix for rejection rate (Amazon Ceiling + Fallback) should naturally fix the Janitor issue by allowing those deals to be "seen" and updated.

**Conclusion:** The primary fix is likely already done (Reducing Rejection Rate). The secondary safeguard is increasing the Janitor timeout to 72h to account for slow backfill cycles.

## Task Steps
1.  Modify `keepa_deals/janitor.py` to change default `grace_period_hours` to `72`.
2.  (Optional) Add a log in `backfiller.py` to count "Refreshed" deals vs "New" deals.
