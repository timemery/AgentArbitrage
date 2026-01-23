# Fix Token Throttling and Keepa API Type Mismatch
**Date:** 2026-01-23
**Status:** SUCCESS

## Overview
The system was suffering from "excessive token usage" (token counts dipping to -200) while failing to collect new deal data (stuck at 223 items). Investigation revealed a severe mismatch between the data ingestion rate and the Keepa API's refill rate, as well as a subtle bug in how API query parameters were being transmitted.

## Challenges
*   **Token Starvation:** The `backfill_deals` task was processing chunks of 20 deals every second. Each chunk consumed ~126 tokens (due to fetching 3 years of history), but the Keepa API only refills ~5 tokens per minute. This caused immediate 429 errors and blocked the system.
*   **API Type Sensitivity:** The Keepa API was silently defaulting to "All Time" searches because the `dateRange` and `sortType` parameters were being sent as strings (`"4"`) instead of integers (`4`). This caused the system to fetch old data (from 2014) instead of new deals.
*   **Data Gaps:** The `update_recent_deals` (upserter) task would update its "watermark" (last scan time) even if it aborted early due to low tokens, permanently skipping any deals it missed during the aborted run.

## Resolution
1.  **Throttled Backfiller:**
    *   **File:** `keepa_deals/backfiller.py`
    *   **Action:** Increased the sleep time between chunks from `1` second to `60` seconds.
    *   **Rationale:** Research in `Dev_Logs/Archive/dev-log-7.md` showed the original 1s sleep was for CPU stability. Increasing it to 60s maintains CPU safety while aligning the consumption rate (1 batch/min) with the API refill rate (5 tokens/min), preventing 429 blocks.

2.  **Fixed API Query Types:**
    *   **Files:** `keepa_query.json`, `keepa_deals/keepa_api.py`
    *   **Action:** Changed `dateRange` and `sortType` values from strings to integers.
    *   **Effect:** The API now correctly respects the date range, returning recent deals instead of 2014 artifacts.

3.  **Prevented Data Loss:**
    *   **File:** `keepa_deals/simple_task.py`
    *   **Action:** Added an `incomplete_run` flag. If the task aborts due to low tokens, it now *skips* updating the watermark, ensuring it will resume from the same point next time and not miss any data.

## Technical Details
*   **Cost Analysis:** `fetch_product_batch` with `days=1095` costs ~126 tokens for 20 ASINs. This is an expensive call and must be rate-limited.
*   **Watermark Logic:** The watermark in `system_state` (DB) takes precedence over `watermark.json` (file). The fix ensures this state is only advanced on fully successful runs.
