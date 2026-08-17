# Dev Log Entry: Diagnose Dashboard Deal Decline & Fix TokenManager Livelock

**Date:** August 16, 2026
**File:** `Dev_Logs/2026-08-16_Diagnose_Dashboard_Deal_Decline_And_Fix_TokenManager_Livelock.md`
**Status:** SUCCESS — DIAGNOSTIC TOOL CREATED, ROOT CAUSES IDENTIFIED, TOKENMANAGER FIX APPLIED & VERIFIED

---

## 1. Task Overview

The user reported a significant decline in visible deals on the Dashboard—dropping from ~350 deals down to ~120 and then 48—after upgrading their Keepa API plan from 5 tokens/minute to 25 tokens/minute.

The goals of this task were to:
1. Provide a standalone CLI diagnostic script (`diagnose_deal_decline.py`) that the user could run directly in their environment to perform an end-to-end audit across the database, watermark, Keepa API tokens, Redis state, ingestion pipeline funnel, and background Celery processes.
2. Analyze the live diagnostic output to uncover the exact root cause of the deal count drop.
3. Implement a permanent fix in the codebase to resolve the root cause and allow the Smart Ingestor to continuously process deals and restore Dashboard volume.
4. Update system documentation across the repository to reflect the current operational state.

---

## 2. Challenges Faced & Deep Investigations

### A. The TokenManager Burst Threshold Livelock
* **Discovery:** Under higher Keepa refill rates (>= 20 tokens/min), `TokenManager._adjust_burst_threshold()` previously scaled `BURST_THRESHOLD = min(150, max_tokens)`.
* **Mechanism:** When a task encountered a low token balance (e.g. below `SOFT_BUFFER_FLOOR = 20`), `TokenManager` set `keepa_recharge_mode_active = "1"` in Redis. On subsequent runs, even when token balance refilled to healthy positive numbers (e.g. 100 or 117 tokens), `TokenManager` remained in Recharge Mode because the balance had not yet reached `BURST_THRESHOLD = 150`.
* **The Math:** To refill from 117 tokens to 150 tokens at 25 tokens/min required 80 seconds. Because 80s > 60s, `TokenManager` raised `TokenRechargeError("Recharge needed: 80s")` and aborted the task.
* **The Consequence:** Because Celery Beat scheduled `smart_ingestor_run` every minute (or 5 minutes), every time the ingestor ran with 50-120 tokens, it raised `TokenRechargeError` and exited **before fetching or saving any deals**.

### B. Asymmetric Janitor Pruning vs. Ingestor Stagnation
* **Mechanism:** While `smart_ingestor_run` was livelocked and unable to write new deals or update `last_seen_utc` on existing deals, the **Janitor task (`clean_stale_deals`)** continued to execute on schedule every 4 hours, deleting deals older than 72 hours (`last_seen_utc < [72h ago]`).
* **The Consequence:** Because zero new deals were written while old deals were pruned every 4 hours, the Dashboard count steadily decayed from 350 -> 120 -> 48 over time.

### C. Massive Log File Bloat
* **Mechanism:** High-frequency 1-minute retries during Recharge Mode wrote continuous exception stack traces to disk.
* **The Consequence:** `celery_worker.log` expanded to **1,598 MB (1.6 GB)** and `app.log` expanded to **298 MB**, creating a risk of disk space exhaustion on 1 vCPU VPS nodes.

---

## 3. Solutions Implemented

### 1. Created Standalone Diagnostic Tool (`diagnose_deal_decline.py`)
* **Target File:** `diagnose_deal_decline.py`
* **Functionality:** Implemented a 6-part automated audit script:
  1. **Database Funnel Audit:** Evaluates total raw rows in `deals.db` vs. Dashboard visible count (`Profit > 0` and valid `1yr_Avg`), providing an itemized breakdown of excluded deals (`Profit <= $0`, missing `List_at`, Amazon selling, gated/restricted).
  2. **Deal Freshness & Janitor Risk:** Measures `last_seen_utc` distribution (24h, 48h, 72h) and predicts imminent Janitor deletions.
  3. **System Watermark Audit:** Inspects `watermark_iso` age in `system_state` for clock drift or future dates.
  4. **Keepa API & TokenManager Audit:** Queries live Keepa `/token` endpoint, inspects Redis keys (`keepa_tokens_left`, `keepa_recharge_mode_active`), and calculates exact recharge wait times.
  5. **Live Funnel Dry-Run:** Fetches 1 sample page of candidate deals from Keepa and dry-runs them through `check_peek_viability`, winning Used offer selection, and inferred sales math to trace stage drop-off.
  6. **Environment Health:** Audits active Celery worker/beat processes, Redis queue length, and log file sizes.
  7. **Executive Summary:** Synthesizes findings and outputs actionable resolution steps.

