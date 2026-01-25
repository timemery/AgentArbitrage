# Dev Log: Fix Dwindling Deals & Watermark Logic (Partial Success)

**Date:** 2026-01-24  
**Task:** Diagnose and fix "dwindling deals" where the dashboard count was dropping/stagnant and new deals were not being ingested.

## Overview
The system was observed to be stuck. The `backfill_deals` task was holding a lock indefinitely, blocking the `update_recent_deals` (Upserter) task. Additionally, when the Upserter did run, it failed to save any new deals. The goal was to unblock the system and restore the flow of fresh data.

## Challenges & Root Cause Analysis

### 1. The 2015 vs. 2026 Time Warp
The most critical discovery was a massive discrepancy between the server time and the API data time.
*   **Server Time:** Jan 2026 (Correct).
*   **Keepa Data:** The API returns data starting from **Jan 2015**.
*   **The Problem:** When we reset the watermark to "Yesterday" (Jan 23, 2026), the system ignored all incoming data because `2015 < 2026`. The system effectively thought all data was "ancient history" and processed nothing.

### 2. Configuration Artifacts
The Keepa Query configuration (`keepa_query.json`) uses:
*   `"dateRange": 4` (All Time)
*   `"sortType": 4` (Last Update / Percentage)
*   **Impact:** This configuration causes the API to return the "Best Deals of All Time" (e.g., massive drops from 10 years ago) rather than "Newest Deals". This floods the system with 10-year-old data, which it struggles to process relevantly for a "Recent Deals" dashboard.

### 3. Infinite Backlog Loop
The Upserter task tried to fetch 10 years of history (from the 2015 data start). It would hit token limits (consuming ~20 tokens per ASIN for history), throttle (sleep), and eventually timeout or stop *without* updating the watermark. This caused an infinite loop of trying to fetch the same 2015 batch over and over.

## Actions Taken

### 1. Load Shedding (`keepa_deals/simple_task.py`)
Implemented a **Circuit Breaker**:
*   Added `MAX_NEW_DEALS_PER_RUN = 200`.
*   **Logic Change:** If the task finds more than 200 new deals, it stops fetching, processes the batch, and **forcefully updates the watermark** to the newest deal found in that batch.
*   **Benefit:** This allows the system to "chew through" the massive 2015 backlog incrementally instead of getting stuck in a token-exhaustion loop.

### 2. Smart Watermark Reset (`Diagnostics/manual_watermark_reset.py`)
Created a "Data-Aware" reset tool.
*   Instead of setting the watermark to `Server_Time - 24h`, it fetches the *actual* newest deal from Keepa (e.g., from 2015).
*   Sets the watermark to `Newest_Deal_Time - 24h`.
*   **Benefit:** This tricks the system into accepting the 2015 data as "new", breaking the "Future Watermark" paralysis.

### 3. Diagnostics (`Diagnostics/diagnose_dwindling_deals.py`)
Created a script to visualize the blockage:
*   Checks Redis Locks (`backfill_deals_lock`).
*   Checks Deal Age (revealing the 2015 timestamps).
*   Checks Database Counts.

## Outcome: Partial Success / Unresolved
*   **Success (Mechanical):** The system is unblocked. The Backfiller lock is free, the Upserter is running, and the watermark is updating (moved to 2015-01-23).
*   **Failure (Functional):** The flow of *useful* fresh deals has not been restored.
    *   Total Processed count only rose slightly (206 -> 212).
    *   **High Rejection Rate:** The 2015 data is being rejected (10 rejections, "Missing List at"). This is expected; trying to price a 2015 deal using 2026 logic (or lacking 2026 context) leads to AI rejections.
    *   **Conclusion:** The system is technically "working" (processing data), but the **data itself** (2015 artifacts) is the bottleneck.

## Recommendations for Next Agent
1.  **Investigate `keepa_query.json`:** The `dateRange: 4` (All Time) setting is dangerous. It forces the system to process 10 years of history. Changing this to `dateRange: 3` (90 Days) or `dateRange: 1` (Day) would likely force the API to return *actual* 2026 data.
2.  **Verify API Sort Order:** Ensure `sortType` is actually returning "Newest" deals. The current behavior suggests it might be returning "Biggest Drop" regardless of date.
3.  **Accept the "Ancient Data":** If the user *must* use `dateRange: 4`, the system needs a way to fast-forward through the 2015-2025 gap without burning tokens on 2015 deals that will be rejected anyway.
