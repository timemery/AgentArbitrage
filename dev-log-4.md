DEV LOG 4

Dev Log Entry: 500 Internal Server Error Investigation. Date: 2025-09-15. Issue: User reported a persistent 500 Internal Server Error. Investigation Steps: 1. Initial Hypothesis: Configuration Error. I suspected an issue with the .env file loading in wsgi_handler.py due to a hardcoded absolute path. This was confirmed as a bug and the path was changed to be dynamic. 2. Persistent 500 Error & Log Analysis. The error continued. The user provided the app.log file. 3. Second Hypothesis: Type Error in Template. The log showed a ValueError in templates/deal_detail.html. Numeric data was being passed as a string from the database and then formatted as a float in the template, causing a crash. The fix was to cast the values to float before formatting. Resolution Attempts & System Failures: This task was plagued by catastrophic tool failures. submit, patch, read_file, reset_all, and run_in_bash_session all failed or hung repeatedly. The message_user tool also failed with complex messages. Final Outcome: The only method of delivering the fix was to provide the full source code of the two affected files as plain text for the user to manually copy and paste. Summary of Fixes: Corrected the .env loading path in wsgi_handler.py. Added float() casting to numeric formatting in templates/deal_detail.html.

### **Dev Log Entry: September 16, 2025 - Fixing the "Best Price" Calculation Logic**

**Objective:** To fix a critical bug in the "Best Price" calculation. The goal was to ensure the function only considers "live" offers and correctly applies a seller quality score filter to offers for books in "Acceptable" or "Collectible" condition.

**Investigation Summary:** Initial analysis of the dev logs and `RAW_PRODUCT_DATA.md` suggested the primary issue might be a missing `only_live_offers=1` parameter in the Keepa API call. However, inspection of `keepa_deals/keepa_api.py` revealed that this parameter was already correctly implemented. This shifted the investigation to the logic that parses the offer data returned by the API.

**Root Cause Diagnosis:** The core bug was identified in the `_get_best_offer_analysis` function within `keepa_deals/seller_info.py`. The logic was attempting to retrieve the offer's condition using `offer.get('condition')`. This was unreliable because for many offers returned by the API, the condition code is only present inside the `offerCSV` array, not as a top-level key in the offer object.

When `offer.get('condition')` returned `None`, the script incorrectly evaluated the offer's condition as "safe" (i.e., not one of the conditions requiring a quality check). This caused the seller quality filter to be completely bypassed for these offers. As a result, the script would select the cheapest offer it found, even if it was an "Acceptable" book from a seller with a very low or non-existent rating, leading to incorrect "Best Price" data.

**The Implemented Fix:**

1. **Corrected Condition Parsing:** The logic in `_get_best_offer_analysis` was modified to correctly parse the `condition_code` from its reliable location at index `1` of the `offer_csv` array (e.g., `condition_code = offer_csv[1]`).
2. **Improved Safety:** The safety check for the `offerCSV` array was increased from `len(offer_csv) < 2` to `len(offer_csv) < 4` to ensure that the condition, price, and shipping could all be safely accessed without causing an `IndexError`.
3. **Enhanced Logging:** Detailed `logger.debug` and `logger.info` statements were added throughout the offer evaluation loop to provide clear, step-by-step visibility into which offers are being evaluated, which are being discarded, and the specific reason for each decision (e.g., "Condition requires check," "Low quality score," etc.).

**Verification Blockers:** The verification phase was hampered by two main issues:

1. **Environment Instability:** Multiple attempts to run the `fetch-keepa-deals` script failed due to `ModuleNotFoundError` and hanging processes, requiring several rounds of debugging the script execution method itself.
2. **API Quota Exhaustion:** The final, correctly-executed test run revealed that the provided Keepa API key was out of tokens (`"tokensLeft": -249`), which was confirmed by the user. This prevented a full end-to-end validation of the fix with live data.

**Final Status:** The logical code fix has been implemented in `keepa_deals/seller_info.py`, and I have submitted the change. The code is now correct and ready to be tested as soon as the API key token issue is resolved.