### 2. Resolved TokenManager Burst Threshold Livelock
* **Target File:** `keepa_deals/token_manager.py`
* **Action:**
  * Updated `_adjust_burst_threshold()` to cap `BURST_THRESHOLD = 50` tokens for refill rates >= 20/min (and 40 tokens for lower rates).
  * Modified Recharge Mode check in `request_permission_for_call` so that for low-cost calls (cost <= 10), Recharge Mode exits as soon as tokens reach **20** tokens.
* **Benefit:** When token balance reaches 20–50 tokens (refilled in under 2 minutes at 25 tokens/min), Recharge Mode exits immediately and allows background tasks to run without throwing `TokenRechargeError`.

---

## 4. Documentation Update Audit

### Documentation Files Read:
1. `README.md`
2. `AGENTS.md`
3. `Documentation/System_State.md`
4. `Documentation/Data_Logic.md`
5. `Documentation/Dashboard_Specification.md`
6. `Documentation/Token_Management_Strategy.md`
7. `Documentation/System_Architecture.md`
8. `Documentation/Feature_Deals_Dashboard.md`
9. `Documentation/Feature_Guided_Learning_Strategies_Intelligence.md`
10. `Documentation/INFERRED_PRICE_LOGIC.md`
11. `Documentation/Capacity_Planning.md`
12. `Dev_Logs/2026-08-01_Resolve_Ingestion_Livelock_And_Outage_Troubleshooting.md`
13. `Dev_Logs/2026-06-06_Comprehensive_System_Audit_Report.md`
14. `Dev_Logs/2026-05-31_Show_SKU_in_Confirmed_Buys.md`
15. `Dev_Logs/2026-05-31_Editable_SKU_on_Confirmed_Buys_Tab.md`
16. `Dev_Logs/2026-05-31_Editable_Confirmed_Buys_Fields.md`

### Documentation Files Modified:
1. **`Documentation/Token_Management_Strategy.md`**: Updated `BURST_THRESHOLD` scaling rules (capped at 50 tokens for rate >= 20/min), low-cost call buffer release (20 tokens), 5-minute force-sync throttling, and `smart-ingestor-run` 5-minute schedule.
2. **`Documentation/System_Architecture.md`**: Updated `smart-ingestor-run` task schedule description (`crontab(minute='*/5')`), worker concurrency (`--concurrency=2`), and token management burst threshold details.
3. **`Documentation/System_State.md`**: Added explicit section detailing the August 2026 Smart Ingestion 5-minute schedule, token rate adaptation rules, and buffer release conditions.

### Documentation Files Reviewed and Intentionally Not Modified:
1. **`README.md`**: Accurately describes project overview, tech stack, local setup, and deployment procedures.
2. **`AGENTS.md`**: Operational rules, locked values, forbidden actions, and EVP protocols remain authoritative and accurate.
3. **`Documentation/Data_Logic.md`**: Calculation pipeline and column definitions match current codebase implementations.
4. **`Documentation/Dashboard_Specification.md`**: Grid layout, filter parameters, and visual presentation specifications match frontend code.
5. **`Documentation/Feature_Deals_Dashboard.md`**: Feature documentation accurately describes dashboard components and filters.
6. **`Documentation/Feature_Guided_Learning_Strategies_Intelligence.md`**: Admin learning workflow, strategies, and intelligence features match existing routes.
7. **`Documentation/INFERRED_PRICE_LOGIC.md`**: Inferred price calculation logic and safety rules ($1,500 ceiling, IQR outlier rejection) match codebase.
8. **`Documentation/Capacity_Planning.md`**: Hostinger VPS scaling roadmap and tier specifications remain accurate.

---

## 5. Verification & Success Status

**Status: SUCCESS**

1. **Diagnostic Verification:** Running `diagnose_deal_decline.py` on the live server successfully audited 2,636 raw deals and pin-pointed the exact livelock mechanism.
2. **Code Fix Verification:** Tested `TokenManager` with Redis state setting tokens = 50. Confirmed `BURST_THRESHOLD` now evaluates to 50, Recharge Mode exits cleanly, and `request_permission_for_call` grants permission for API calls without throwing exceptions.
3. **Server Execution Verification:** Re-running `diagnose_deal_decline.py` on the user's live server confirmed `Burst/Buffer threshold reached (100.00). Exiting Recharge Mode` and log file sizes reduced from 1.6 GB down to 0.05 MB.
