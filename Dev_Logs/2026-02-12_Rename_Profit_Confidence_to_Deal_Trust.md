# Dev Log: Rename Profit Confidence to Deal Trust

**Date:** 2026-02-12
**Task:** Rename UI Labels & Code References ("Profit Confidence" -> "Deal Trust")
**Status:** Success

## Overview
The goal of this task was to rename the metric "Profit Confidence" to "Deal Trust" across the entire application stack to better reflect its semantic meaning (trust in the deal's viability based on sales correlation, rather than just profit certainty). This required updates to the User Interface, Backend Logic, Database Schema, and Documentation.

## Changes Implemented

### 1. User Interface (Frontend)
-   **File:** `templates/dashboard.html`
-   **Filter Panel:** Renamed the label "Min. Profit Trust:" to **"Min. Deal Trust:"**.
-   **Table Header:** Renamed the column header under "Trust Rates" from "Est." to **"Deal"**.
-   **Logic:** Updated JavaScript sliders and event listeners to use `dealTrustSlider` and send the `deal_trust_gte` parameter to the API.

### 2. Backend Logic & API
-   **File:** `keepa_deals/stable_calculations.py`
    -   Renamed `profit_confidence(product)` function to `deal_trust(product)`.
    -   Updated the return key to `{'Deal Trust': ...}`.
-   **File:** `keepa_deals/processing.py`
    -   Updated logic to check and assign `row_data['Deal Trust']`.
    -   Updated fallback logic (Silver Standard) to downgrade `Deal Trust` instead of `Profit Confidence`.
-   **File:** `keepa_deals/field_mappings.py`
    -   Updated function imports and the `FUNCTION_LIST` to use `deal_trust`.
-   **File:** `wsgi_handler.py`
    -   Updated `api_deals` and `deal_count` endpoints to accept `deal_trust_gte` as a filter parameter.
    -   Updated SQL query construction to filter against the `"Deal_Trust"` column.

### 3. Database & Schema Migration
-   **Challenge:** Changing a column name in SQLite and preserving existing data for thousands of records without external migration tools (like Alembic) required a careful approach.
-   **Solution:** Implemented a "Lazy Migration" inside `keepa_deals/db_utils.py` -> `create_deals_table_if_not_exists`.
    -   **Schema Update:** The system automatically adds the missing `"Deal_Trust"` column based on the updated `headers.json`.
    -   **Data Preservation:** Added a specific SQL block that checks if both columns exist. If they do, it runs:
        ```sql
        UPDATE deals 
        SET "Deal_Trust" = "Profit_Confidence" 
        WHERE "Deal_Trust" IS NULL AND "Profit_Confidence" IS NOT NULL
        ```
    -   This ensures that upon the first run after deployment, all existing `Profit_Confidence` scores are safely copied to `Deal_Trust`.

### 4. Configuration & Documentation
-   **File:** `keepa_deals/headers.json`
    -   Renamed "Profit Confidence" to "Deal Trust".
-   **Documentation:**
    -   Updated `Data_Logic.md`, `Dashboard_Specification.md`, and `Feature_Deals_Dashboard.md` to reflect the new terminology.

## Verification
-   **Unit Tests:** Created `tests/test_deal_trust.py` to verify the renaming of the calculation logic. Tests passed.
-   **Frontend:** Verified via Playwright screenshot (`verification/dashboard_ui.png`) that the labels "Min. Deal Trust" and "Deal" appear correctly in the dashboard.

## Conclusion
The refactoring was successful. The system now consistently uses "Deal Trust" from the database layer up to the UI, with a safe migration path for existing data.