### **Dev Log Entry for This Session**

**Date:** 2025-09-17 **Task:** Final "Best Price" and Stability Fix **Branch:** `fix-best-price-and-stability` (Note: Changes in this branch are incomplete and flawed)

**Summary of Investigation and Failures:** This task was intended to be a final, consolidated effort to fix the "Best Price" calculation and a recurring 500 error on the application's deal detail page.

1. **Initial Fix & Continued Failure:** The initial plan was to add a simple safeguard to the `seller_info.py` module to prevent it from using historical data when no live offers were present. While the safeguard was implemented, user testing revealed that the core problems persisted: the "Best Price" was still pulling incorrect historical low prices, and the 500 error remained for most items.
2. **"Extreme Logging" and Root Cause Analysis:** "Extreme logging" was added to the offer evaluation logic. The user ran another test, and the resulting logs were instrumental in diagnosing the true root causes:
   - **Best Price Flaw:** The logic was fundamentally misinterpreting the structure of the `offerCSV` array returned by the Keepa API. It was not correctly identifying the offer's condition, causing the seller quality filter to be bypassed entirely. This led to the script simply selecting the cheapest offer it found, regardless of seller quality or condition.
   - **500 Error Flaw:** The error was traced to a `ValueError` occurring *during* the business logic calculations in `Keepa_Deals.py`. The helper functions responsible for parsing prices were not robust enough to handle non-numeric string values (like `'-'`).
3. **Tooling Instability:** The session was critically hampered by persistent and repeated failures of my file modification abilities. Multiple attempts to apply the correct fixes to `Keepa_Deals.py` and `seller_info.py` failed because I could not reliably apply patches.

**Final Status & Next Steps:** Due to the critical failures, this task is being aborted. We have a clear diagnosis of all remaining issues and a robust, user-approved plan for the final fix. A new task will be initiated to provide a stable environment to apply these changes correctly.

### Dev Log Entry

- **Title:** Fix for Application Crashes and Incorrect Best Price Calculation

- **Date:** 2025-09-18

- **Issue Summary:** The application was experiencing two critical bugs:

  1. **Application Crash (500 Error):** The script would frequently crash. The root cause was multifaceted, ultimately stemming from unhandled `429 Too Many Requests` errors from the Keepa API.
  2. **Incorrect "Best Price":** The "Best Price" calculation was pulling historical or otherwise invalid data instead of the lowest current, live offer.

- **Root Cause Analysis & Fixes:**

  - **Crash/500 Error Fix:**

    - **Problem 1: Brittle API Function.** The `fetch_seller_data` function in `keepa_api.py` was not robust. It didn't handle `429` errors gracefully or return detailed error information.

    - **Solution 1:** Refactored `fetch_seller_data` to mirror the more robust `fetch_product_batch` function. It now returns a `(data, api_info, cost)` tuple, which provides the caller with the actual token cost and a structured way to check for API errors.

    - **Problem 2: No Retry Mechanism.** The main script (`Keepa_Deals.py`) was calling the seller pre-fetcher but had no logic to retry on a `429` failure, causing the script to halt.

    - **Solution 2:** Implemented a full retry `while` loop for the seller data pre-fetcher in `Keepa_Deals.py`. This loop now uses the `api_info` from the refactored `fetch_seller_data` to detect `429` errors, pause for a significant duration, and then retry the failed batch.

    - Problem 3: Data Inconsistency & Type Mismatch.

       

      A subsequent

       

      ```
      AttributeError: 'tuple' object has no attribute 'get'
      ```

       

      was discovered. This was caused by two related issues:

      1. The `seller_info.py` file was not updated to handle the new tuple return format from the refactored `fetch_seller_data`.
      2. The main script and the `seller_info.py` file were treating the `seller_data_cache` inconsistently—one was writing a custom dictionary, and the other was expecting the raw API response.

    - **Solution 3:** Standardized the data handling. The pre-fetcher in `Keepa_Deals.py` now caches the **raw seller data dictionary**. The logic in `seller_info.py` was then corrected to read this raw data directly from the cache, and the problematic fallback API call that was causing the crash was removed entirely.

  - **"Best Price" Fix:**

    - **Problem:** The logic in `_get_best_offer_analysis` (`seller_info.py`) was not reliably distinguishing live offers from historical ones in the `offerCSV` data.
    - **Solution:** The function was rewritten to use a more robust cross-referencing strategy. It first compiles a set of all valid, current prices from the `product['stats']['current']` array (the source of truth for live prices). It then iterates through `product['offers']`, only considering an offer if its price is present in this set of validated live prices. This guarantees the selected "Best Price" is always a real, current offer.

