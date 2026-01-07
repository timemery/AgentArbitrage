## Backfill Performance & Token Starvation Fix

**Date:** November 2025 **Task:** Diagnose and fix extreme slowness in data collection (106 deals in 40 hours). **Status:** **Success**

### 1. Overview

The user reported that the backfill process was collecting deals at a rate of ~2.6 deals/hour, which was orders of magnitude slower than expected. The goal was to identify the bottleneck and calculate a realistic time estimate for collecting 10,000 deals.

### 2. Challenges & Diagnosis

- The "Starvation" Loop:
  - The `TokenManager` was originally implemented with a **"Conservative"** strategy: if the token balance was insufficient for a batch, it would pause execution until the bucket refilled to its **maximum** (300 tokens).
  - Refilling 0 to 300 tokens takes approx. 60 minutes.
  - **The Conflict:** A separate, high-frequency "Upserter" task (`simple_task.py`) runs every minute. Although its consumption is low, it constantly sips from the bucket.
  - **Result:** The Backfiller would wait for 300. The Upserter would consume tokens at minute 59 (e.g., dropping balance from 295 to 290). The Backfiller would see "Not 300" and continue waiting. This effectively created a deadlock where the Backfiller almost never ran.

### 3. Solutions Implemented

#### A. Optimized "Controlled Deficit" Strategy

Modified `keepa_deals/token_manager.py` to implement a robust, high-throughput logic:

- **Threshold-Based Permission:** Instead of checking if `tokens > cost`, we check if `tokens > MIN_TOKEN_THRESHOLD` (set to 50). If true, the call proceeds immediately. This leverages the Keepa API's behavior of allowing the balance to dip negative.
- **Smart Recovery:** If `tokens < 50`, the system waits only until the balance recovers to **55** (Threshold + Buffer), rather than waiting for the full 300. This 5-token recovery takes ~1 minute, preventing long deadlocks.

#### B. Diagnostic Tooling

- Simulation Script (`Diagnostics/calculate_backfill_time.py`):



  Created a script to mathematically model the backfill process.

  - *Finding:* Confirmed that under the old strategy with concurrent usage, completion time approached infinity.
  - *Result:* The new strategy estimates **~17.3 days** to collect 10,000 deals (approx. 24 deals/hour), which is the theoretical speed limit of the API.

- **Logic Verification (`Diagnostics/test_token_manager_logic.py`):** Created a unit test suite to prove that the new code allows aggressive consumption and triggers the correct sleep durations during low-token states.

### 4. Technical Details

- **Files Modified:** `keepa_deals/token_manager.py`
- **New Artifacts:** `Diagnostics/calculate_backfill_time.py`, `Diagnostics/test_token_manager_logic.py`
- **Key Learnings:** When working with Token Buckets and concurrent processes, a "Wait for Max" strategy is dangerous. A "Threshold + Buffer" strategy is required to ensure throughput.
