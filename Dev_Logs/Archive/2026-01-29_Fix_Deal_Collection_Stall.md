# Dev Log: Fix Deal Collection Stall

**Date:** 2026-01-29
**Task:** Fix Stalled Deal Collection (Delta Sync Failure)
**Status:** Successful

## Overview
The system's deal collection pipeline (`update_recent_deals`) had stalled, failing to ingest new deals for several hours. Diagnostics showed that the task was running but finding "0 new deals" and stopping immediately. Additionally, the Celery Beat scheduler was found to be stopped.

The root cause was identified as a logic mismatch between the "Delta Sync" strategy and the API query parameters. The Delta Sync logic relies on fetching deals sorted by **Last Update (Newest First)**. It iterates through the list and stops as soon as it encounters a deal older than the "Watermark" (last successful sync time).

Logs revealed that the API was being queried with `sortType: 0` (Sales Rank / Default) instead of `sortType: 4` (Last Update). Because highly-ranked deals are not necessarily new, the first page of results almost always contained an "old" deal, causing the Delta Sync logic to trigger an immediate exit ("Stop pagination"), skipping all actual new deals.

## Challenges Faced

1.  **Stale Running Code:**
    -   The source code appeared to set `sort_type=4`, but the logs explicitly stated `Fetching deals using a hardcoded... query... Sort: 0`. This indicated that the running Celery worker was using an older version of the code or ignoring the parameter.
    -   *Resolution:* We modified `simple_task.py` to use an explicit constant `SORT_TYPE_LAST_UPDATE = 4` and added logging to print the *actual* value being used. This forced a code change that would be picked up on restart.

2.  **Misleading Timestamp Artifacts:**
    -   Logs showed a confusing discrepancy: `Loaded watermark: 2014-11-24... (Keepa time: 7836100)`.
    -   A Keepa timestamp of `7836100` minutes (since 2011 Epoch) actually corresponds to late 2025. The "2014" date in the log was a red herring (likely a hardcoded fallback or display error in an older log line).
    -   *Resolution:* Created `Diagnostics/verify_time_conversion.py` which verified that the system's time conversion logic (`_convert_iso_to_keepa_time` and `_convert_keepa_time_to_iso`) was actually correct and using the 2011 Epoch properly. This saved us from refactoring working code.

3.  **Environmental Instability:**
    -   The production environment was unstable, and the agent did not have permission to restart system services (`systemctl`, `service`, etc.) or access `/var/www` directly to restart Celery.
    -   *Resolution:* We relied on local unit testing with `unittest.mock` to verify the logic of the fix (confirming the function call arguments), and the user manually handled the process restart.

## Actions Taken

1.  **Code Fix in `simple_task.py`:**
    -   Defined `SORT_TYPE_LAST_UPDATE = 4` to eliminate magic numbers.
    -   Updated the `fetch_deals_for_deals` call to explicitly use this constant.
    -   Added high-visibility logging: `logger.info(f"Fetching deals using Sort Type: {SORT_TYPE_LAST_UPDATE} (Last Update)...")`.

2.  **Diagnostic Tooling:**
    -   Created `Diagnostics/verify_time_conversion.py` to serve as a permanent verifier for the Keepa 2011 Epoch logic.

3.  **Verification:**
    -   Wrote a specific unit test `tests/verify_fix_test.py` that mocked the Redis and API layers.
    -   The test confirmed that `fetch_deals_for_deals` is indeed called with `sort_type=4` under the new code.

## Outcome
The task was successful. The user reported that "the script appears to be collecting deals again."

## Technical Takeaways for Future Agents

*   **Delta Sync Requirement:** Any task that uses the "Stop when older than Watermark" logic **MUST** ensure the API returns data sorted by `Last Update` (`sortType: 4`). If it sorts by anything else (Sales Rank, Deal Age), the logic will break silently.
*   **Keepa Epoch:** Always remember the Keepa Epoch is **2011-01-01**, not 1970 or 2000. `7,800,000` minutes is roughly late 2025.
*   **Celery State:** If logs contradict the code (e.g., Log says "Sort 0" but code says "Sort 4"), the worker process is likely stale. Force a restart or modify the file to trigger a reload.
