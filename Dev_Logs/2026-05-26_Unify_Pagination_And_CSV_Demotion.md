# 2026-05-26: Unify Pagination & Demote CSV Buttons

## Task Overview
The goal of this task was to address three related UI changes on the Tracking page's Active Inventory and Sales & Profit tabs, and a follow-up refinement:
1. Unify the pagination component so that the Tracking page uses the same styled, numbered pagination as the Dashboard.
2. Propose and implement new, clearer labels for the three primary buttons on the Active Inventory tab ("Sync from Amazon", "Download Missing Costs CSV", "Upload Costs (CSV)").
3. Demote the CSV-related buttons behind a less prominent text link to clean up the primary UI, and adjust their placement to balance the layout.
4. Fix a scroll-offset bug triggered when navigating via the pagination controls that caused the table header to be obscured by sticky elements.

## Challenges & Solutions

### Pagination Unification
- **Challenge**: The Dashboard had an inline pagination rendering function tightly coupled to its specific data flow (`total_pages`, `current_page`, `fetchDeals`). The Tracking page had its own inline function (`renderPaginationControls`) handling a different API format (`pages`, `page`, and custom fetch callbacks).
- **Solution**: Extracted the logic into a shared utility `renderSharedPagination` inside `static/js/pagination.js`. This function gracefully handles both API data formats and dynamically triggers the appropriate callback function (`fetchDeals`, `fetchActiveInventory`, or `fetchSalesHistory`). Dead code was subsequently removed from the templates.

### Pagination Scroll Bug Fix
- **Challenge**: Clicking a pagination button scrolled the table into view using `scrollIntoView()`, which didn't account for the newly added sticky headers and tab navigation, resulting in the top rows being hidden beneath the header.
- **Solution**: Modified the scroll logic in `static/js/pagination.js` to explicitly calculate the element's position using `getBoundingClientRect().top + window.scrollY` and subtracted a fixed offset (`140px`) to account for the sticky elements before executing `window.scrollTo()`.

### Button Re-labeling & CSV Demotion
- **Challenge**: The original button labels were overly technical and cluttered the top action bar. The new drop-down container also initially experienced CSS issues where the button text wrapped awkwardly due to absolute positioning constraints.
- **Solution**:
  - Buttons were renamed to "Sync FBA Inventory", "Download Missing Costs", and "Upload Updated Costs" based on user feedback to clarify intent.
  - Implemented an expandable "Bulk edit via CSV" text link with a `▼` / `▲` toggle icon.
  - Positioned the toggle link on the same row as the "Sync FBA Inventory" button (using `justify-content: space-between` for balance).
  - Resolved the CSS wrapping issue by adding `white-space: nowrap;` and `width: max-content;` to the `.csv-actions-container` class in `static/global.css`.

## Success Status
**Success.** All pagination components share a unified design and function correctly with sticky headers. The Active Inventory UI is cleaner and more intuitive, with CSV tools neatly tucked away but easily accessible. Visual changes were verified using Playwright headless browser tests.
