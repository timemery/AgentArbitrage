# Proposed Token Management Upgrade: Soft Buffers & Stall Detection

**Date:** 2026-02-18
**Status:** PROPOSED (Assessment & Plan)

## 1. Assessment of the Proposal

The user has proposed a "Soft Buffer" strategy to replace the rigid token thresholds currently in place. The core idea is to operate within a flexible range (e.g., 20 to 290 tokens) rather than pushing to the absolute limits (0 or 300).

### Key Components & Analysis

1.  **Soft Buffer Floor (~20 Tokens):**
    *   **Concept:** Instead of consuming tokens until hitting 0 (or a hard deficit limit), the system should detect when tokens drop below a "Soft Floor" (e.g., 20).
    *   **Mechanism:** When this floor is breached, the system allows the *current* operation to finish (Graceful Stop) but immediately triggers "Recharge Mode" for subsequent requests.
    *   **Verdict:** **HIGHLY FEASIBLE & BENEFICIAL.**
    *   **Reasoning:** This prevents "Hitting the Wall" (0 tokens) where operations fail abruptly. It allows for a controlled descent and ensures that even if a batch consumes slightly more than expected, it won't trigger a hard API lockout. It smooths out the "stop-start" cycle.

2.  **Stall Detection (~290 Tokens):**
    *   **Concept:** If tokens refill to near-maximum capacity (>290) while the system *should* be working, it indicates a stall or livelock.
    *   **Mechanism:** A monitor checks if `tokens > STALL_THRESHOLD` (e.g., 290). If so, it alerts or restarts the worker.
    *   **Verdict:** **CRITICAL SAFETY NET.**
    *   **Reasoning:** This addresses the "Silent Failure" mode where a worker thread dies or hangs but the process remains active. The token count is a reliable proxy for system activity: if tokens are full, nothing is happening.

3.  **Heartbeat "Stay Alive":**
    *   **Concept:** To prevent timeouts during long waits (e.g., low refill rates), the worker should emit a signal every few minutes.
    *   **Verdict:** **ESSENTIAL.**
    *   **Reasoning:** Hostinger and other VPS providers may kill idle processes. A simple log entry or file touch every 5 minutes prevents this "Zombie Death" during deep recharge cycles.

---

## 2. Implementation Plan

This section outlines the specific steps for a future developer to implement this strategy.

### Phase 1: `TokenManager` Enhancements (`keepa_deals/token_manager.py`)

1.  **Add Constants:**
    *   `SOFT_BUFFER_FLOOR = 20` (Configurable).
    *   `STALL_THRESHOLD = 290`.

2.  **Add Heartbeat Method:**
    *   Create a public method `emit_heartbeat(self)`:
        *   Updates a Redis key `keepa_worker_last_heartbeat` with the current timestamp (`time.time()`).
        *   Logs a "Heartbeat" message if called from within a wait loop.

3.  **Modify `request_permission_for_call` (The Soft Stop):**
    *   Insert a check *before* the main reservation logic:
        ```python
        # Soft Floor Check
        if self.tokens < self.SOFT_BUFFER_FLOOR and not self.is_recharging():
            logger.warning(f"Soft Floor Reached ({self.tokens} < {self.SOFT_BUFFER_FLOOR}). allowing current call, but triggering Recharge Mode.")
            self.set_recharge_mode(True)
            # Proceed with current call (Graceful Finish)
        ```
    *   This ensures the *next* call will see `is_recharging=True` and enter the wait loop immediately.

4.  **Modify `_wait_for_tokens` (The Heartbeat Loop):**
    *   Refactor the `time.sleep` loop to wake up every 300 seconds (5 minutes).
    *   Inside the loop:
        *   Call `self.emit_heartbeat()`.
        *   Log: `[Heartbeat] Waiting for tokens... Current: {self.tokens}. Target: {self.BURST_THRESHOLD}.`

5.  **Modify `sync_tokens` (The Stall Check):**
    *   After fetching tokens from API:
        *   If `tokens > STALL_THRESHOLD`:
            *   Log a warning: `POTENTIAL STALL: Tokens at Max Capacity ({tokens}). Is the worker stuck?`
            *   (Optional) Update a Redis key `keepa_system_stall_detected = 1` for external monitoring.

### Phase 2: `SmartIngestor` Integration (`keepa_deals/smart_ingestor.py`)

1.  **Main Loop Heartbeat:**
    *   Inside the main processing loop (e.g., `while True` or batch iteration):
    *   Call `token_manager.emit_heartbeat()` periodically.
    *   **Why:** Ensures the watchdog knows the worker is active and healthy even when it's crunching data (CPU bound) and not calling the API.

### Phase 3: The Watchdog (`Diagnostics/watchdog_stall_detector.py`)

1.  **Create Script:**
    *   A standalone Python script to be run via `cron` (every 15 mins) or as a sidecar process.

2.  **Logic:**
    *   Connect to Redis.
    *   Get `keepa_tokens_left`.
    *   Get `keepa_worker_last_heartbeat`.
    *   **Condition:**
        *   If `tokens > 280` **AND** `last_heartbeat` is older than 15 minutes:
            *   **Action:** Log ERROR "STALL DETECTED".
            *   **Recovery:** Execute `kill_everything_force.sh` (or trigger a graceful restart).

### Phase 4: Testing & Verification

1.  **Test Soft Buffer:**
    *   Simulate token drop from 25 -> 15.
    *   Verify the 15-token call succeeds.
    *   Verify the *next* call is blocked and enters Recharge Mode.

2.  **Test Heartbeat:**
    *   Run a mock wait loop.
    *   Verify `keepa_worker_last_heartbeat` is updated in Redis every 5 mins.

3.  **Test Stall Detector:**
    *   Manually set Redis tokens to 300.
    *   Manually set heartbeat to 20 mins ago.
    *   Run `watchdog_stall_detector.py` and verify it triggers the alert.
