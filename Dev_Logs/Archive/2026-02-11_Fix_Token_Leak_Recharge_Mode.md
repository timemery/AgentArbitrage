# Fix Token Leak & Enforce Recharge Mode Persistence

**Date:** 2026-02-11
**Task:** Investigate and Fix Random Token Consumption during Recharge Mode
**Status:** ✅ Successful

## 1. Overview
The system was observed behaving erratically during "Recharge Mode" (the state where it pauses to accumulate 80 tokens for a burst). Instead of waiting for the full 80 tokens, it would randomly consume tokens at lower levels (e.g., 12, 17, 21), preventing the burst threshold from ever being reached. This effectively stalled the ingestion pipeline on low-tier Keepa plans.

## 2. The Issue (Symptoms)
- **Expected Behavior:** When tokens < 20 and Refill Rate < 10/min, the system should enter `Recharge Mode` and **completely pause** all API calls until tokens >= 80.
- **Observed Behavior:** The system would enter Recharge Mode but then "leak" tokens every few minutes.
- **Impact:** The token bucket hovered around 15-25, never reaching the efficient "Burst Mode" threshold (80), causing the `smart_ingestor` to run in inefficient, starvation-prone single-item batches.

## 3. Root Cause Analysis
Two distinct issues were identified that contributed to this behavior:

### A. The "Flapping Rate" Bug
The `TokenManager` logic coupled the **maintenance** of Recharge Mode with the **trigger** condition.

*   **The Flaw:**
    ```python
    # OLD LOGIC (Simplified)
    if self.REFILL_RATE_PER_MINUTE < 10:  # <--- CRITICAL FLAW
        if is_recharging:
            wait()
    ```
*   **The Trigger:** Keepa's API sometimes reports transient spikes in the `refillRate` (e.g., jumping from 5/min to 12/min for a single response) before settling back down.
*   **The Result:** When the rate spiked to 12, the outer `if` condition failed. The code skipped the "Recharge Mode" check entirely, even though the `is_recharging` flag was set in Redis. The system immediately consumed tokens, dropping the balance back down, and then re-entered Recharge Mode when the rate normalized. This caused the "sawtooth" pattern of random consumption.

### B. The "Status Check" Drain
The `sync_tokens()` method calls the Keepa `/token` endpoint to get an authoritative count. This call costs **1 token**.
*   **The Flaw:** There was no throttling on this method.
*   **The Trigger:** If the `smart_ingestor` or other tasks crashed, restarted, or looped tightly, they would call `sync_tokens()` on initialization.
*   **The Result:** Frequent restarts could drain the bucket at a rate of ~1 token/minute just by checking the balance, neutralizing the natural refill rate of 5/min.

## 4. The Solution

### 1. Decoupled Persistence Logic
The check for an active Recharge Mode was moved **outside** the rate condition. Once the system enters Recharge Mode (sets the Redis flag), it **must** respect that mode until the exit condition (`tokens >= BURST_THRESHOLD`) is met, regardless of what the current refill rate reports.

```python
# NEW LOGIC
# 1. Check Persistence FIRST
if self.redis_client:
    is_recharging = self.redis_client.get(self.REDIS_KEY_RECHARGE_MODE)
    if is_recharging == "1":
         # Enforce wait loop until 80 tokens, ignoring current rate
         ...

# 2. Check Triggers LATER
if self.REFILL_RATE_PER_MINUTE < 10 and tokens < 20:
    # Enter Recharge Mode
```

### 2. Throttled Status Checks
Implemented a `last_sync_request_timestamp` to prevent `sync_tokens()` from calling the API more than once every 60 seconds, unless `force=True` is passed. This stops the "drain via observation" effect.

## 5. Verification & Outcome
*   **Reproduction Script:** Created `tests/verify_token_logic.py` which successfully simulated the "Rate Spike" scenario. It failed (leaked) on the old code and passed (blocked) on the new code.
*   **Live Diagnostics:** After deployment, the system correctly entered Recharge Mode and held firm at ~31 tokens (Status: `PAUSED (Recharge Mode Active)`), waiting for the full 80-token charge despite any rate fluctuations.

## 6. Key Learnings
*   **State Machine Persistence:** When a system enters a specific state (like "Recharging"), the *exit* condition must be the only way out. Relying on the *entry* condition (low rate) to persist the state is fragile against noisy data.
*   **Observer Effect:** In low-resource environments (5 tokens/min), the cost of monitoring (1 token/call) is non-negligible. Throttling status checks is mandatory to prevent the monitoring system from becoming the bottleneck.
