# Fix Dwindling Deals: Token Starvation & System Stability

## Task Overview
The system was experiencing a "Fast Diminishing Deals" phenomenon where the number of active deals on the dashboard would drop rapidly (e.g., from 450 to 250 in an hour). This indicated that the `update_recent_deals` task (Upserter), responsible for refreshing timestamps to prevent expiration, was failing to run effectively.

## Root Cause Analysis
Investigation revealed a complex interaction of three distinct failures:

1.  **Token Starvation & Deadlock:**
    *   The **Backfiller** task runs continuously and is designed to consume Keepa API tokens aggressively, keeping the balance near zero ("Controlled Deficit").
    *   The **Upserter** task is lightweight (needs ~5 tokens) but had logic to **skip execution** if tokens were low.
    *   **The Deadlock:** Even when changed to "wait" for tokens, the `TokenManager` logic enforced a "Recovery Mode" when the balance dropped below 50, requiring it to refill to 55 before allowing *any* request. Since the concurrent Backfiller constantly drained tokens as soon as they appeared, the balance never reached 55. The Upserter would wait indefinitely for a condition that never happened.

2.  **Scheduler Instability (Celery Beat):**
    *   The Celery Beat scheduler was frequently found to be down.
    *   **Cause:** Stale `celerybeat.pid` files left over from crashes or forceful kills prevented the service from restarting ("Pidfile already exists").

3.  **Zombie Redis Locks:**
    *   Forceful restarts (`kill_everything_force.sh`) killed the worker processes but left the Redis lock `update_recent_deals_lock` active with a long TTL (30 mins).
    *   Upon restart, the new Upserter task would see the lock, assume another instance was running, and exit immediately.

## Implementation & Fixes

### 1. Token Manager "Priority Pass"
Modified `keepa_deals/token_manager.py` to break the deadlock.
*   **Old Logic:** If `tokens < 50`, wait until `tokens >= 55`.
*   **New Logic (Priority Pass):** If the request is small (`<= 10` tokens) and `current_tokens >= cost`, **proceed immediately**, bypassing the recovery wait.
*   **Result:** The Upserter (cost 5) can now squeeze in its request even when the Backfiller keeps the balance at 40, ensuring deals are refreshed.

### 2. Upserter Task Logic
Updated `keepa_deals/simple_task.py`:
*   Removed the non-blocking check (`if not has_tokens: return`).
*   Replaced with `token_manager.request_permission_for_call(5)`, forcing the task to queue up rather than give up.

### 3. Operational Stability Scripts
Hardened the deployment scripts to ensure a clean state:
*   **`kill_everything_force.sh`**: Added commands to explicitly delete `celerybeat.pid` and clear `update_recent_deals_lock` from Redis.
*   **`start_celery.sh`**: Added a pre-flight check to remove any stale `celerybeat.pid` before launching the scheduler.

### 4. Diagnostic Tooling
Enhanced `Diagnostics/diagnose_dwindling_deals.py`:
*   **Robust Process Detection:** Changed `pgrep` to use regex (`celery.*beat`) to correctly identify the scheduler process even when command-line arguments are interleaved.
*   **Log Visibility:** Added logic to automatically tail `celery_beat.log` and `celery_worker.log` if issues are detected, enabling rapid root cause confirmation.

### 5. Consolidated Deployment
Created `deploy_update.sh` to automate the standard deployment workflow (Permissions -> Stop -> Start -> Reload -> Backfill) in a single command.

## Validation
*   **Logs:** Confirmed that `update_recent_deals` (Version 2.11) successfully started and completed while the Backfiller was simultaneously waiting for tokens (negative balance).
*   **Diagnostics:** Confirmed Celery Beat is stable and running. Redis locks are correctly managed.
*   **Outcome:** The "Dwindling Deals" issue is resolved. The Upserter now runs reliably alongside the Backfiller.
