# Dev Log: Fix Token Starvation & Zombie Locks
**Date:** 2026-02-03
**Status:** SUCCESS

## Overview
The system was experiencing "lugubrious" (extremely slow/stalled) data collection and persistent "zombie locks" that survived deployment restarts. The primary symptoms were:
1.  **Token Starvation:** Celery workers were driving the Keepa API token balance deep into the negative (e.g., -150), causing 30+ minute wait times for all tasks.
2.  **Deployment Deadlocks:** After running `deploy_update.sh`, workers would immediately report "Task is already running" and exit, despite the system having just been restarted.

## Challenges & Root Causes

### 1. The Token Debt Spiral (Race Condition)
The `TokenManager` relied on local, instance-specific state. When multiple Celery workers (concurrency: 4) ran simultaneously:
*   Worker A checked tokens: "5 available. Go."
*   Worker B checked tokens: "5 available. Go." (Reads stale/local state)
*   Worker C checked tokens: "5 available. Go."
*   **Result:** All workers fired requests. Keepa allows deficit spending, so the balance dropped to -15, then -20, etc. The refill rate (5/min) could never catch up to the burst consumption, leading to massive wait times (wait = deficit / refill_rate).

### 2. Zombie Locks (Persistence Paradox)
The deployment script (`deploy_update.sh` -> `kill_everything_force.sh`) attempted to clear Redis locks by deleting the `dump.rdb` file. This failed because:
*   **Redis Shutdown Behavior:** When Redis receives a kill signal (SIGTERM), it dumps its *current in-memory state* to disk before exiting.
*   **The Loop:** Our script deleted the file -> Redis shutdown -> Redis re-saved the file (with locks) -> Redis restarted -> Redis loaded the file (locks restored).
*   **Environment Issue:** The bash script used `redis-cli`, which failed silently due to missing authentication/env vars on the production server, meaning `DEL` commands were never executed.

## Solutions Implemented

### 1. Distributed Token Bucket (Redis-Backed)
Refactored `keepa_deals/token_manager.py` to use a **Shared Redis State**.
*   **Atomic Reservation:** Before making an API call, workers use `redis.decrby()` to atomically reserve tokens.
*   **Optimistic Locking:** If the reservation drops the balance below the `MIN_TOKEN_THRESHOLD` (50), the worker immediately `reverts` the reservation (`incrby`) and enters a wait loop.
*   **Outcome:** Workers now coordinate. If tokens are low, they queue up rather than digging a deeper hole.

### 2. The "Brain Wipe" Kill Script
Overhauled `kill_everything_force.sh` to guarantee a clean slate.
*   **Python Wrapper:** Replaced brittle `redis-cli` commands with a robust Python script (`Diagnostics/kill_redis_safely.py`).
*   **Logic:**
    1.  Connects using the application's `redis-py` library (handling auth/host correctly).
    2.  Executes `FLUSHALL` (Wipes memory *before* shutdown).
    3.  Executes `SAVE` (Forces disk overwrite with empty state).
*   **Outcome:** Zombie locks are permanently eliminated.

### 3. Concurrency Verification
Addressed concerns that the 10-day `backfill_deals_lock` was blocking freshness updates.
*   Verified `keepa_deals/simple_task.py` (Upserter) explicitly **ignores** the backfill lock.
*   The system now runs Backfill (Historical) and Upsert (Freshness) tasks concurrently, managed safely by the new Token Manager.

## Validated Files
*   `keepa_deals/token_manager.py`
*   `kill_everything_force.sh`
*   `Diagnostics/kill_redis_safely.py`
*   `Diagnostics/find_redis_config.py` (Restored tool)

## Conclusion
The system is now resilient against concurrency-based token starvation and deployment persistence issues. Data collection has resumed at maximum efficient throughput.
