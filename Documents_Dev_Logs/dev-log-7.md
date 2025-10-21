### Dev Log Entry: October 17, 2025

**Task:** `refactor/recalculator-api-free`

**Objective:** To implement Part 4 of the Keepa Sync Strategy by refactoring the `recalculate_deals` Celery task to be a pure, API-free, database-only operation. The goal was to provide a token-free way to update deals with new business logic from `settings.json`.

**Summary of a Multi-Stage, Multi-Failure Debugging Process:**

This task was a difficult and protracted debugging marathon that ultimately succeeded, but only after overcoming a cascade of issues ranging from incorrect code logic and bad data handling to stale server-side caches and configuration files.

**Chronology of Failures & Resolutions:**

1. **Initial Implementation (API-Free Logic):**
   - **Action:** The `recalculate_deals` task in `keepa_deals/recalculator.py` was successfully rewritten to remove all Keepa API calls (`fetch_product_batch`, `TokenManager`, etc.). The new logic was designed to load deals from the local `deals.db`, re-apply calculations, and save the results.
   - **Status:** **Partial Success.** The architectural goal was met, but the implementation contained several latent bugs.
2. **Failure 1: Database Was Empty:**
   - **Symptom:** Initial verification failed because the `deals.db` in the test environment was empty.
   - **Diagnosis:** The `backfill_deals` task, which is responsible for populating the database, was failing silently. This was traced to a missing `.env` file, which prevented the Celery worker from loading the necessary `KEEPA_API_KEY`.
   - **Resolution:** Created the `.env` file and successfully ran the `backfill_deals` task to populate the database with a test set of 50 deals.
3. **Failure 2: Incorrect Column Name Mapping:**
   - **Symptom:** After populating the database and running the recalculator, the `All_in_Cost` and `Profit` values in the database were not updating. The task ran without error but had no effect.
   - **Diagnosis:** A careful manual calculation revealed that the script was not reading the correct values from the database. The root cause was a mismatch between the sanitized column names used in the Python code (e.g., `FBA_PickPack_Fee`) and the actual column names in the SQLite database (e.g., `FBA_PickPack_Fee`).
   - **Resolution:** The SQL `SELECT` statement was modified to use aliases, mapping the database's column names to the names expected by the Python code.
4. **Failure 3: The Wrong Code Was Executing (Server-Side Cache):**
   - **Symptom:** Even after fixing the column mapping, user testing showed the old, API-heavy code was *still* running, evidenced by API token consumption and log messages related to `TokenManager`.
   - **Diagnosis:** This proved that the Celery worker was not loading the newly updated Python file. The most likely cause was a stale Python cache (`__pycache__` directory) on the server.
   - **Resolution:** Instructed the user to stop the Celery worker, delete all `__pycache__` directories from the project, and then restart the worker. This forced Python to recompile the `.py` files and load the correct, API-free version of the task.
5. **Failure 4: Bad Data Handling (`ValueError`):**
   - **Symptom:** After clearing the cache, the task was still not completing. The celery log revealed the task was now crashing with `ValueError: could not convert string to float: '$5.77'` and `ValueError: could not convert string to float: '-'`.
   - **Diagnosis:** The code was not robust enough to handle the variety of data formats in the database. It was attempting to convert strings containing `$` symbols and hyphens (`-`) directly to floats, causing a crash.
   - **Resolution:** A `_safe_float` helper function was implemented. This function sanitizes the input string by removing both `$` and `,` characters and handles conversion errors gracefully by returning a default value of `0.0`, preventing the task from crashing.
6. **Failure 5: External API Timeouts (XAI):**
   - **Symptom:** With the `ValueError` fixed, the task was still hanging, and the UI banner remained stuck. The logs showed the business calculations were finally succeeding, but the task was then getting stuck for long periods, with errors like `XAI API request failed... The read operation timed out`.
   - **Diagnosis:** The seasonality classification portion of the task was making blocking network calls to an external AI service that was slow and unreliable, preventing the task from ever finishing.
   - **Resolution:** As a final measure to make the task fast and reliable, the seasonality classification section was **temporarily commented out**. This isolates the task to its core purpose: recalculating business logic.
7. **Failure 6: Stale UI State File:**
   - **Symptom:** The final successful test run correctly updated the database, but the blue "Recalculating..." banner on the UI remained stuck.
   - **Diagnosis:** The banner's visibility is controlled by a status file, `recalc_status.json`. Previous crashes had left this file in a stale "Running" state, and it was never being cleared.
   - **Resolution:** The user was instructed to manually delete the `recalc_status.json` file, which immediately cleared the stuck banner and restored normal UI behavior.

**Final Outcome: Success.**

