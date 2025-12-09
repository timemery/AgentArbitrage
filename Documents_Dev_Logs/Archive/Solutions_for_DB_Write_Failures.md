# Summary of `deals.db` Write Failures and Solutions

This document summarizes the historical issues and solutions related to silent and explicit failures when writing data to the `deals.db` SQLite database, as extracted from the project's development logs.

## 1. Data Type Mismatches and Sanitization

This is the most common cause of silent data corruption or missing data. The database schema would define a column as `INTEGER` or `REAL`, but the data processing pipeline would attempt to insert a string. SQLite often fails silently in these cases, resulting in `NULL` values.

*   **Issue:** Inserting strings with currency symbols, commas, or percentage signs (e.g., `"$1,234.56"`, `"50%"`) into numeric columns.
    *   **Solution:** A centralized data cleaning function, `clean_numeric_values`, was created in `keepa_deals/processing.py`. This function strips all non-numeric characters and correctly casts the value to a `float` or `int` *before* it is sent to the database. Both the `backfill_deals` and `update_recent_deals` tasks must use this function.

*   **Issue:** Inserting descriptive strings (e.g., `"New Seller"`, `"Too New"`) into a numeric column.
    *   **Solution 1 (Hardening):** The `save_to_database` function was hardened to check if a column's intended type is numeric. If it is, the function forces the value to a `float` or, if conversion fails (as it would for `"New Seller"`), stores it as `NULL`. This prevents database corruption.
    *   **Solution 2 (Schema Change):** For specific columns where descriptive strings are desired (e.g., `Percent_Down`), the `create_deals_table_if_not_exists` function in `keepa_deals/db_utils.py` was modified to explicitly define that column's type as `TEXT`, overriding the default numeric inference.

*   **Issue:** Incorrectly inferring the data type for Sales Rank columns.
    *   **Solution:** The `create_deals_table_if_not_exists` function was updated with explicit checks to ensure that columns named `'Sales Rank - Current'` and `'Sales Rank - 365 days avg.'` are always created with the `INTEGER` data type.

## 2. Silent Celery Worker Failures

A recurring and difficult-to-diagnose issue is the silent failure of the final `database_connection.commit()` call when executed from within a Celery worker process in the sandbox environment.

*   **Symptom:** The `backfill_deals` task runs to completion in the `celery.log`. All log messages, including "Processing complete" and "Saving to database," appear. However, the `deals.db` file remains empty or its timestamp is unchanged, indicating the final transaction was never committed.
*   **Root Cause:** **Unknown and unresolved.** This appears to be a systemic issue within the sandbox environment where SQLite commits fail silently from a Celery worker, even when the code appears to execute correctly.
*   **Workarounds/Investigation:**
    *   Ensuring file permissions are correct for `www-data`.
    *   Confirming all paths to the database file are consistent and correct across all modules.
    *   Verifying that the Celery worker is running the latest code (clearing `__pycache__`).
    *   Despite these checks, the issue has persisted intermittently.

## 3. Configuration and Data Pipeline Errors

These issues prevented data from being written because the pipeline failed before the database write step.

*   **Issue:** The database file (`deals.db`) was not created by the Celery worker, likely due to sandboxing or permissions issues.
    *   **Solution:** The database utility scripts were made more robust. A reliable workaround is to ensure the `deals.db` file is created manually or by a setup script before the Celery worker attempts to write to it.

*   **Issue:** The API call (`fetch_deals_for_deals`) was using a hardcoded, restrictive query, resulting in zero deals being returned from the API.
    *   **Solution:** The function was refactored to remove the hardcoded query and correctly use the dynamic, user-configurable filters from `settings.json`. When the pipeline produces no deals, no data is written to the database.

*   **Issue:** The file timestamp of `deals.db` was observed to be unchanging.
    *   **Diagnosis:** This was the key symptom confirming that database write operations were failing silently. The `check_db.py` script was sometimes misleading as it could have been reading from a stale or cached version of the database. The file system's last modified timestamp is a more reliable indicator of a successful write.
