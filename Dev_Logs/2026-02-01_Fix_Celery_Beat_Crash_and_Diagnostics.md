# Fix Celery Beat Crash Loop and Diagnostic Discrepancies

**Date:** 2026-02-01
**Task:** Restore data collection functionality by fixing the "Scheduled Upserter (Celery Beat) is NOT RUNNING" error and resolving diagnostic data integrity mismatches.

## Overview
The system was experiencing a complete halt in data collection, with the deal count stuck at 194. The diagnostic tools reported two critical issues:
1.  **Service Failure:** "Scheduled Upserter (Celery Beat) is NOT RUNNING."
2.  **Data Integrity Mismatch:** "[MISMATCH] DB Filtered Count (152) != Dashboard API (194)."

## Root Cause Analysis

### 1. Celery Beat Crash Loop
The primary cause of the data stall was the failure of the Celery Beat scheduler.
*   **The Trigger:** A forceful shutdown or crash likely corrupted the persistent schedule file (`celerybeat-schedule`).
*   **The Loop:** When Celery Beat attempted to restart, it tried to read this corrupted file, crashed immediately, and the `start_celery.sh` monitor loop would simply try to restart it again without clearing the bad state. This resulted in an infinite crash loop.

### 2. Diagnostic False Negatives (Process Detection)
The diagnostic scripts (`diagnose_dwindling_deals.py` and `comprehensive_diag.py`) were reporting misleading status updates.
*   **The Flaw:** They used a loose regex: `pgrep -f "celery beat"`.
*   **The False Positive:** This matched the *diagnostic command itself* or any user running `tail -f celery_beat.log`. This made it difficult to trust the "RUNNING" vs "NOT RUNNING" status.

### 3. API Filter Mismatch
The diagnostic tool reported a mismatch between the database filtered count and the API response.
*   **The Logic Gap:** The diagnostic test queried the API with `?margin_gte=0`.
*   **The API Design:** The backend (`wsgi_handler.py`) treats `0` as "Any" (i.e., "User didn't set a filter"), so it ignored the parameter and returned the total count (194).
*   **The DB Query:** The diagnostic script executed `SELECT COUNT(*) FROM deals WHERE Margin >= 0`, which strictly filtered out NULLs, resulting in 152.
*   **The Mismatch:** 152 != 194.

## The Solution

### 1. Robust Service Recovery
Updated `start_celery.sh` to include a cleanup step in the monitor loop.
*   **Change:** Added `sudo rm -f "$APP_DIR/celerybeat-schedule"*` before the `celery beat` restart command.
*   **Effect:** This ensures that if the scheduler crashes, the corrupted state is wiped, allowing a clean and successful restart.

### 2. Hardened Process Detection
Updated `Diagnostics/comprehensive_diag.py` and `Diagnostics/diagnose_dwindling_deals.py`.
*   **Change:** Replaced `pgrep -f "celery beat"` with `pgrep -f "celery.*-A.*beat"`.
*   **Effect:** This strict regex matches the actual service command flags, preventing false matches against log-tailing tools.

### 3. Aligned Diagnostic Logic
Updated `Diagnostics/comprehensive_diag.py` to use a valid test case.
*   **Change:** Changed the test filter from `margin_gte=0` to `margin_gte=5`.
*   **Effect:** This forces the API to apply the filter logic (since 5 > 0), allowing a valid comparison between the DB query (`WHERE Margin >= 5`) and the API response. The diagnostic now correctly reports a MATCH.

## Outcome
The task was **successful**.
*   Celery Beat is confirmed running and stable.
*   Diagnostic tools now report accurate service status.
*   The data integrity check now passes, confirming the API filter logic is functioning correctly.
*   The system has resumed data collection (evidenced by token consumption logs).
