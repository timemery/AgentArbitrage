# Task List for Next Agent: Restoring Dashboard Functionality

This document outlines the tasks required to repair and restore the full functionality of the Agent Arbitrage deals dashboard. The tasks should be completed in the order listed to ensure that dependencies are handled correctly.

**Reference Document:** Before starting, please thoroughly review `Documents_Dev_Logs/data_logic.md`. This document contains the detailed logic and expected behavior for each column and feature.

---

### **Task 1: Restore Core Data Processing Logic**

**Goal:** Reinstate the original, robust data processing pipeline from the `AgentArbitrage-before_persistent_db` version of the codebase.

**Files to Modify:** `keepa_deals/Keepa_Deals.py`

**Steps:**

1.  **Replace the main processing loop:** The current `run_keepa_script` function in `keepa_deals/Keepa_Deals.py` is missing the sequential, multi-stage processing logic. Replace the current processing section with the series of decoupled loops from the older version of the file. This includes:
    *   The initial loop that uses `FUNCTION_LIST`.
    *   The decoupled seller information processing loop.
    *   The business logic calculations loop.
    *   The new analytics calculations loop.
    *   The seasonality classification loop.
2.  **Ensure data consistency:** Make sure that the `all_fetched_products_map` is correctly populated and that the data is merged correctly before the processing loops begin.
3.  **Verify data flow:** Add logging to confirm that each loop is receiving the correct data and that the `row_data` dictionary is being correctly updated at each stage.

---

### **Task 2: Fix Database Schema and Data Types**

**Goal:** Correct the database schema to ensure that numeric columns are stored and sorted correctly.

**Files to Modify:** `keepa_deals/db_utils.py` (or the `save_to_database` function if it's still in `Keepa_Deals.py`).

**Steps:**

1.  **Modify type inference:** The logic that creates the database table incorrectly types the sales rank columns as `TEXT`. Modify the type inference logic to correctly identify `Sales Rank - Current` and `Sales Rank - 365 days avg.` as `INTEGER`.
2.  **Handle numeric parsing:** Ensure that the `save_to_database` function correctly parses and cleans numeric values (removing commas, currency symbols) before insertion.

---

### **Task 3: Restore and Enhance Core Analytics**

**Goal:** Restore the sophisticated calculation logic for "List at", "Season", and "Trend" columns as defined in `data_logic.md`.

**Files to Modify:** `keepa_deals/stable_calculations.py`, `keepa_deals/new_analytics.py`, `keepa_deals/seasonality_classifier.py`

**Steps:**

1.  **"List at" Calculation (`stable_calculations.py`):**
    *   Implement the `mode` (most frequent price) calculation for the peak inferred sale price.
    *   Add a call to the XAI model to act as a final verification step.
2.  **"Season" Calculation (`seasonality_classifier.py`):**
    *   Modify the `classify_seasonality` function to first analyze the dates of the inferred peak/trough sale prices.
    *   Use this date analysis, along with product metadata, as the input for the final AI reasoning step.
3.  **"Trend" Calculation (`new_analytics.py`):**
    *   Rewrite the `get_trend` function to use both "NEW" and "USED" price data.
    *   Implement the dynamic sample size logic based on the 365-day average sales rank tiers.

---

### **Task 4: Correct Business Logic Formulas**

**Goal:** Ensure all financial calculations are performed correctly and in the proper order.

**Files to Modify:** `keepa_deals/business_calculations.py`

**Steps:**

1.  **Update `All-in Cost`:** Modify the `calculate_all_in_cost` function to correctly calculate the `Referral Fee` based on the `"List at"` price, and then include it in the final cost calculation.
2.  **Update `Min. List Price`:** Ensure the formula for `Min. List Price` is correct and update the comments to reflect its purpose for repricing software.
3.  **Verify `Now` price:** In `seller_info.py`, ensure the logic for the "Now" price always returns a value and does not filter out sellers.

---

### **Task 5: Final Verification and Cleanup**

**Goal:** Perform a full, end-to-end test of the dashboard to ensure all functionality is restored and working as expected.

**Steps:**

1.  **Run a full scan:** Trigger a new data scan to populate the database with fresh data.
2.  **Verify all columns:** Meticulously check each column on the dashboard against the logic defined in the updated `data_logic.md`.
3.  **Test all features:** Test the sorting, filtering, and keyword search functionality.
4.  **Remove any debugging code:** Remove any temporary logging or debugging code that was added during the restoration process.
