# Fix Deal Stagnation (DB Locking & Persistence)

**Date:** 2026-02-05
**Status:** SUCCESS
**Modules Modified:** `keepa_deals/backfiller.py`, `keepa_deals/simple_task.py`, `celery_config.py`

## 1. Overview
The system was experiencing a critical issue where the deal count on the dashboard remained stagnant at ~62 deals for two days, despite diagnostics showing "green" status for API connectivity and service health. The objective was to perform a deep-dive diagnosis, identify the silent failure mechanism, and implement a robust fix.

## 2. Investigation & Root Cause
The investigation revealed a "Silent Crash" scenario caused by database contention between the `Upserter` (Live Updates) and the `Backfiller` (Historical Data).

*   **The Conflict:** Both tasks write to the `deals` SQLite database. The `Upserter` runs frequently and locks the database.
*   **The Crash:** The `Backfiller` used the default SQLite timeout (5 seconds). When the `Upserter` held the lock for > 5 seconds (common during batch updates), the `Backfiller` raised `sqlite3.OperationalError: database is locked`.
*   **The Persistence Failure:** The `Backfiller` was not configured in `celery_config.py` as a recurring task. It relied on being triggered once. When it crashed due to the DB lock, it **died permanently** and never restarted.
*   **The "Green" Trap:** Diagnostics reported the Celery Worker was "Running" (because other tasks were alive) and the Redis Lock was "Active" (because the crashed task never released it), masking the fact that the actual data processing loop had terminated.

## 3. Solutions Implemented

### A. Database Hardening (The Fix)
We modified `keepa_deals/backfiller.py` and `keepa_deals/simple_task.py` to explicitly set a 60-second timeout for database connections.
*   **Old:** `sqlite3.connect(DB_PATH)` (Defaults to 5s).
*   **New:** `sqlite3.connect(DB_PATH, timeout=60)`.
*   **Result:** The tasks now patiently wait for the lock instead of crashing.

### B. Task Resilience (The Safety Net)
We wrapped the main processing loop in `backfiller.py` with a `try...except` block.
*   **Logic:** If a chunk fails (due to a transient DB lock, API error, or network blip), the error is logged, and the task sleeps for 5 seconds before attempting the next chunk.
*   **Impact:** A single error no longer kills the entire 10,000-deal pipeline.

### C. Process Persistence (The Guarantee)
We added `backfill_deals` to the `beat_schedule` in `celery_config.py` to run every 30 minutes.
*   **Mechanism:** It uses a Redis lock (`blocking=False`) to ensure only one instance runs at a time.
*   **Benefit:** If the task *does* crash (e.g., server reboot, OOM kill), the scheduler automatically restarts it within 30 minutes. This turns a permanent stoppage into a temporary pause.

### D. Token Optimization (The Scalability Fix)
We reduced `BACKFILL_BATCH_SIZE` from 5 to 2.
*   **Context:** The Keepa plan allows 5 tokens/minute. A batch of 5 new deals costs ~100 tokens.
*   **Problem:** Requesting 100 tokens created huge "starvation windows" where the Backfiller sat idle waiting for the bucket to refill, while the Upserter (costing 5-10 tokens) constantly jumped the queue.
*   **Fix:** A batch of 2 costs ~40 tokens. This is much easier to satisfy, allowing the Backfiller to "squeeze in" operations more frequently between Upserter runs.

## 4. Verification
*   **Locking Test:** A reproduction script (`verify_db_locking.py`) confirmed that the default 5s timeout causes crashes during concurrent writes, while the 60s timeout successfully handles the wait.
*   **Logic Test:** `reproduce_issue.py` verified that the new logic correctly processes deals and handles the "Lightweight" vs "Heavy" logic paths without errors.
*   **Syntax Check:** Verified `celery_config.py` is valid and loadable.

## 5. Conclusion
The system is now hardened against SQLite concurrency issues. The deal collection pipeline should now run continuously, automatically recovering from transient errors or crashes, and efficiently utilizing the limited Keepa token budget.
