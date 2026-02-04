# Fix Deal Collection Stall & System Instability

**Date:** 2026-02-04
**Status:** SUCCESS
**Files Modified:** 
- `keepa_deals/simple_task.py`
- `keepa_deals/backfiller.py`
- `start_celery.sh`
- `kill_everything_force.sh`
- `deploy_update.sh`
- `Diagnostics/force_clear_locks.py` (New File)

## Overview
The system was suffering from a critical "Deal Starvation" issue where no new deals were being collected (deal count stuck at 62). Despite previous attempts to fix priority inversion, the system remained stalled. Diagnostics revealed two primary root causes:
1.  **Zombie Locks:** The Backfill task had acquired a lock with a 10-day TTL but crashed or stalled, preventing any future backfill runs.
2.  **Environment Crashes:** The Celery Worker service was repeatedly crashing on startup with `ModuleNotFoundError: No module named 'celery'`, preventing any tasks (including the Upserter) from running effectively.
3.  **Token Starvation Loop:** When the Upserter did run, it would immediately abort if tokens were low (due to the Backfiller), rather than waiting, causing it to skip updates during busy periods.

## Challenges & Diagnosis
*   **Startup Failure:** The `start_celery.sh` script used `su -s ... www-data`, which in the production/sandbox environment caused the process to use the system Python instead of the virtual environment. This led to immediate crashes that were masked by the "resilient monitor" restarting them in a loop.
*   **Stale Locks:** The `kill_everything_force.sh` script relied on `redis-cli`, which was missing or unauthenticated in the environment, causing it to fail to clear Redis state. This left "Zombie Locks" from previous crashed workers alive for days.
*   **Logic Flaw:** The `simple_task.py` (Upserter) had a check `if not token_manager.has_enough_tokens(): break`. This meant that if the Backfiller (which is token-hungry) was running, the Upserter would see low tokens and *give up* instead of waiting its turn, leading to starvation.

## Solutions Implemented

### 1. Environment & Path Fixes
We modified `start_celery.sh`, `kill_everything_force.sh`, and `deploy_update.sh` to implement **Dynamic Python Detection**:
```bash
if [ -f "$APP_DIR/venv/bin/python" ]; then
    VENV_PYTHON="$APP_DIR/venv/bin/python"
else
    VENV_PYTHON="python3" # Fallback
fi
We also removed the su user switching to run processes as the current user, resolving permission conflicts and ensuring the virtual environment is correctly utilized.

2. Zombie Lock Prevention
Reduced TTL: Modified keepa_deals/backfiller.py to reduce the backfill_deals_lock timeout from 10 days to 1 hour. This ensures that even if a worker crashes hard, the system recovers automatically within an hour.
Force Clear on Deploy: Created Diagnostics/force_clear_locks.py and integrated it into deploy_update.sh. This script surgically deletes backfill_deals_lock and update_recent_deals_lock on every deployment, ensuring a clean slate.
3. Token Starvation Fix
Modified keepa_deals/simple_task.py to replace the "check and abort" logic with "request and wait" logic:

# Old:
# if not token_manager.has_enough_tokens(5): break

# New:
token_manager.request_permission_for_call(5) # Blocks until tokens available
This ensures the Upserter persists and eventually executes, even during heavy load.

Results
Services Stable: Celery Worker and Beat are running without crashes.
Locks Cleared: Diagnostics confirm locks are active only when tasks are running and have appropriate TTLs (~1 hour).
Pipeline Active: Logs confirm the Backfiller successfully resumed from Page 4 (Fetching page 4 of deals...) and the Upserter is running concurrently.
Data Flow: The system is actively fetching and processing batches of 150 deals per page.
Future Considerations
Deal Count Lag: The deal count in the UI (62) will rise slowly because the Backfiller processes data in chunks and is rate-limited by the Keepa API. This is expected behavior.
Lock Monitoring: The new 1-hour TTL should be sufficient, but if backfill tasks genuinely take longer than 1 hour per chunk (unlikely), this might need adjustment.
