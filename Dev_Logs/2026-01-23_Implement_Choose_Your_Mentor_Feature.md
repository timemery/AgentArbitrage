# Dev Log: Implement Choose Your Mentor Feature

**Date:** 2026-01-23
**Task:** Implement "Choose Your Mentor" feature for Ava Advisor.

## Overview
The goal was to allow users to select different "Mentor" personas (CFO, Flipper, Professor, Quant) to customize the AI's analysis style in the Deal Details Overlay. This involved backend changes to prompt generation and frontend changes to the UI.

## Implementation Details

### Backend
-   Modified `keepa_deals/ava_advisor.py`:
    -   Added `MENTOR_PERSONAS` dictionary defining role, focus, tone, and style for each mentor.
    -   Updated `generate_ava_advice` to accept a `mentor_type` argument.
    -   Updated prompt construction to use the selected persona's attributes.
    -   Fixed a bug where the code referenced the deprecated `Best_Price` field instead of `Price_Now`.
-   Modified `wsgi_handler.py`:
    -   Updated `/api/ava-advice/<string:asin>` endpoint to accept `mentor` query parameter.

### Frontend
-   Modified `templates/dashboard.html`:
    -   Added HTML structure for the mentor selector (icons list) in the advice header.
    -   Added CSS styles for layout, icons, and active states.
    -   Implemented JavaScript logic:
        -   State management using `localStorage` (`ava_mentor`).
        -   UI updates (highlight active mentor, update main header icon).
        -   Dynamic fetching of advice when mentor changes.

## Challenges
-   **Missing Assets:** The specified mentor icons (`AvaCFO.png`, etc.) were missing from the `static/` directory in the sandbox. Created placeholders (copies of `AgentArbitrage.png`) to enable frontend verification.
-   **Database State:** The sandbox database was empty or missing the schema. Created a script `setup_test_db.py` to initialize a test schema and insert dummy data for verification.
-   **Deprecated Fields:** Discovered `ava_advisor.py` was using `Best_Price` which caused advice generation to return empty/error values ("-"). Patched it to use `Price_Now` with a fallback.
-   **Frontend Verification:** Used Playwright to verify the UI. Required creating a custom login script that handled the hidden login form logic on the index page.

## Success Status
-   **Backend Verification:** Confirmed via `test_mentor_api.py` that different mentors return distinctly different advice styles.
-   **Frontend Verification:** Confirmed via Playwright screenshots that the UI matches the mockup specs (layout, active states) and interactions work correctly.
-   **Code Review:** Passed with minor notes on standardizing transparency behavior (Active=100%, Inactive=50%).

## Next Steps
-   Ensure the actual mentor icon assets are deployed to `static/` in the production environment.
