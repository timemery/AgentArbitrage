# Task: Layout Tidy Up (Non-Dashboard Pages)

**Date:** 2026-01-21
**Status:** Successful

## Overview
The objective of this task was to standardize the layout and styling of all application pages *except* the Dashboard (`/dashboard`). The goal was to eliminate the "random" look of these pages and enforce a strict design system based on a provided mockup.

**Key Requirements:**
*   **Containerization:** All content must be centered in a container with a max-width of 950px (750px for Settings).
*   **Typography:** Strict use of 'Open Sans' for headers and body text.
*   **Styling:** Implementation of specific "blue" button styles consistent with the Dashboard Filter Panel.
*   **Spacing:** A fixed top offset of 135px from the browser top to the start of the page content.
*   **Scope:** `deals.html`, `settings.html`, `guided_learning.html`, `strategies.html`, and `intelligence.html`.

## Challenges Faced

1.  **Environmental Instability:**
    *   The initial environment setup required installing missing dependencies (`flask`, `httpx`, `redis`, `celery`, `keepa`, `openai`, `beautifulsoup4`, `boto3`, `youtube_transcript_api`) to successfully run the verification scripts.
    *   Ensuring the Flask application could start without errors (due to missing imports in `wsgi_handler.py`) was a prerequisite for visual verification.

2.  **Visual Verification without live UI:**
    *   Since I cannot see the browser, I relied on Playwright to generate screenshots.
    *   Navigating to protected routes (`/deals`, `/settings`) required handling authentication within the script.
    *   The `tester` account (Admin role) redirects to `/guided_learning` instead of `/dashboard` upon login, which required adjusting the verification script's wait conditions.

3.  **Strict Isolation:**
    *   A major constraint was to *not* affect the Dashboard page. This meant global style changes had to be carefully scoped. We achieved this by introducing a new `.tidy-container` class rather than modifying generic global selectors that might bleed into the Dashboard.

## Actions Taken

1.  **CSS Architecture (`static/global.css`):**
    *   Created a `.tidy-container` class with `max-width: 950px`, `margin: 1px auto 40px`, and `padding: 40px`.
    *   Created a `.tidy-container.settings-width` variant with `max-width: 750px` specifically for the Settings page.
    *   Defined `.tidy-header` and `.tidy-text` classes to enforce 'Open Sans' typography and specific colors (`#ffffff` for headers, `#a3aec0` for text).
    *   Defined `.tidy-button` to replicate the "blue button" style (Background `#566e9e`, Border `#7397c2`, Radius 8px).
    *   Defined `.tidy-card` for boxed content areas and `.tidy-code-block` for the Keepa query editor.

2.  **Template Refactoring:**
    *   **`templates/deals.html`:** Replaced the old `.settings-container` with `.tidy-container`. Standardized the "Keepa Deals API Query" section and "Artificial Backfill Limiter" card using the new classes.
    *   **`templates/settings.html`:** Applied `.tidy-container.settings-width`. Updated the form grid and input styles to match the new design. Maintained specific button semantic colors (e.g., Green for "Save", Yellow for "Connect") while adopting the `.tidy-button` shape/font.
    *   **`templates/guided_learning.html`:** Wrapped the learning form in `.tidy-container` and `.tidy-card`.
    *   **`templates/strategies.html`:** Wrapped the strategy table in `.tidy-container` and `.tidy-card`. Styled the table headers and cells to match the `.tidy-text` standards.
    *   **`templates/intelligence.html`:** Wrapped the content in `.tidy-container` and `.tidy-card`.

3.  **Verification:**
    *   Installed necessary Python dependencies to run the Flask app locally.
    *   Wrote and executed a Playwright script (`verify_styles.py`) that logged in as an admin, navigated to all modified pages, and captured screenshots.
    *   Verified that the Dashboard page remained unaffected by these changes.

## Outcome
The task was **successful**. The non-dashboard pages now share a cohesive, professional layout that aligns with the strict design guidelines provided. The code is modular (using utility-like `.tidy-*` classes), making it easy to maintain or extend to future pages without risking regression on the critical Dashboard interface.
