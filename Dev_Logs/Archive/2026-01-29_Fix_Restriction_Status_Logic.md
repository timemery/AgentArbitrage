# Fix Restriction Status Logic - Dev Log

**Date:** 2026-01-29
**Task:** Fix the "Check Restriction" column logic in the Deals Dashboard, which was displaying incorrect states (specifically showing "Buy" buttons for items that had API errors).

## Overview
The user reported that the "Action" column in the Deals Dashboard was behaving erratically, showing "Buy" and "Apply" buttons inconsistently and sometimes showing only loading icons. The most critical issue identified was that items which failed the Amazon SP-API restriction check (returning an error state) were incorrectly defaulting to the "Buy" (Not Restricted) state. This posed a safety risk, as users might attempt to purchase items they are not actually approved to sell.

## Challenges
*   **Environment Instability:** The initial environment setup required careful handling of dependencies and database initialization. Reproducing the issue required creating a synthetic test database because the production database state could not be safely modified for destructive testing.
*   **Logic Gap Identification:** The core issue wasn't a crash, but a logic "fall-through". The code explicitly handled `None` (Pending) and `1` (Restricted), but lumped everything else (including `-1` for Error) into the `else` block, which assigned `not_restricted`.
*   **Frontend Verification:** Verifying the fix required simulating specific database states (`is_restricted` values of `1`, `0`, `-1`, and `None`) to ensure the dashboard rendered the correct icons (Apply button, Buy button, Warning icon, Spinner) for each case.

## Solution Implemented
1.  **Backend Logic Fix (`wsgi_handler.py`):**
    *   Updated the `api_deals` endpoint logic to explicitly check for `is_restricted == -1`.
    *   Mapped this value to a new status string `'error'`.
    *   The existing code:
        ```python
        # BEFORE
        if is_restricted is None:
            deal['restriction_status'] = 'pending_check'
        elif is_restricted == 1:
            deal['restriction_status'] = 'restricted'
        else:
            deal['restriction_status'] = 'not_restricted' # Caught -1 (Error) here!
        ```
    *   The fixed code:
        ```python
        # AFTER
        if is_restricted is None:
            deal['restriction_status'] = 'pending_check'
        elif is_restricted == 1:
            deal['restriction_status'] = 'restricted'
        elif is_restricted == -1:
            deal['restriction_status'] = 'error' # Explicitly handle error
        else:
            deal['restriction_status'] = 'not_restricted'
        ```

2.  **Verification:**
    *   **Unit Test (`tests/reproduce_issue.py`):** Created a script to populate a test database with deals in all four states. Verified that the API response for the error case changed from `'not_restricted'` to `'error'`.
    *   **Frontend Test (`verification/verify_dashboard.py`):** Used Playwright to render the dashboard with the test data. Confirmed visually (via screenshot) that the error case now displays the warning icon (`⚠`) instead of the "Buy" button.

## Outcome
**Successful.** The task was completed, and the critical logic flaw was resolved. The dashboard now correctly informs the user when an automated restriction check has failed, allowing them to investigate manually rather than assuming the item is safe to buy.

## Reference Material
*   **Database Schema:** The `user_restrictions` table uses the following values for `is_restricted`:
    *   `1`: Restricted
    *   `0`: Not Restricted
    *   `-1`: Error / Auth Failure / API Error
    *   `NULL` (No Record): Pending Check
*   **Dashboard States:**
    *   `restricted` -> "Apply" Button (Orange)
    *   `not_restricted` -> "Buy" Button (Green)
    *   `error` -> Warning Icon (`⚠`)
    *   `pending_check` -> Spinner
