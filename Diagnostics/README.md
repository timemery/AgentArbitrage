# Diagnostics Suite

This directory contains the standard diagnostic tools for the Agent Arbitrage system.

## The Core Suite

To run the standard health check, execute:

```bash
./Diagnostics/run_suite.sh
```

This script executes the following three critical diagnostics in order:

### 1. `system_health_report.py` (Green Light Check)
*   **Purpose:** Verifies that the entire infrastructure is online and configured correctly.
*   **Checks:** Environment variables, API keys, Redis connectivity, Celery processes (Worker/Beat), Database integrity, and API connectivity (Keepa/xAI).
*   **Output:** A Pass/Fail/Warn summary for each component.

### 2. `comprehensive_diag.py` (Deal Statistics)
*   **Purpose:** detailed view of the deal data pipeline.
*   **Checks:** Total deals, deals visible on dashboard (Margin >= 0), rejection rates, and specific rejection reasons (e.g., "Missing 1yr Avg").
*   **Verification:** Compares internal Database counts with the API endpoints to ensure the Dashboard is seeing the correct data.

### 3. `diagnose_dwindling_deals.py` (Pipeline Flow)
*   **Purpose:** Deep dive into data freshness and pipeline blockages.
*   **Checks:** Redis Locks (Zombie locks), Deal Age distribution (are deals getting stale?), and Scheduler status.
*   **Use Case:** Run this if the "Deal Count" is dropping or deals seem "stuck".

---

## Utilities

*   `kill_redis_safely.py`: A safety script used by `kill_everything_force.sh` to wipe Redis state cleanly.
*   `find_redis_config.py`: Helper to locate Redis configuration files.
*   `reset_logs.sh`: Truncates large log files to safe sizes.
*   `manual_watermark_reset.py`: Reset the ingestion watermark to force a re-scan.

---

## Legacy Scripts

The `Legacy/` directory contains older, redundant, or one-off diagnostic scripts. These are kept for archival purposes but are not part of the standard daily workflow.
