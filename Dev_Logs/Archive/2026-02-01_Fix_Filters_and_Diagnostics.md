# Dev Log: Fix Dashboard Filters & System Diagnostics

## Tasks Completed
1.  **Dashboard Filters ("Any" Logic)**
    -   **Issue**: "Min. Profit" and "Min. Margin" filters defaulted to `$0+` and `0%+`, which hid negative values. Users wanted a true "Any" state.
    -   **Fix (Frontend)**: Updated `templates/dashboard.html` and `static/js/dashboard.js` (embedded) to display "Any" when the slider is at 0.
    -   **Fix (Backend)**: Modified `wsgi_handler.py` to skip the SQL `WHERE` clause for `margin_gte` when the value is 0. (Profit logic was already correct).
    -   **Verification**: Verified via Playwright script `verification/verify_filters.py`.

2.  **System Diagnostics ("One Tool")**
    -   **Requirement**: A single script to check the entire application health.
    -   **Implementation**: Created `Diagnostics/system_health_report.py`.
    -   **Checks**: Environment (.env, keys), Infrastructure (Redis, Celery), Database (Integrity, Tables), API Connectivity (Keepa, xAI), and Logs.
    -   **Output**: Console with emojis and a JSON summary.

3.  **Service Resiliency (Startup Loop)**
    -   **Issue**: Services (Celery/Beat) were failing silently or not restarting.
    -   **Fix**: Rewrote `start_celery.sh` to include an infinite `while true` loop that monitors processes every 60 seconds and restarts them if missing.
    -   **Refinement**: Updated process detection from strict string matching to flexible regex (`celery.*worker`) to prevent false negatives and restart loops.
    -   **Automation**: Created `Diagnostics/fix_and_restart.py` to automate the "Kill -> Start -> Verify" workflow.

## Current State (Failure)
Despite the logic fixes in `start_celery.sh`, the diagnostic report still shows **Celery Worker** and **Celery Beat** as `FAIL - Not Found`.
-   The monitor log indicates the loop is running.
-   The worker log shows successful startup.
-   **Hypothesis**: There is a disconnect between how the processes are spawned (via `su -s ... www-data`) and how they are detected (`pgrep`) or they are crashing silently post-startup.

## Artifacts
-   `Diagnostics/system_health_report.py`
-   `Diagnostics/fix_and_restart.py`
-   `start_celery.sh` (Modified)
-   `TASK_DIAGNOSE_SERVICE_FAILURE.md` (Handoff)
