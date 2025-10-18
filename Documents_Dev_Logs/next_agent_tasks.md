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

### **Task 3: Restore AI-Powered Seasonality**

**Goal:** Re-implement the AI-powered seasonality and sells period calculations.

**Files to Modify:** `keepa_deals/seasonality_classifier.py`

**Steps:**

1.  **Restore keyword heuristics:** Ensure the `classify_seasonality` function correctly uses the `seasonal_config.py` file to check for keyword matches in the product's title and categories.
2.  **Restore AI fallback:** Re-implement the logic to query the external XAI model if no keyword match is found.
3.  **Restore `get_sells_period`:** Ensure the `get_sells_period` function correctly maps the season to a human-readable date range.

---

### **Task 4: Implement External Keepa Query**

**Goal:** Allow an administrator to change the Keepa deal-finding query without modifying the code.

**Files to Modify:** `keepa_deals/keepa_api.py`, `wsgi_handler.py`, and a new admin template.

**Steps:**

1.  **Create an admin page:** Create a new, simple HTML template for the admin page with a `<textarea>` for the Keepa query JSON.
2.  **Create a new route:** In `wsgi_handler.py`, create a new route (e.g., `/admin/settings`) that handles both `GET` and `POST` requests for the new admin page. The `POST` handler should save the submitted JSON to a new file (e.g., `keepa_query.json`).
3.  **Modify `fetch_deals_for_deals`:** In `keepa_api.py`, modify the `fetch_deals_for_deals` function to:
    *   Check for the existence of `keepa_query.json`.
    *   If it exists, use the query from the file.
    *   If not, use the current hardcoded default query.

---

### **Task 5: Final Verification and Cleanup**

**Goal:** Perform a full, end-to-end test of the dashboard to ensure all functionality is restored and working as expected.

**Steps:**

1.  **Run a full scan:** Trigger a new data scan to populate the database with fresh data.
2.  **Verify all columns:** Meticulously check each column on the dashboard against the logic defined in `data_logic.md`.
3.  **Test all features:** Test the sorting, filtering, and keyword search functionality.
4.  **Test the new admin feature:** Test the ability to update the Keepa query and see the results in a new scan.
5.  **Remove any debugging code:** Remove any temporary logging or debugging code that was added during the restoration process.
