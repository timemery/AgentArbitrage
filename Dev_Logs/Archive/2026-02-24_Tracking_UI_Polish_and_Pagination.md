# Dev Log: Tracking UI Polish & Pagination (2026-02-24)

## Overview
This task focused on the final polish and optimization of the "Profit & Inventory Tracking" feature. The primary goals were to improve the scalability of the backend by introducing pagination for active inventory and sales history, and to align the UI of the Tracking page with the main Dashboard's visual style (dark theme, rounded tables, tooltips).

## Changes Implemented

### Backend Refactoring (`wsgi_handler.py`)
-   **New Endpoints:** Replaced the monolithic `/api/inventory` GET route with three specialized, paginated endpoints:
    -   `/api/tracking/potential` (GET): Returns potential buys (unpaginated, typically small list).
    -   `/api/tracking/active` (GET): Accepts `page` and `limit` query parameters. Returns `{ data: [...], pagination: { total, page, limit, pages } }`.
    -   `/api/tracking/sales` (GET): Accepts `page` and `limit`. Returns sales history with pagination metadata.
-   **Efficiency:** Queries now use `LIMIT` and `OFFSET` to prevent loading thousands of rows into memory, crucial for accounts with large sales histories.

### Frontend Updates (`templates/tracking.html`)
-   **Pagination Controls:** Implemented `renderPaginationControls` function to generate "Previous" / "Next" buttons dynamically based on API response.
-   **Dashboard Styling:** Applied the `.strategies-table` class structure to match the main Dashboard.
    -   Header: Dark blue background (`#1f293c`), rounded top corners.
    -   Cells: Transparent/Dark background, white text.
    -   Hover Effects: Rows highlight on mouseover (`#304163`).
-   **Tooltips:** Added CSS-only tooltips (`.tooltip-header`) for columns like "Qty" and "Sale Price (Gross)" to clarify data definitions without cluttering the UI.

### Verification
-   **Unit Tests:** Created `tests/test_tracking_pagination.py` to verify the new API endpoints correctly handle page limits and offsets.
-   **Visual Verification:** Used a Playwright script (`verification/verify_tracking.py`) to log in, navigate to the Tracking page, and capture screenshots of the paginated tables.

## Challenges & Solutions

### 1. Playwright Selector Strictness
-   **Issue:** The verification script failed when clicking the "Log In" button because `page.get_by_text("Log In")` matched multiple elements (both the toggle button and the form submit button), triggering a strict mode violation.
-   **Solution:** Switched to a more specific CSS selector: `page.locator(".login-button")` for the toggle, and `page.get_by_role("button", name="Log In")` for the form submission. This highlights the importance of using unique classes or IDs for interactive elements to facilitate testing.

### 2. Styling Consistency
-   **Issue:** The Tracking page initially used default browser table styles which clashed with the dark theme of the application.
-   **Solution:** We imported the `strategies-table` styles from the Dashboard but had to wrap them in a `<style>` block within `tracking.html` (temporarily) or verify they were in `global.css`. We ultimately ensured the styles were consistent by applying the same class names and verifying visual output.

## Success Status
**Success.** The Tracking page now loads data efficiently via pagination, looks consistent with the rest of the application, and passes both automated API tests and visual inspection.

## Key Learnings
-   **Pagination is Essential:** For "Sales History", attempting to load all records at once is not viable. Splitting this early prevents future performance bottlenecks.
-   **CSS Tooltips:** Using pure CSS tooltips (`.tooltip-header:hover .tooltip-text`) is a lightweight and reliable way to add context to table headers without JavaScript libraries.
-   **Test Selectors:** When writing E2E tests for this app, be aware that "Log In" appears multiple times. Always prefer unique IDs or specific roles.