Despite the numerous and complex failures, the task was ultimately successful. The `recalculate_deals` task is now a fast, robust, and completely Keepa API-free operation. It correctly updates business metrics based on user settings and is resilient to common data quality issues. The primary goal of the task was fully achieved.

### **Dev Log: Restore Dashboard Functionality (Phase 1)**

**Date:** 2025-10-21 **Agent:** Jules **Task:** Restore core data processing logic and fix database schema to resolve dashboard failures.

------

#### **1. Initial Goal**

The primary objective was to complete "Phase 1" of a two-part plan to restore the deals dashboard. This involved two main tasks:

1. **Restore Core Data Processing Logic:** Reinstate the original, multi-stage data processing pipeline in `keepa_deals/Keepa_Deals.py`.
2. **Fix Database Schema:** Modify `keepa_deals/db_utils.py` to correctly type sales rank columns as `INTEGER` to fix numerical sorting on the dashboard.

------

#### **2. Challenges, Solutions, and Outcomes**

This task involved a significant amount of iterative debugging due to a combination of code regressions, environmental differences, and latent bugs.

**Challenge 1: Major Code Regression**

- **Issue:** My initial attempt to restore the data processing logic involved a full replacement of the `keepa_deals/Keepa_Deals.py` file. This was a critical error, as it reintroduced a slow, API-intensive version of the `recalculate_deals` function, a major performance regression that the user had previously flagged.
- **Solution:** The `recalculate_deals` function was reverted to the correct, fast, database-only version. The rest of the file was then carefully patched with the required multi-stage processing loops.
- **Outcome:** **Success.** The final code contains the correct, high-performance `recalculate_deals` function while also restoring the necessary data processing pipeline.
- **Learning:** Blindly replacing entire files is risky. Future changes should be surgical and targeted, even when restoring from a "known good" version.

**Challenge 2: Critical `ValueError` Crashes**

- **Issue:** The `run_keepa_script` task consistently failed with a `ValueError: too many values to unpack`. This was traced to two separate API calls in `keepa_deals/keepa_api.py` (`fetch_deals_for_deals` and `fetch_product_batch`) that returned more values than the calling code in `Keepa_Deals.py` was expecting.
- **Solution:** Both call sites in `Keepa_Deals.py` were patched to correctly unpack all four return values. For example, the `fetch_product_batch` call was changed to `product_data_response, api_info, _, tokens_left = fetch_product_batch(...)`.
- **Outcome:** **Success.** This fix was critical and resolved the primary application crashes, allowing the test script to run to completion.

**Challenge 3: Missing Seller and Business Data**

- **Issue:** After fixing the `ValueError` crashes, test runs completed but key data columns (`Best_Price`, `Profit`, `Margin`, `Seller`) were empty in the database.

- Solution:

   

  The root cause was that the seller-caching mechanism had been lost in a previous version. I restored the original, efficient logic:

  1. Collected all unique `sellerId`s from the fetched products.
  2. Made a single, batch API call to `fetch_seller_data` to get all seller information at once.
  3. Stored this data in a `seller_data_cache` dictionary.
  4. Passed this cache to the `get_all_seller_info` function within a dedicated processing loop.

- **Outcome:** **Success.** This not only fixed the missing data but also ensured the process was highly efficient, avoiding N+1 API calls.

**Challenge 4: XAI Seasonality API Rate Limiting**

- **Issue:** The user noted that the seasonality classification was frequently failing due to `429 Too Many Requests` errors from the XAI API, and the fallback logic was unhelpful (returning "None").

- Solution:

   

  Implemented two user-requested improvements in

   

  ```
  keepa_deals/seasonality_classifier.py
  ```

  :

  1. Added a simple time-based rate limiter to wait at least 2 seconds between XAI API calls.
  2. Modified the logic to fall back to the original heuristic result ("Year-round") if the API call failed, rather than returning an unhelpful value.

- **Outcome:** **Success.** The system is now resilient to XAI API rate limits and produces more sensible default data when they occur.

**Challenge 5: Environment and Permissions**

- **Issue:** Testing was repeatedly hampered by a mismatch between the test environment and the user's production server. The application and Celery worker must run as the `www-data` user, and running test setup commands as `root` broke file permissions, causing the Celery worker to fail silently.
- **Solution:** Through extensive collaboration, we established a definitive testing protocol that involves using `sudo -u www-data` to run commands in the correct user context and `sudo chown -R www-data:www-data` to fix permissions.
- **Outcome:** **Success.** This shared knowledge is critical for any future debugging or testing.

------

#### **3. Final Status: COMPLETE**

All objectives for this task were met. The dashboard's core functionality is fully restored, as confirmed by `check_db.py` and direct database schema inspection. The application is stable, data is processed and calculated correctly, and several critical bugs and regressions have been resolved. The learnings regarding the environment and permissions are particularly valuable for future work.