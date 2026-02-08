# Fix Restriction Check Silent Failure & Infinite Loading Spinners

**Date:** 2026-02-08
**Author:** Jules
**Status:** Success

## Overview
The "Check Restriction" feature, which queries Amazon SP-API to determine if a user is gated from selling a product, was failing silently. This resulted in deals on the dashboard displaying an infinite loading spinner (Pending state) instead of resolving to "Apply" (Restricted), "Buy" (Approved), or an Error icon. Previous fixes addressed some error paths, but the issue persisted, indicating a deeper resiliency problem where background tasks were crashing or stalling without updating the database.

## Challenges
1.  **Silent Failures:** The background Celery tasks (`check_all_restrictions_for_user`) would sometimes crash or time out due to network issues with the Amazon SP-API. Because the exception handling was not comprehensive, the task would exit *without* writing a result to the database. The frontend, seeing a `NULL` value in the `is_restricted` column, would assume the check was still in progress and display the spinner forever.
2.  **API Stalls:** The `requests.get` call to the Amazon API did not have a timeout configured. If the connection hung (a common occurrence with external APIs), the worker thread would be blocked indefinitely, neither failing nor succeeding.
3.  **Lack of Visibility:** The system lacked diagnostic tools to quickly identify how many deals were stuck in this "Pending" limbo versus genuine processing delays.

## Solutions Implemented

### 1. Robust Exception Handling with Fallback
*   **File:** `keepa_deals/sp_api_tasks.py`
*   **Change:** Implemented a multi-layered `try...except` strategy.
    *   **Batch Level:** If a specific batch of 5 items fails (e.g., API returns 500), the `except` block catches it and immediately writes an "Error" state (`is_restricted = -1`) to the database for those 5 items.
    *   **Task Level (Outer Loop):** Added a global `try...except` block around the entire task logic. If the script crashes unpredictably (e.g., Database connection loss, Memory error), the `except` block calculates which items were left pending and attempts to bulk-update them to "Error".
*   **Outcome:** "Fail Loudly." The UI is guaranteed to receive a terminal state (Error icon) rather than hanging, allowing the user to retry.

### 2. API Timeouts
*   **File:** `keepa_deals/amazon_sp_api.py`
*   **Change:** Added `timeout=15` to the `requests.get()` call.
*   **Outcome:** If Amazon does not respond within 15 seconds, the request raises a `Timeout` exception. This exception is caught by the new robust handler in the task, which then marks the item as "Error". This prevents worker starvation caused by hung threads.

### 3. Diagnostic & Recovery Tools
*   **`Diagnostics/debug_restriction_status.py`:** A script that inspects the database and reports the exact count of deals in each state (Pending, Error, Restricted, Approved). It specifically flags "Pending" deals that are candidates for being stuck.
*   **`Diagnostics/force_restriction_check.py`:** A surgical recovery tool. It finds *only* the deals currently in the "Pending" (stuck) state and re-queues them for processing. This allows the user to unblock the dashboard without re-running the check for thousands of already-processed items.

## Verification
*   **Reproduction:** A test script (`Diagnostics/reproduce_restriction_bug.py`) successfully mocked a crash inside the API function and verified that the new code caught the exception and updated the database to `-1` (Error).
*   **Live Confirmation:** The user ran the diagnostic tools on the production server.
    *   `debug_restriction_status.py` identified 70 stuck deals.
    *   `force_restriction_check.py` successfully queued them.
    *   **Result:** The user confirmed "Web UI is now showing no loading spinners."

## Conclusion
The system is now resilient against both network stalls and unexpected crashes during restriction checks. The introduction of specific diagnostic and recovery scripts empowers the user to manage the system state effectively if external APIs become unstable in the future.
