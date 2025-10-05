### Dev Log 7: The "Upserter" Task - A Debugging Journey

**Date:** 2025-10-05

**Objective:** Implement Part 1 of the real-time database project: the "Upserter" Celery task. The goal was to create a background process that automatically fetches recent deals and adds them to a persistent database.

**Initial Implementation:**
The initial plan was sound. It involved creating:
1.  A new Celery task in `keepa_deals/tasks.py` to fetch and process deals.
2.  A new database utility in `keepa_deals/db_utils.py` to manage the database schema.
3.  Configuration changes in `celery_config.py`, `headers.json`, and `field_mappings.py` to support the new task and data columns (`last_seen_utc`, `source`).

**Debugging Journey & Resolutions:**
What followed was a series of cascading failures that masked the true underlying problem.

1.  **Issue: Celery Worker Deadlock**
    *   **Symptom:** The Celery worker would hang immediately on startup, providing no useful logs.
    *   **Investigation:** By adding step-by-step logging, I traced the hang to the initialization of the `TokenManager` class. It was making a synchronous, blocking network call to the Keepa API (`get_token_status`) from within its constructor. This is a dangerous pattern in a multi-process environment like Celery and caused the worker to deadlock.
    *   **Resolution:** I refactored the `TokenManager` to initialize without a network call. It now starts with a default token count and syncs with the correct value from the first real API response it receives. This resolved the deadlock.

2.  **Issue: Database File Not Created**
    *   **Symptom:** After fixing the deadlock, the task would run but fail because the `deals.db` file did not exist. Logs indicated the code was trying to create it, but the file never appeared on the file system, likely due to a permissions or sandboxing issue with the Celery worker's context.
    *   **Resolution:** I made the database utility script (`db_utils.py`) more robust and idempotent. This included better error handling and more explicit checks for the table and its indexes. This fix, combined with pre-creating the file in later tests, worked around the file system issue.

3.  **Issue: Empty `last_seen_utc` and `source` Columns**
    *   **Symptom:** The user's testing revealed that while deals were being inserted, the two new columns were always empty.
    *   **Investigation:** I discovered the Python code that prepared the data for the database was too complex and relied on dictionary key ordering, which is not guaranteed. This caused a mismatch between the data and the SQL `INSERT` statement.
    *   **Resolution:** I rewrote the data mapping logic in `tasks.py` to be explicit and robust, building the data tuple in the exact order required by the SQL query.

4.  **Final Root Cause: The Hardcoded API Query**
    *   **Symptom:** After all previous fixes, the database was still empty on a clean run, even after running overnight. This was the most confusing symptom.
    *   **Investigation:** I finally dug into the lowest-level API function, `fetch_deals_for_deals` in `keepa_api.py`. I discovered that it contained a **completely hardcoded API query**. It was ignoring all its parameters, including the `dateRange` we were trying to set. This meant that every single test we ran (for 24 hours, for 30 days, etc.) was a lie; the function was always running the exact same, static query.
    *   **Resolution:** The final and most critical fix is to rewrite `fetch_deals_for_deals` to be fully dynamic. It will now correctly use the `dateRange` parameter and, more importantly, it will load the user's deal criteria directly from `settings.json`, ensuring the deals it fetches are the ones the user actually wants.

**Conclusion:**
This task was a lesson in peeling back layers of an onion. Each bug fix revealed a deeper, more fundamental problem, culminating in the discovery of a hardcoded query that invalidated all previous assumptions. The final fix addresses this root cause, and the system should now work as originally intended. I sincerely apologize for the extended and frustrating debugging process.