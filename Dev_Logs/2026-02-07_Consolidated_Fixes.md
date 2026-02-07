# Consolidated Fixes: System Stabilization & Data Integrity (2026-02-07)

## Overview
This session addressed critical instability in token management ("Livelock") and data quality issues ("Zombie Deals") on the dashboard. This document consolidates all changes made across multiple steps.

## 1. Token Management: Fixing the "Stall" (Livelock)
**Problem:** The system would restart with ~40 tokens, run immediately, consume them down to 20, wait a minute, refill to 25, and repeat. This "Livelock" prevented the efficient "Burst Mode" (waiting for 280 tokens) from ever triggering, resulting in a perceived stall at 5 deals/min.

**Solution:**
*   **Force Recharge on Deploy:** Updated `deploy_update.sh` to execute `Diagnostics/force_pause.py` on every restart.
*   **Mechanism:** This script sets `keepa_recharge_mode_active = 1` in Redis, forcing `TokenManager` to block ALL requests until the bucket fully recharges to **280 tokens**.
*   **Result:** Deploys now cause a ~50-minute "Charging" pause (0 deals processed), followed by a high-speed "Burst" (300 deals in ~2 mins).

## 2. Data Integrity: Eliminating "Zombie Deals"
**Problem:** The dashboard displayed deals with "Missing Data" (`1yr Avg: -`, `List at: -`) or `Negative Profit`. This was due to legacy data in the DB and failed ingestion attempts.

**Solution (Multi-Layered):**
*   **API Gatekeeper (`wsgi_handler.py`):** The `/api/deals` endpoint now strictly filters out any deal where:
    *   `Profit <= 0`
    *   `List_at` is NULL or 0
    *   `1yr_Avg` is invalid (`-`, `N/A`, `0`)
    *   *Note:* This filtering happens at the SQL level, ensuring "Zombies" are invisible even if they exist in the DB.
*   **Ingestion Hygiene (`processing.py`):** Updated `clean_numeric_values` to correctly parse "1yr. Avg." as a float, ensuring future data is valid.
*   **Self-Healing Backfill (`backfiller.py`):** The backfiller now scans the DB for existing deals with missing critical data. If found, it treats them as "New" (ignoring the cache) to force a full re-fetch from Keepa, attempting to repair the data.

## 3. Safety: Incremental Upserts
**Verification:**
*   Confirmed that `keepa_deals/backfiller.py` dynamically reduces its batch size to **1 ASIN** when the refill rate is low (< 20/min).
*   Confirmed that it commits to the database **after every single deal**.
*   **Benefit:** This prevents data loss during the long "Recharge" pauses. If the system stops after processing deal #10 of 300, those 10 are safely saved.

## 4. Diagnostics
*   **New Tool:** `Diagnostics/check_pause_status.py` reports the exact state of the token bucket, refill rate, and whether "Recharge Mode" is active.
*   **Updated Suite:** `Diagnostics/run_suite.sh` now includes this check automatically.

## Summary of Changed Files
*   `deploy_update.sh`: Added force pause trigger.
*   `wsgi_handler.py`: Added strict SQL filters.
*   `keepa_deals/processing.py`: Improved number parsing.
*   `keepa_deals/backfiller.py`: Added self-healing logic.
*   `Diagnostics/`: Added `force_pause.py`, `check_pause_status.py`.
