# Dev Log: Dashboard Filter Fixes and Optimal Tuning
**Date:** 2026-02-20
**Task:** Fix Dashboard Filter Logic, crashes, and tune "Optimal Filters" to be useful.

## Overview
The goal was to stabilize the Dashboard, which was suffering from JavaScript crashes (`updateResponsiveLayout` undefined), incorrect deal counting, and filtering logic that returned 0 results—specifically the "Optimal Filters" button.

## Challenges Faced

1.  **Data Type Mismatch in SQLite:**
    *   Columns like `Deal_Trust` and `Percent_Down` were stored as TEXT (e.g., "75%", "15.00") but filtered as numbers in SQL. This caused filters like `>= 70` to fail silently or behave unpredictably.
    *   `Profit` and `All_in_Cost` contained currency symbols (`$`), causing mathematical operations (ROI calculation) to return 0 or NULL, effectively hiding all profitable deals.

2.  **"Optimal Filters" Too Strict:**
    *   The initial definition of "Optimal" (Rank < 250k, ROI > 35%, Trust > 70%) was too aggressive for the current database state, resulting in 0 deals found.
    *   Specifically, the `Deal_Trust` score is often `NULL` or `'-'` for new deals awaiting analysis. Enforcing `>= 70%` hid these potential opportunities.

3.  **Frontend Crashes:**
    *   The `dashboard.html` template referenced functions (`renderPagination`, `updateResponsiveLayout`) that were missing from the inline script, causing the table render to abort.

## Resolution

1.  **Robust SQL Sanitization (`wsgi_handler.py`):**
    *   Implemented on-the-fly casting and sanitization in SQL queries:
        ```sql
        CAST(REPLACE(REPLACE("Profit", '$', ''), ',', '') AS REAL)
        CAST("Deal_Trust" AS INTEGER)
        ```
    *   This ensures filtering works correctly regardless of whether the data is "dirty" text or clean numbers.

2.  **Tuned "Optimal Filters" (`dashboard.html`):**
    *   Collaborated with the user to find a "Sweet Spot" that yields results without sacrificing quality.
    *   **New Settings:**
        *   **Rank:** Raised to **1,000,000** (was 250k) to include viable long-tail books.
        *   **ROI:** Lowered to **20%** (was 35%).
        *   **Profit:** Kept at **$4**.
        *   **Drops (30d):** Increased to **2** (was 1) to ensure demand.
        *   **Deal Trust:** **Restored to 70%** but code logic handles missing values safely.
        *   **Seller Trust:** Added **5/10**.
        *   **Below Avg:** Added **10%**.

3.  **Frontend Fixes:**
    *   Implemented the missing pagination and layout functions.
    *   Added robust error handling to `fetchDeals`.
    *   Ensured the "Deals Found" counter updates dynamically.

## Outcome
The Dashboard is now stable, filters work as expected against real-world data, and the "Optimal" button provides a useful starting point rather than an empty table. Future tuning is recommended once the database exceeds 5,000 deals.
