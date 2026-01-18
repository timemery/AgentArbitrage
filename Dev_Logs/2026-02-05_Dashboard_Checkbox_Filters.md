# Dev Log: Dashboard Checkbox Filters & Styling Refinement

## Task Description
Implemented "Hide Gated" and "Hide AMZ Offers" checkbox filters in the Dashboard Filter Panel and refined the UI styling based on feedback regarding button sizes, font weights, and panel dimensions.

## Changes Implemented

### 1. Backend Logic (`wsgi_handler.py`)
-   Updated `api_deals` and `deal_count` to support `hide_gated` and `hide_amz` query parameters.
-   **Hide Gated Logic**:
    -   Excludes deals where `user_restrictions.is_restricted = 1`.
    -   Includes deals where status is NULL (Pending), 0 (Not Restricted), or -1 (Error).
    -   **Important**: In `deal_count`, the filter and its associated `JOIN` are strictly conditioned on `is_sp_api_connected`, preventing server crashes when disconnected.
-   **Hide AMZ Logic**:
    -   Excludes deals where the `AMZ` column contains the warning icon ('⚠️').

### 2. Frontend HTML (`templates/dashboard.html`)
-   Added `.checkboxes-wrapper` containing two `.checkbox-item` divs for the new filters.
-   Updated `getFilters()` JavaScript function to include `hide_gated=1` and `hide_amz=1` in the API request params when checked.
-   Updated `btnReset` event listener to uncheck these boxes visually.

### 3. Frontend CSS (`static/global.css`)
-   **Checkboxes**:
    -   Styled with `.custom-checkbox`.
    -   Size: 18x18px.
    -   Border: 2px solid `#7397c2`.
    -   Background: `#566e9e` (filled in both checked and unchecked states).
    -   Checkmark: CSS pseudo-element (`::after`) creating a white checkmark.
-   **Slider Readouts**:
    -   Updated `.slider-value-readout` to use font-weight `700` (Bold).
-   **Action Buttons**:
    -   Updated `.filter-btn` dimensions to `56px` width and `32px` height to account for the 2px border (inner content 52x28).
-   **Filter Panel Height**:
    -   Increased `.filter-panel-open` height to `102px` to accommodate the stacked buttons and provide sufficient vertical padding.

## Verification
-   **Backend**: Verified via regression test script (`verify_regression.py`) that `deal_count` handles disconnected state gracefully without crashing.
-   **Frontend**: Verified via Playwright script (`verify_dashboard.py`) and visual inspection of the screenshot (`dashboard_filters.png`), confirming correct placement, sizing, and styling.
