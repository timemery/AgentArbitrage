# Dev Log: Dashboard Checkbox Filters Implementation

## Task Description
Added "Hide Gated" and "Hide AMZ Offers" checkbox filters to the Dashboard Filter Panel. These filters allow users to exclude restricted items and items where Amazon is a competing seller, respectively.

## Changes Implemented

### 1. Backend Logic (`wsgi_handler.py`)
-   Updated `api_deals` to accept `hide_gated` and `hide_amz` query parameters.
-   Updated `deal_count` to accept `hide_gated` and `hide_amz` query parameters.
-   **Hide Gated Logic**:
    -   Excludes deals where `user_restrictions.is_restricted = 1`.
    -   Includes deals where status is NULL (Pending), 0 (Not Restricted), or -1 (Error).
    -   **Important**: In `deal_count`, the filter is conditionally applied *only* if `is_sp_api_connected` is true, ensuring that the `JOIN` with `user_restrictions` exists before referencing its columns. This prevents server crashes when not connected.
-   **Hide AMZ Logic**:
    -   Excludes deals where the `AMZ` column contains the warning icon ('⚠️').

### 2. Frontend HTML (`templates/dashboard.html`)
-   Added `.checkboxes-wrapper` containing two `.checkbox-item` divs for the new filters.
-   Updated `getFilters()` JavaScript function to include `hide_gated=1` and `hide_amz=1` in the API request params when checked.
-   Updated `btnReset` event listener to uncheck these boxes visually.

### 3. Frontend CSS (`static/global.css`)
-   Implemented custom checkbox styling to match the mockup:
    -   Size: 18x18px.
    -   Border: 1px solid `#7397c2`.
    -   Checked Background: `#566e9e` (matches slider thumb).
    -   Checkmark: CSS pseudo-element (`::after`) creating a white checkmark.
    -   Hover Effect: Border color change to `#a3aec0`.
    -   Label: Open Sans Bold 12px, White (`#ffffff`).

## Verification
-   **Backend Logic**: Verified via a regression test script (`verify_regression.py`) ensuring `deal_count` does not crash when `hide_gated` is used while disconnected from SP-API.
-   **Frontend UI**: Verified via Playwright script (`verify_dashboard.py`) and visual inspection of the screenshot, confirming correct placement and visibility.

## Key Learnings
-   **SQL Safety**: When adding filters that rely on a `JOIN` table (like `user_restrictions`), the `WHERE` clause must be strictly conditioned on the presence of that `JOIN`. Failing to do so (adding the WHERE clause blindly based on the filter param) causes a "no such column" error if the JOIN logic was skipped (e.g., due to disconnected state).
