# Dev Log: Smart Ingestor Refactor & Token Drain Fix
**Date:** 2026-02-09
**Author:** Jules (AI Agent)
**Status:** Completed & Deployed

## 1. Executive Summary
This task successfully consolidated the deal ingestion pipeline into a single, efficient `Smart_Ingestor`, replacing the legacy `backfiller.py` and `simple_task.py`. Crucially, it identified and resolved a critical "Token Drain" bug where the system consumed ~120 tokens/hour simply by polling the API during recharge periods. The deployment process was also streamlined with improved sync scripts.

## 2. Key Changes

### A. The "Smart Ingestor" (`keepa_deals/smart_ingestor.py`)
*   **Consolidation:** Replaced the split "Backfiller vs. Upserter" architecture with a single unified task running every minute.
*   **Peek Strategy (Stage 1 Filtering):**
    *   Implmented a low-cost "Peek" (2 tokens) using `stats=365`.
    *   Filters candidates based on profitability heuristics *before* committing to a full fetch (20 tokens).
    *   **Benefit:** Increases effective scanning capacity by ~10x.
*   **Watermark Ratchet:**
    *   Sorts new deals by `Last Update` (Ascending).
    *   Updates the watermark after *every* batch (whether deals are saved or rejected).
    *   **Benefit:** Prevents infinite loops on "bad" deals by ensuring the system always moves forward.
*   **Zombie Defense:** Detects "Zombie" rows (missing critical fields like `List Price`) in the DB and forces a repair fetch.

### B. The Token Drain Fix (`keepa_deals/token_manager.py`)
*   **The Bug:** During "Recharge Mode" (low-tier strategy), `TokenManager` was polling the Keepa API (`sync_tokens`) every 30 seconds to check if tokens had refilled. Each check consumed 1 token (or bandwidth/quota).
*   **The Impact:** On a 5 token/min plan, consuming ~2 tokens/min just for checking reduced effective refill by 40%, causing the system to stall or drain.
*   **The Fix:** Updated `_wait_for_tokens` to calculate the required wait time mathematically and **sleep** for the full duration without polling.
*   **Result:** Zero token consumption during wait periods. Efficient recharge verified (57 -> 62 -> 67 tokens).

### C. Logic Enhancements (`keepa_deals/stable_calculations.py`)
*   **Amazon Ceiling:** Defined as the MINIMUM of Current, 180-day Avg, and 365-day Avg Amazon prices.
*   **AI Bypass:** If the calculated "List at" price is capped by this ceiling (with a 10% safety buffer), the expensive XAI Reasonableness Check is skipped.

### D. Deployment Improvements
*   **`sync_from_repo.sh`:** Updated to include a `--reset` flag and clearer instructions for handling uncommitted changes.
*   **Workflow:** Established `git checkout main && git pull` as the standard start-of-task procedure.

## 3. Verification & Results
*   **Token Efficiency:** Verified via logs that `ForkPoolWorker` enters a "Wait Loop" and remains silent (no API calls) until the target is reached.
*   **Ingestion:** Confirmed `Smart_Ingestor` wakes up after recharge and successfully processes deals.
*   **Dashboard:** Deal count temporarily dropped (due to 3-day pause/Janitor cleanup) but is expected to rise rapidly as the new ingestor catches up.

## 4. Next Steps
*   **Monitor:** Watch the dashboard deal count to ensure it refills to ~200+.
*   **Standardize:** Ensure all future tasks start from `main` to avoid the git conflicts encountered during this hotfix.

## 5. Artifacts
*   `keepa_deals/smart_ingestor.py` (New Core)
*   `Archive/backfiller_legacy.py` & `Archive/simple_task_legacy.py` (Archived)
*   `keepa_deals/token_manager.py` (Patched)
