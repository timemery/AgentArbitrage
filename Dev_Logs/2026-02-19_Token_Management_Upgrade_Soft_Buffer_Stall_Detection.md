# Token Management Upgrade: Soft Buffer & Stall Detection

**Date:** 2026-02-19
**Task:** Implement Soft Buffer (20 tokens) and Stall Detection (Watchdog + Heartbeats)
**Status:** SUCCESS

## Overview
The goal of this task was to enhance the robustness of the Keepa API token management system. Previous implementations relied on rigid thresholds (e.g., waiting until 0 tokens) which could lead to "hard stops" or API lockouts. Additionally, the system lacked a mechanism to detect and recover from "stalls" where a worker thread hangs or silently fails while holding resources.

## Changes Implemented

### 1. Soft Buffer Strategy (`keepa_deals/token_manager.py`)
-   **Concept:** Introduced a `SOFT_BUFFER_FLOOR` of **20 tokens**.
-   **Mechanism:** When tokens drop below this floor, the system allows the *current* request to proceed (Graceful Stop) but immediately triggers "Recharge Mode" for subsequent requests. This prevents the system from hitting the absolute 0-token limit or the `MAX_DEFICIT` hard stop.
-   **Code Change:** Modified `request_permission_for_call` to check `self.tokens < self.SOFT_BUFFER_FLOOR`. If true, it sets the Redis key `keepa_recharge_mode_active` to "1" but allows the current call to pass by setting a local flag `skip_recharge_check = True`.

### 2. Stall Detection System
-   **Heartbeats (`keepa_deals/token_manager.py`, `keepa_deals/smart_ingestor.py`):**
    -   Added an `emit_heartbeat()` method to `TokenManager` which updates a timestamp in Redis (`keepa_worker_last_heartbeat`).
    -   Integrated this heartbeat into long-running loops:
        -   `TokenManager._wait_for_tokens`: Emits heartbeat during long recharge sleeps.
        -   `SmartIngestor`: Emits heartbeat during pagination and batch processing loops.
-   **Watchdog (`Diagnostics/watchdog_stall_detector.py`):**
    -   Created a standalone script to monitor system health.
    -   **Logic:** Detects a stall if:
        1.  Tokens are high (> 290, meaning no consumption).
        2.  Heartbeat is old (> 15 minutes, meaning worker is silent).
    -   **Recovery:** Automatically executes `kill_everything_force.sh` to restart the system if a stall is detected.

### 3. Testing
-   Created `tests/test_token_upgrade.py` to verify:
    -   Soft Buffer trigger logic (ensuring it doesn't block the current call).
    -   Heartbeat emission to Redis.
    -   Stall warning logging.

## Challenges & Resolutions

### Challenge 1: The "Blocking Soft Buffer" Bug
**Issue:** Initial implementation of the Soft Buffer check inadvertently blocked the *current* call because the "Recharge Mode" check (Step 0) was executed immediately after setting the flag.
**Resolution:** Introduced a `skip_recharge_check` local variable. If the Soft Buffer condition is met, this flag is set to `True`, allowing the subsequent Recharge Mode check to be bypassed for *this specific function call only*.

### Challenge 2: NameError in Wait Loop
**Issue:** The `_wait_for_tokens` method attempted to log the `target` variable, which was not defined in that scope (it was passed as an argument but the log message referenced a global constant name style).
**Resolution:** Corrected the log message to use the `target` argument passed to the function.

### Challenge 3: Stall Detection Recovery
**Issue:** The initial watchdog script only logged the error but did not take action.
**Resolution:** Uncommented the `os.system("./kill_everything_force.sh")` line to enable automated recovery as per requirements.

## Conclusion
The system now possesses a proactive defense against API exhaustion (Soft Buffer) and a reactive safety net for process failures (Stall Watchdog). This significantly improves the stability of long-running ingestion tasks.
