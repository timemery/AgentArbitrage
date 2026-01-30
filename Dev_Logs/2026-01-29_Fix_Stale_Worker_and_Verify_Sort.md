# Fix Stale Worker and Verify Deal Collection Sort Logic

**Date:** 2026-01-29
**Task:** Investigate and fix stalled deal collection by verifying worker code freshness.
**Status:** Successful

## Overview
The user reported that deal collection was stalled or dwindling, with logs showing:
1.  **Stale Code:** The system was referencing `importer_task` (which had been deleted in a previous update) and using `Sort Type: 0` (Sales Rank) instead of `Sort Type: 4` (Last Update).
2.  **Logic Failure:** Because the API was sorting by Sales Rank, the "Delta Sync" logic (which stops pagination upon finding an old deal) was triggering immediately, causing the system to find "0 new deals" and exit prematurely.

The investigation confirmed that the codebase itself was correct (`simple_task.py` correctly specified `Sort Type: 4`), but the running Celery worker process was "stale" — it had not picked up the recent code changes despite restart attempts.

## Challenges Faced

1.  **Stale Worker Processes:**
    -   The primary challenge was that the running process did not match the source code on disk. Standard restart scripts were failing to fully kill/reload the worker, leaving the old code (with the `Sort: 0` bug) active in memory.
    -   *Resolution:* We modified the code to include a specific version identifier (`SIMPLE_TASK_VERSION`) to act as a "tracer bullet," allowing definitive verification of which code version was running.

2.  **Log File Confusion:**
    -   Verification initially failed because we were grepping `celery.log` (which was stale/unused) instead of `celery_worker.log` (where the active worker was actually writing).
    -   *Resolution:* Corrected the verification command to target the correct log file defined in `start_celery.sh`.

## Actions Taken

1.  **Code Instrumentation (`keepa_deals/simple_task.py`):**
    -   Added a constant `SIMPLE_TASK_VERSION = "2.10-Sort-Fix-Verified"`.
    -   Added logging at the start of the `update_recent_deals` task to print this version string.
    -   Added logging to print the module source of `fetch_deals_for_deals` to confirm the import path.

2.  **Verification:**
    -   The user performed a forceful restart of the environment.
    -   We verified the fix by grepping the logs for the unique version string:
        ```bash
        grep -a "Version: 2.10-Sort-Fix-Verified" /var/www/agentarbitrage/celery_worker.log | tail -n 1
        ```
    -   **Result:** `[INFO] --- Task: update_recent_deals started (Version: 2.10-Sort-Fix-Verified) ---`
    -   This confirmed the worker was finally running the corrected code, which inherently includes the `Sort Type: 4` fix.

## Outcome
The task was successful. The system is now confirmed to be running the correct code version that forces `Sort Type: 4` (Last Update). This ensures that the "Delta Sync" logic (stopping when a deal is older than the watermark) functions correctly, preventing the premature stalls that were occurring when sorting by Sales Rank.

## Technical Takeaways for Future Agents

*   **Version Tracing:** When you suspect a "stale worker" (code on disk doesn't match behavior), adding a unique, logged constant (like `VERSION = "..."`) is a highly effective way to prove whether the restart actually worked.
*   **Log Locations:** Always check `start_celery.sh` or the Supervisor config to confirm *where* logs are being written. Do not assume `celery.log` is the active file; in this setup, it is `celery_worker.log` and `celery_beat.log`.
*   **Sort Type is Critical:** For any "Delta Sync" or "Watermark" strategy to work, the API **MUST** return data sorted by `Last Update` (`Sort Type: 4`). If it defaults to `Sort Type: 0`, the sync logic will break immediately.
