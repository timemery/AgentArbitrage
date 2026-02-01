# Fix Service Startup, Resilience, and Diagnostic False Negatives

**Date:** 2026-02-01
**Task:** Diagnose and fix persistent Celery Worker/Beat startup failures and "Not Found" diagnostic errors.

## Overview
The system was experiencing a persistent issue where Celery Worker and Beat services would seemingly start (logs showed "ready") but then disappear or fail to be detected by diagnostic tools. Additionally, the resiliency script (`start_celery.sh`) failed to restart them when they crashed.

## Root Cause Analysis

### 1. Monitor Blindness (The "Tail Masking" Bug)
The primary resilience script, `start_celery.sh`, uses an infinite loop to check if the worker is running and restart it if missing.
*   **The Flaw:** It used the regex `pgrep -f "celery.*worker"`.
*   **The Trigger:** When a developer or deployment script runs `tail -f celery_worker.log` to monitor progress, that process command line contains both "celery" and "worker".
*   **The Consequence:** `pgrep` matched the `tail` process. The script concluded "The worker is running" (false positive) and did **not** restart the actual worker process if it had crashed.

### 2. Diagnostic False Negatives
The system health check scripts (`system_health_report.py` and `comprehensive_health_check.py`) were reporting `[FAIL] Celery Worker: Not Found` even when the worker *was* running.
*   **The Flaw:** They checked for the exact substring `"celery worker"` in the process list.
*   **The Reality:** In the production environment, the process often runs as `python3 -m celery -A worker.celery_app worker ...`. The arguments (`-A ...`) separate the word "celery" from "worker".
*   **The Consequence:** The exact substring match failed, leading to false alarms and confusion.

### 3. False "Ingestion Stalled" Warning
The `comprehensive_health_check.py` script warned `[WARNING] No deals seen in the last hour. Ingestion is STALLED` whenever deal flow stopped.
*   **The Context:** During a **Backfill** operation (heavy historical fetch), the system intentionally pauses the "Delta Sync" (Upserter) to prevent token starvation.
*   **The Flaw:** The diagnostic script did not check for the active Backfill Lock, interpreting the intentional pause as a system failure.

## The Solution

### 1. Hardened Process Detection in Monitor
Updated `start_celery.sh` to use a stricter regex that targets the standard Celery application flag:
*   **Old:** `pgrep -f "celery.*worker"`
*   **New:** `pgrep -f "celery.*-A.*worker"`
*   **Why:** The `tail` command does not contain the `-A` flag. This correctly distinguishes the actual worker process from log viewing tools.

### 2. Robust Diagnostic Logic
Updated both `Diagnostics/system_health_report.py` and `Diagnostics/comprehensive_health_check.py` to use independent keyword verification:
*   **Logic:** `if ('celery' in cmd and 'worker' in cmd)`
*   **Why:** This accurately detects the process regardless of argument order or interleaved flags.

### 3. Context-Aware Stalled Check
Updated `Diagnostics/comprehensive_health_check.py` to check for `backfill_deals_lock` in Redis.
*   **New Behavior:** If the lock is held, it reports `[INFO] Ingestion is paused for backfill (Expected)` instead of a warning.

## Verification
*   **Reproduction Script:** Confirmed that `pgrep` with the old regex falsely matched a mock `tail` process, while the new regex did not.
*   **Logic Verification:** Confirmed that the new diagnostic logic correctly identifies split process strings that the old logic missed.
*   **Deployment:** The system now correctly reports all services as "Running", and the monitor successfully restarts the worker if it is killed, even while logs are being tailed.

## Key Learnings
1.  **Avoid Loose Regex in Process Monitors:** When grepping for processes, always try to match specific flags (like `-A` or `--app`) rather than generic names, especially if log files share those names.
2.  **String Matching vs Token Matching:** Exact substring matching (`if "a b" in s`) is brittle for command lines. Checking for independent tokens (`if "a" in s and "b" in s`) is much more robust against argument reordering.
3.  **Context is King in Diagnostics:** A "zero data flow" state isn't always an error. Diagnostics must check system locks/state flags (like Backfill active) to differentiate between a crash and a planned pause.
