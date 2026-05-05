# Dev Log: Fix Token Loop & Ingestion Stall

**Date:** 2026-02-12
**Task:** Investigate Token Loop (Oscillation between 80-83 tokens) & Stuck Deal Count
**Status:** SUCCESS

## Overview
The user reported a "Token Loop" where the application consumed Keepa tokens (oscillating between ~80-83) but failed to ingest any new deals, leaving the dashboard stuck at 6-9 deals. Diagnostics revealed that the `smart_ingestor` was hitting a "Stop Trigger" (Deal <= Watermark) immediately upon fetching a page, suggesting that the API response was not strictly sorted by date.

## Challenges & Diagnosis
1.  **Initial Hypothesis (Future Watermark):** The first suspicion was a "Future Watermark" issue caused by clock skew. The ingestor was checking `deal_time > watermark`. If the watermark was slightly in the future (due to server lag), the ingestor would stop immediately.
    *   **Action:** Implemented `save_safe_watermark` with a 24-hour tolerance to prevent infinite loops caused by minor clock drift.
    *   **Result:** This was a valid safeguard but did not resolve the core issue.

2.  **Root Cause Discovery (Unsorted API Response):**
    *   **Diagnostic Tool:** Created `Diagnostics/inspect_latest_deals.py` to inspect the raw API response.
    *   **Finding:** The Keepa API response for `sortType=4` (Last Update) is **not strictly sorted**.
        *   Example: Index 0 (First Item) had a timestamp of `11:36` (Old / <= Watermark).
        *   Example: Index 6 (Later Item) had a timestamp of `13:58` (New / > Watermark).
    *   **Impact:** The ingestor's logic assumed a sorted list. It checked Index 0, saw it was old, and stopped processing immediately to save tokens. This caused it to miss the valid new deals at Index 6, 9, etc., leading to an infinite loop of fetching Page 0 and finding "nothing new."

## Implementation
1.  **Explicit Sorting:** Modified `keepa_deals/smart_ingestor.py` to **explicitly sort** the fetched page of deals by `lastUpdate` (Descending) *before* iterating to check against the watermark.
    *   This ensures that even if the API returns mixed results, the ingestor processes all available new deals (e.g., the `13:58` item) before encountering the old watermark (e.g., the `11:36` item).

2.  **Future Watermark Tolerance:**
    *   Updated `save_safe_watermark` to allow the watermark to drift up to 24 hours into the future.
    *   Timestamps are only clamped (reset to 24h ago) if they exceed this 24-hour future tolerance.
    *   This prevents infinite re-processing loops where a deal with a slightly future timestamp is clamped to `now` (which is still behind the deal time), causing it to be re-fetched indefinitely.

## Verification
*   **Watermark Advancement:** Logs confirmed the watermark successfully advanced from `11:36` to `11:52`.
*   **Deal Ingestion:** The `Deal Statistics` count increased from 9 to 11 immediately after the fix.
*   **Token Consumption:** Token usage dropped to 45 (active consumption for full product details), breaking the stuck oscillation pattern.
*   **Diagnostic Confirmation:** `Diagnostics/inspect_latest_deals.py` confirmed the unsorted nature of the API response, validating the necessity of the fix.

## Key Learnings
*   **Never Assume API Sorting:** Even if an API parameter suggests a sort order (`sortType=4`), always verify the raw response or implement explicit sorting in the application logic to prevent critical bugs.
*   **Stop Triggers:** Any logic that relies on a "Stop Condition" (e.g., `if date <= watermark: break`) MUST operate on a strictly sorted list.
*   **Clock Skew:** Always implement tolerance for server clock skew when comparing timestamps from external APIs. Strict equality or inequality checks against `now()` can lead to infinite loops if the server lags behind the API source.
