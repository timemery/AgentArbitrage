# Fix Zombie Deals Livelock via Safe Batch Reduction

**Date:** 2026-02-18
**Task:** Investigate and fix "Zombie Alert" (319 deals not updated in > 24 hours).
**Status:** Successful

## Overview

The system was reporting a critical "Zombie Alert," where 319 deals had not been updated for over 24 hours. The Smart Ingestor was running but failing to advance the watermark or save updates, effectively wasting tokens without making progress.

## Root Cause Analysis

The issue was identified as a **Token Livelock** occurring specifically on low-tier Keepa accounts (5 tokens/min refill rate).

1.  **Configuration Mismatch:**
    *   `BURST_THRESHOLD`: **40 tokens** (set low to ensure responsiveness/frequent updates).
    *   `SCAN_BATCH_SIZE`: **15 items** (for low refill rates).
2.  **The Deadlock Cycle:**
    *   The ingestor would wake up with ~40 tokens.
    *   It would "Peek" at 15 items (Cost: 15 * 2 = 30 tokens). Remaining: ~10 tokens.
    *   If any of these items required a "Commit" (full update, cost 20 tokens), the `TokenManager` would block the request because 10 < 20.
    *   The task would then abort due to `TokenRechargeError` or simply fail to proceed, **without saving the watermark**.
    *   The system would wait ~6-8 minutes, recharge to 40 tokens, and repeat the *exact same cycle* on the *exact same batch* of deals.
    *   This infinite loop caused the "Zombie" state.

## Solution Implemented

We opted for a **Safe Batch Reduction** strategy rather than increasing the burst threshold.

1.  **Reduced Batch Size:**
    *   Modified `keepa_deals/smart_ingestor.py` to reduce `SCAN_BATCH_SIZE` from **15** to **1** when the refill rate is < 10/min.
    *   **New Math:**
        *   Peek Cost: 1 * 2 = 2 tokens.
        *   Max Commit Cost: 1 * 20 = 20 tokens.
        *   **Total Max Cost:** 22 tokens.
    *   This fits comfortably within the **40-token** buffer, guaranteeing that the task can always complete the "Commit" phase if needed.

2.  **Preserved Responsiveness:**
    *   We deliberately **did not increase** the `BURST_THRESHOLD` to 80 (which would have allowed a batch size of 3).
    *   Staying at 40 ensures the system wakes up every ~8 minutes (at 5 tokens/min) rather than waiting 16+ minutes. This avoids the perception of a "stalled" system, which was a key user requirement.

## Outcome

*   **Livelock Broken:** The ingestor can now successfully process and save updates for at least 1 item per cycle.
*   **Zombie Clearance:** The system will steadily chew through the backlog of 319 zombie deals. While the throughput per cycle is lower (1 item vs potential 15), the *reliability* is 100%, ensuring the backlog is eventually cleared.
*   **Responsiveness:** The system remains active and visible to the user, updating frequently.

## Future Recommendations

*   **Monitor Throughput:** If the backlog clearance is too slow (> 24 hours), consider a slight increase to `BURST_THRESHOLD=60` and `SCAN_BATCH_SIZE=2` as a middle ground.
*   **Dynamic Tuning:** The system could theoretically auto-tune the batch size based on the *actual* available tokens at the start of the run, rather than a hardcoded constant.
