1. **Part 1: Unify Pagination**
   - Extract the pagination logic from `templates/dashboard.html` into a shared utility function `renderSharedPagination` in `static/js/pagination.js`.
   - Update `templates/dashboard.html` to include `static/js/pagination.js` and use `renderSharedPagination`. Note that `dashboard.html` pagination has an API with `pagination.total_pages` and `pagination.current_page` and invokes `fetchDeals(page, currentSort.by, currentSort.order)`.
   - Update `templates/tracking.html` to include `static/js/pagination.js` and use `renderSharedPagination`. In `tracking.html`, the API returns `pagination.pages` and `pagination.page`, so the shared component will handle both formats. Replace `renderPaginationControls`.
   - Ensure the scroll behavior works correctly for both pages.

2. **Part 2: Active Inventory Button Re-labeling Proposals**
   - I will pause and present proposals to the user for the three buttons on the Active Inventory tab:
     - "Sync from Amazon" -> Proposal: "Sync FBA Inventory" or "Refresh Amazon Data"
     - "Download Missing Costs CSV" -> Proposal: "Export Missing Costs" or "Download Missing"
     - "Upload Costs (CSV)" -> Proposal: "Import Costs" or "Upload CSV"
   - I will ask for Tim's approval on the new labels and whether to move them.

3. **Part 3: CSV Button Demotion**
   - Wait for user response. After approval:
   - Hide the current top-level "Download" and "Upload" buttons.
   - Add a "Bulk edit via CSV" small text link below the table.
   - Create a disclosure widget (or inline reveal) that displays the new "Export" and "Import" buttons when clicked.
   - Any new styling will go into `static/global.css`.

4. **Complete Pre Commit Steps**
   - Execute `./run_tests.sh` to make sure proper testing, verifications, reviews and reflections are done.
