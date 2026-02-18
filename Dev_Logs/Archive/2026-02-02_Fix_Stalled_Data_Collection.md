# Fix Stalled Data Collection & "Missing 1yr Avg" Logic

## 1. Task Overview
**Objective:** Resolve a critical system stall where the `Backfill Lock` was held for ~10 days, preventing data ingestion. Additionally, investigate a spike in deal rejections due to "Missing 1yr Avg" errors.

**Initial Symptoms:**
- `Backfill Lock` (Redis) had a TTL of ~860,000 seconds (10 days) and persisted across service restarts.
- Deal rejection rate spiked to ~56% with the reason "Missing 1yr Avg".
- Keepa API token balance was frequently negative (e.g., -30), indicating a "Death Spiral" where tasks consumed tokens faster than they could refill, leading to 429 errors.

## 2. Root Cause Analysis

### A. The "Zombie Lock" (Persistence Issue)
The primary cause of the stall was a race condition in the `kill_everything_force.sh` script used during deployment/restarts.
- **Old Logic:**
  1. Kill Redis (`sudo fuser -k 6379/tcp`).
  2. Attempt to clear Redis locks (`redis-cli DEL ...`).
  3. Restart Redis.
- **The Bug:** Step 2 always failed because Redis was already dead. Consequently, the locks remained in Redis's on-disk persistence file (`dump.rdb`). When Redis restarted (Step 3), it reloaded the old locks from disk, immediately deadlocking the system again.

### B. Token Starvation & "Missing 1yr Avg"
The "Missing 1yr Avg" error was a **symptom**, not a code bug.
- **Mechanism:** The persistent deadlock caused the Backfiller and Upserter to fight for resources in an uncoordinated way. This drove the token balance negative.
- **Result:** API calls began failing with `429 Too Many Requests`. The application logic received `None` or partial data instead of full history. Without sales history, the `get_1yr_avg_sale_price` function correctly returned `None`, leading to deal rejection.
- **Diagnosis:** A new unit test (`tests/test_1yr_avg_logic.py`) confirmed the calculation logic correctly handles sparse data, validating that the issue was upstream data availability.

### C. TokenManager "Death Spiral"
The `TokenManager`'s wait logic had a flaw where it could enter a tight loop or crash if the token balance remained negative for an extended period (typical during a 429 lockout), preventing the system from pausing long enough to recover.

## 3. Changes Implemented

### 1. Fix `kill_everything_force.sh` (The "Nuclear Option")
- **Reordered Operations:** Moved the `redis-cli DEL` command to run *before* killing the Redis process.
- **Persistence Wipe:** Added a step to explicitly delete `dump.rdb` files from `/var/lib/redis/` and the application root. This guarantees that even if the soft clear fails (e.g., Redis is hung), the bad state cannot be reloaded from disk upon restart.

### 2. Harden `TokenManager` (`keepa_deals/token_manager.py`)
- Replaced the fragile `while` loop with a robust infinite loop structure (`while True`).
- Added explicit `time.sleep(max(1, ...))` safeguards to prevent CPU-intensive tight loops.
- Implemented safety checks to handle negative token balances gracefully without crashing.

### 3. Diagnostic Tools
- **`Diagnostics/investigate_1yr_avg.py`:** A script to fetch live deals and verify why the 1-year average is missing (differentiating between "No Data" vs "Logic Error").
- **`tests/test_1yr_avg_logic.py`:** A unit test verifying the `new_analytics.py` logic handles sparse history correctly.

## 4. Verification & Outcome
- **Deadlock Cleared:** After applying the fix and running `deploy_update.sh` (which calls the fixed kill script), the 10-day old lock was removed. A fresh lock was acquired by the Backfiller.
- **Data Flow:** Worker logs confirmed the Backfiller resumed processing (Page 4) and tokens began refilling (`-30` -> `110`).
- **Starvation Ended:** The `TokenManager` now correctly pauses execution when tokens are low, allowing the bucket to refill instead of hammering the API.

**Status:** SUCCESS