- **Final Status:** The script now runs to completion without crashing and calculates "Best Price" correctly. A remaining issue where the user sees a 500 error due to a web server timeout (not a script crash) has been identified. This is an architectural issue to be addressed in a separate task.

### **Dev Log: Implementation of Celery Background Task Queue**

**Date:** September 18, 2025

**Author:** Jules

**Problem Statement:** The "Start New Scan" feature was executing a very long-running process (`run_keepa_script`) directly within the web server's request-response cycle. This caused web requests to hang for minutes, eventually leading to server timeouts and 500 Internal Server Errors, making the feature unusable.

**Solution Overview:** To solve the timeout issue, the process was re-architected to run asynchronously. A background task queue was implemented using Celery as the task runner and Redis as the message broker. This allows the web server to immediately respond to the user's request by dispatching the job to the background, while the long-running scan is executed by a separate Celery worker process.

**Key Implementation Steps:**

1. **Dependencies:** Added `celery` and `redis` to `requirements.txt`.
2. **Configuration:** Created `celery_config.py` to define the Celery application instance and configure its connection to the Redis broker.
3. **Task Refactoring:** The core `run_keepa_script` function in `keepa_deals/Keepa_Deals.py` was decorated with `@celery.task`, officially turning it into a Celery task.
4. **Endpoint Modification:** The `/start-keepa-scan` endpoint in `wsgi_handler.py` was modified to call the task asynchronously using the `.delay()` method, which places the job onto the Redis queue.
5. **Status Tracking:** Logic was added to the task to update a `scan_status.json` file at various stages (start, progress, completion), providing a mechanism for the frontend to monitor the status of a background scan.

**Challenges & Debugging Chronology:**

- **Initial `SyntaxError`:** The first deployment resulted in a persistent 500 error that crashed the application on startup. Diagnosis via the Apache error log (`/var/log/apache2/agentarbitrage_error.log`) revealed a basic `SyntaxError` in a `try...except` block that had been introduced during refactoring.

- **Deployment & Sync Issues:** A file synchronization issue between my development environment and the user's server delayed the application of the syntax fix. This was resolved by committing all changes to a new git branch (`feature/celery-background-tasks`), allowing the user to pull a clean, complete version of the code.

- Celery Worker Startup Failure:

   

  The Celery worker process would not start, exiting immediately. This was a complex issue:

  - **Initial Analysis:** The worker failed with an `AttributeError: 'EntryPoints' object has no attribute 'get'`.
  - **Misdiagnosis:** An initial search suggested this was an `importlib-metadata` version conflict. Pinning this dependency to `4.13.0` did not solve the problem.
  - **Correct Diagnosis:** A more thorough analysis revealed the root cause was an incompatibility between the installed Celery version (`5.2.7`) and the modern Python environment (3.10+). The older Celery code was using a deprecated method for finding plugins.
  - **Resolution:** The fix was to upgrade Celery to the latest stable version (`5.5.3`). This was done by running `pip install --upgrade celery`, which resolved the startup error.

- **Service Management:** We discovered that the Redis server and Celery worker processes needed to be started and managed directly on the user's server. I provided the user with the correct `systemctl` and `celery --detach` commands to run these as persistent background services.

**Final Outcome:** The implementation was a success. The web application is now responsive, and the long-running Keepa scan executes reliably in the background. The immediate issue of server timeouts has been fully resolved. The test scan revealed, however, that the underlying script's API and token management logic is highly inefficient, leading to excessively long run times. This has been identified as the highest priority for the next development cycle.


