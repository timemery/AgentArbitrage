# Dev Log: Diagnostics Suite Improvement & Token Death Spiral Mitigation

**Date:** 2026-02-18
**Author:** Jules
**Status:** SUCCESS

## Overview
The primary objective of this task was to investigate the effectiveness of the existing diagnostic toolset (`Diagnostics/run_suite.sh`) and enhance it to better understand critical application failures. Specifically, the system was experiencing a "Dwindling Deals" issue where deal ingestion had stalled for ~23 hours, and a suspected "Token Death Spiral" where Keepa tokens were stuck in a negative deficit despite the ingestor being paused.

## Challenges Faced

1.  **Token Death Spiral:** The system was stuck at ~-20 tokens, consuming tokens at the exact rate of refill (5/min), preventing recovery to the Burst Threshold (+40). This indicated a "Phantom Process" (stuck loop) was consuming tokens in the background.
2.  **Diagnostic Blind Spots:**
    *   `run_suite.sh` lacked visibility into the Celery Queue depth, making it hard to distinguish between "idle" and "stuck".
    *   It did not track XAI API errors, leaving a gap in understanding AI-related failures.
    *   It did not flag "Zombie Deals" (stalled items) explicitly enough.
3.  **User Confusion on Restart:** After a force kill/restart, `check_pause_status.py` reported "Unknown" for token status because Redis keys were wiped, causing alarm.
4.  **Execution Errors:** The new `monitor_phantom_processes.py` script initially failed to run because it lacked a shebang and executable permissions.

## Solutions Implemented

### 1. Diagnostics Suite Overhaul
*   **Queue Depth Monitoring:** Updated `Diagnostics/system_health_report.py` to check Redis for `celery` queue length.
    *   PASS: < 100 tasks
    *   WARN: < 1000 tasks
    *   FAIL: > 1000 tasks (Critical Backlog)
*   **Zombie Deal Detection:** Updated `Diagnostics/comprehensive_diag.py` to count deals not updated in > 24 hours.
*   **XAI Error Tracking:** Added logic to grep logs for "XAI Rescue Failed" and "XAI API Error".
*   **Deep Dive Recommendation:** Updated `run_suite.sh` to explicitly recommend running `Diagnostics/analyze_rejection_reasons.py` when rejection rates are high.

### 2. "Unknown" Token Status Fix
*   Modified `Diagnostics/check_pause_status.py` to automatically fetch token status from the Keepa API if Redis keys are missing (e.g., after a flush). This ensures the user always sees a valid token count.

### 3. Phantom Process Mitigation (The Trap)
*   **Detection Tool:** Created `Diagnostics/monitor_phantom_processes.py` using `psutil` to identify Python processes running for > 1 hour. This tool logs findings to `phantom_process_monitor.log`.
*   **TokenManager Trap:** Implemented a "High Frequency Monitor" inside `keepa_deals/token_manager.py`.
    *   Tracks API calls per minute by process PID.
    *   **Trigger:** If a single process exceeds **60 calls/minute**, it logs a `PHANTOM TRAP` warning.
    *   **Action:** It forces a `time.sleep(1)` penalty to throttle the runaway process, preventing it from consuming tokens faster than the refill rate.

### 4. Operational Fixes
*   Added `#!/usr/bin/env python3` shebang to `monitor_phantom_processes.py` and set executable permissions (`chmod +x`).
*   Verified that `kill_everything_force.sh` performs a Redis `FLUSHALL`, which explains the loss of state data (and justifies the fix in #2).

## Outcome
The task was successful. The "Phantom Process" was terminated via `kill_everything_force.sh`, restoring token balance to healthy levels (~130). The diagnostic suite is now robust enough to detect:
1.  **Stalled Queues** (Queue Depth)
2.  **Stalled Data** (Zombie Deals)
3.  **Stuck Loops** (Phantom Monitor & TokenManager Trap)
4.  **AI Failures** (XAI Error Counts)

This ensures that future "Death Spirals" can be identified and mitigated proactively.
