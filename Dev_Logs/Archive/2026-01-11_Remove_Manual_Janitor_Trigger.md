# Dev Log: Remove Manual Janitor Trigger

**Date:** 2026-01-11
**Task:** Remove user-initiated Janitor trigger from "Refresh Deals" link on the dashboard.
**Status:** Success

## Overview
The user requested the removal of the manual "Janitor" trigger from the "Refresh Deals" button on the dashboard. The Janitor task (`/api/run-janitor`) deletes deals older than 72 hours. Allowing users to trigger this manually was deemed risky as it could lead to the deletion of deals that the backfiller hasn't had time to update yet, effectively causing data loss from the user's perspective. The system should instead rely solely on the scheduled background Janitor task (every 4 hours).

The requirements were:
1.  Remove the API call to `/api/run-janitor` in `templates/dashboard.html` but keep the code commented out for reference/debugging.
2.  Update the documentation to reflect this change.
3.  Add an explanatory comment in the code.

## Changes Implemented

### 1. Dashboard Template (`templates/dashboard.html`)
-   Commented out the `await fetch('/api/run-janitor', { method: 'POST' });` line within the "Refresh Deals" click handler.
-   Added a detailed comment block explaining *why* it was removed (to prevent accidental data loss) and noting that the backend logic remains intact.
-   The "Refresh Deals" button now only triggers `fetchDeals()`, which reloads the grid with the latest data from the database.

### 2. Documentation Updates
-   **`Documentation/System_State.md`**: Updated the "Dashboard & UI" section to explicitly state that the "Refresh Deals" button no longer triggers the Janitor.
-   **`Documentation/System_Architecture.md`**: Updated the `clean_stale_deals` (Janitor) section to remove "Manual" from the Trigger list and add a note about the removal.
-   **`Documentation/Dashboard_Specification.md`**: Updated "The 'Janitor' & Data Freshness" section to clarify the new behavior.

## Challenges & Solutions

### 1. Environment Instability (Missing Dependencies)
-   **Challenge:** Upon starting the sandbox, the `flask` module and other dependencies were missing, preventing the application from starting (`ModuleNotFoundError`).
-   **Solution:** Ran `pip install -r requirements.txt` to restore the environment. This is a recurring issue with fresh sandboxes where the `venv` or system packages might not be fully hydrated.

### 2. Playwright Verification (Login Form Interaction)
-   **Challenge:** The initial verification script failed to log in because the login form is hidden behind a toggle button. The script attempted to click "Login" immediately but couldn't interact with the hidden inputs.
-   **Solution:** Updated the Playwright script to first click the "Log In" toggle button (`button.login-button`) to reveal the form, and then proceeded to fill in credentials and submit.
-   **Challenge:** Distinguishing between the "Log In" toggle button and the "Log In" submit button (both had similar text).
-   **Solution:** Used specific CSS selectors (`button.login-button` vs `form.login-form button[type='submit']`) to target the correct elements.

### 3. Playwright Network Interception
-   **Challenge:** Verifying that a specific API call *did not* happen.
-   **Solution:** Used Playwright's `page.route("**/*", handle_route)` to intercept all network requests. The handler flagged a boolean `janitor_called` if a request to `/api/run-janitor` was detected. The test asserted that this boolean remained `False` after clicking the refresh button.

## Outcome
The task was completed successfully. 
-   The "Refresh Deals" button now functions safely as a simple data reloader.
-   The documentation accurately reflects the system state.
-   The change was verified with a targeted automated test script.
