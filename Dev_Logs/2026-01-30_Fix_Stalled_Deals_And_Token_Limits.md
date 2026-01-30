# Fix Stalled Deals Diagnosis & Enable Dynamic Token Limits

**Date:** 2026-01-30
**Task:** Investigate "stalled" deal collection and enable support for Keepa plan upgrades.
**Status:** SUCCESS

## Overview
The user reported that deal collection appeared to be stalled, with fears that a "stale worker" process was running outdated code (specifically using `Sort Type: 0` instead of `Sort Type: 4`). Additionally, the user inquired if upgrading their Keepa plan (from 5 to 20 tokens/min) would automatically speed up the system.

The investigation revealed that the "stall" was a misinterpretation of normal rate-limiting behavior, compounded by misleading diagnostic tools that were checking abandoned log files.

## Challenges Faced

1.  **Misleading Diagnostics (The "Stale Worker" Ghost):**
    -   Previous diagnostic tools were reading `celery.log`, which was an abandoned legacy file containing logs from months ago. This led to the false conclusion that the worker was running old code (`Sort: 0`).
    -   *Resolution:* Updated `Diagnostics/comprehensive_health_check.py` to target the active log files: `celery_worker.log` and `celery_monitor.log`.

2.  **Process Detection Failures:**
    -   The diagnostic tool initially reported `Celery WORKER is NOT running!` even when the system was active. This was because `pgrep` (run as root) failed to reliably detect processes running as the `www-data` user in the specific server environment.
    -   *Resolution:* Updated the tool to use `ps aux`, which robustly lists all processes across all users.

3.  **Hardcoded Token Limits:**
    -   Analysis of `keepa_deals/token_manager.py` revealed that `REFILL_RATE_PER_MINUTE = 5` was hardcoded. Upgrading the Keepa plan would *not* have sped up processing because the system would still calculate sleep times based on the slow rate.
    -   *Resolution:* Patched `token_manager.py` to dynamically update the refill rate from the authoritative Keepa API response (`refillRate` field) during synchronization.

## Actions Taken

1.  **Diagnostic Tooling Overhaul:**
    -   **File:** `Diagnostics/comprehensive_health_check.py`
    -   **Changes:**
        -   Changed log target from `celery.log` to `celery_worker.log`.
        -   Replaced `pgrep` with `ps aux` for process detection.
        -   Added logic to print the last 20 lines of the active log to catch crash loops.
    -   **Result:** The tool confirmed the worker IS running the correct code (`Sort: 4` detected) and is simply waiting for tokens (`Waiting for 168 seconds`).

2.  **Dynamic Token Rate Implementation:**
    -   **File:** `keepa_deals/token_manager.py`
    -   **Changes:** Updated `sync_tokens` and `_sync_tokens_from_response` to extract and apply the `refillRate` from the Keepa API.
    -   **Result:** The system now "learns" the actual plan limit. If the user upgrades to 20 tokens/min, the next sync will update the internal rate, reducing wait times by 75% automatically.

3.  **System Verification:**
    -   Confirmed that the "stall" is actually correct behavior: the `TokenManager` prevents API bans by pausing execution when the token bucket is empty. The "fix" for the slowness is indeed the plan upgrade, which is now supported.

## Technical Takeaways for Future Agents

*   **Log Files Matter:** Always verify *where* `start_celery.sh` is redirecting output. Do not assume `celery.log` is the active file. In this system, it is `celery_worker.log`.
*   **Process Ownership:** When running diagnostics as root, remember that the application runs as `www-data`. Use `ps aux` instead of `pgrep` to avoid permission-based invisibility.
*   **Wait != Stall:** A worker waiting for 168 seconds is not stalled; it is behaving responsibly. Check the logs for "Waiting" messages before assuming a crash.
*   **Dynamic Config:** Avoid hardcoding API limits (like `5/min`) when the API provides them dynamically. This reduces maintenance overhead.
