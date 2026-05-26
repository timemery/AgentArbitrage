# 2026-05-26: Unify Pagination & Demote CSV Buttons

## Task Overview
The goal of this task was to address three related UI changes on the Tracking page's Active Inventory and Sales & Profit tabs:
1. Unify the pagination component so that the Tracking page uses the same styled, numbered pagination as the Dashboard.
2. Propose and implement new, clearer labels for the three primary buttons on the Active Inventory tab ("Sync from Amazon", "Download Missing Costs CSV", "Upload Costs (CSV)").
3. Demote the CSV-related buttons behind a less prominent text link to clean up the primary UI.

## Challenges & Solutions

### Pagination Unification
- **Challenge**: The Dashboard had an inline pagination rendering function that was tightly coupled to its specific data flow (`total_pages`, `current_page`, `fetchDeals`). The Tracking page had its own inline function (`renderPaginationControls`) that handled a different API format (`pages`, `page`, and custom fetch callbacks).
- **Solution**: Extracted the logic into a shared utility `renderSharedPagination` inside `static/js/pagination.js`. This function accepts an options-like parameter list to gracefully handle both API data formats and dynamically triggers the appropriate callback function (`fetchDeals`, `fetchActiveInventory`, or `fetchSalesHistory`).

### Button Re-labeling & CSV Demotion
- **Challenge**: The original button labels were overly technical and cluttered the top action bar.
- **Solution**: After consulting the user, the buttons were renamed to "Sync FBA Inventory" (kept as a top-level button), "Export Missing Costs", and "Import Costs".
- **Demotion**: Implemented an expandable "Bulk edit via CSV" text link with a `▼` / `▲` toggle icon beneath the Active Inventory table. The new Export and Import buttons were placed inside this collapsible container, significantly tidying up the primary view while keeping the tools accessible.

## Success Status
**Success.** All pagination components share a unified design, and the Active Inventory UI is cleaner and more intuitive. The visual changes were fully verified with Playwright tests checking both the collapsed and expanded states of the demoted CSV container.
