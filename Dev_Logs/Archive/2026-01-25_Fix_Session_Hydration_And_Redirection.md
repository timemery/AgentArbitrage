# Dev Log: Fix Session Hydration and Login Redirection

**Date:** 2026-01-25
**Task:** Fix "View" button persistence on login and standardize login redirection.

## Overview
The user reported a usability issue where the Deals Dashboard would only display "View" buttons (generic fallback) instead of "Apply" or "Buy" buttons immediately after logging in. This occurred even for users who had previously connected their Amazon Seller Account (SP-API). The correct buttons would only appear after the user navigated to the Settings page and then back to the Dashboard.

Additionally, the user requested two UX improvements:
1.  Redirect all users (including Admins) to the Dashboard immediately after login, replacing the previous logic that sent Admins to the "Guided Learning" page.
2.  Ensure the application logo in the header links to the Dashboard for all logged-in users.

## Challenges
1.  **Session State Persistence:** The root cause of the "View" button issue was that the session variables `sp_api_connected`, `sp_api_user_id`, and `sp_api_refresh_token` were not being automatically populated (hydrated) upon login. They were only set when the `settings` route was accessed, which contained the logic to fetch credentials from the persistent database (`user_credentials`).
2.  **Test Environment Limitations:** The development environment lacks full browser automation tools (like Playwright with all dependencies), making it difficult to perform true end-to-end testing of the login flow and UI state. We had to rely on `unittest` and `pytest` with `flask.test_client()` to simulate session behavior.
3.  **Route Refactoring:** The logic for checking and restoring credentials was tightly coupled inside the `settings` view function, violating the DRY (Don't Repeat Yourself) principle and making it inaccessible to other routes.

## Solution

### 1. Session Hydration Logic
We extracted the credential recovery logic from `wsgi_handler.py:settings()` into a new standalone helper function: `ensure_sp_api_session()`.

```python
def ensure_sp_api_session():
    """
    Checks if the session has SP-API credentials. If not, attempts to re-hydrate
    them from the persistent database (user_credentials).
    """
    if not session.get('sp_api_connected'):
        try:
            creds = get_all_user_credentials()
            if creds:
                # ... (populates session variables) ...
                app.logger.info(f"Re-hydrated SP-API session for user: {user_record['user_id']}")
        except Exception as e:
            app.logger.error(f"Error checking DB...")
```

This function was then integrated into:
*   The `login()` route (immediately after successful authentication).
*   The `dashboard()` route (as a fail-safe check before rendering).
*   The `settings()` route (replacing the inline code).

This ensures that as soon as a user enters the authenticated state, their SP-API status is verified against the database, allowing the correct buttons to render immediately.

### 2. Login Redirection and Logo Link
*   **Redirect:** Updated `wsgi_handler.py` to remove the conditional check that redirected Admins to `url_for('guided_learning')`. Now, both the `login` POST handler and the `index` route redirect strictly to `url_for('dashboard')`.
*   **Logo:** Modified `templates/layout.html` to change the header logo's `href` from `url_for('guided_learning')` to `url_for('dashboard')`.

## Verification
*   **Reproduction Test:** Created `tests/reproduce_issue.py` which simulated a login and immediately checked the `/api/deals` endpoint response. It confirmed that `restriction_status` (which drives the button logic) was missing before the fix and present after the fix.
*   **Regression Test:** Updated `tests/test_auth_phase1.py` to verify that the Admin login now redirects to the Dashboard instead of the Guided Learning page. All tests passed.

## Outcome
The task was **successful**.
*   Users now see the correct "Apply"/"Buy" buttons immediately upon login.
*   The navigation flow is streamlined, with the Dashboard serving as the central hub for all users.
*   Code maintainability was improved by centralizing the session hydration logic.
