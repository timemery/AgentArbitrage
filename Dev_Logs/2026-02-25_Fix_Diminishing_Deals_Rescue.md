# Fix Diminishing Deals: Stale Rescue & Ceiling Check

**Date:** 2026-02-25
**Author:** Jules (AI Agent)
**Status:** Success (Verified in Production)

## Overview
The user reported a critical issue where the number of active deals in the system was steadily declining ("diminishing"), dropping from ~500 to 414, and then even lower. This was occurring despite valid inventory existing. The goal was to identify why deals were disappearing and implement a robust mechanism to preserve them.

## Root Cause Analysis
The investigation revealed two distinct but interacting causes for the "diminishing deals" phenomenon:

1.  **Stale Data & Janitor Deletion:**
    -   The `clean_stale_deals` (Janitor) task runs every 4 hours and strictly deletes any deal record where `last_seen_utc` is older than 72 hours.
    -   The primary `smart_ingestor` relies on Keepa's "Delta Fetch" (finding products updated *since* a watermark).
    -   Stable products (e.g., long-tail books with consistent prices) often do not generate Keepa updates for days. Consequently, they are not returned in the delta fetch, their `last_seen_utc` is not updated, and they eventually cross the 72-hour threshold and get deleted.

2.  **Unrealistic Pricing & Ceiling Check:**
    -   Previously, the system would "preserve" the `List at` (Peak) price during lightweight updates to save tokens.
    -   However, if the market crashed (e.g., Amazon lowers the New price significantly), the preserved `List at` price would remain high, showing a "fake profit."
    -   When we implemented a fix to update these prices, many deals revealed their true nature: they were no longer profitable.
    -   The Dashboard filters hide deals with `Profit <= 0`. Thus, "correcting" the data caused a visible drop in the deal count (from 416 to 324), which looked like a bug but was actually a feature (hiding bad deals).

## Solutions Implemented

### 1. Stale Deal Rescue Mechanism (`keepa_deals/smart_ingestor.py`)
To prevent valid deals from being deleted by the Janitor, I implemented a proactive rescue system:
-   **Function:** `rescue_stale_deals(token_manager, limit=20)`
-   **Logic:**
    1.  Queries the database for deals where `last_seen_utc` is older than 48 hours (entering the "danger zone").
    2.  Checks the Refill Rate: Skips execution if tokens are low (< 10/min).
    3.  Fetches fresh lightweight stats for these ASINs from Keepa.
    4.  Updates the record in the database, refreshing `last_seen_utc` to `NOW`.
-   **Tuning:** The batch limit was increased from 5 to **20 deals per run** (every minute) to ensure the system can clear any backlog faster than the Janitor can delete it.

### 2. Amazon Ceiling Check (`keepa_deals/processing.py`)
To prevent "fake profits" from persisting during updates:
-   **Logic:** In `_process_lightweight_update`, the system now compares the preserved `List at` price against the current **Amazon New Price** (and 90/180/365d averages).
-   **Action:** If `List at > (Amazon New * 0.90)`, the List Price is clamped down to that ceiling.
-   **Result:** This ensures realistic profit calculations. If the resulting profit becomes negative, the deal is kept in the database (persisted) but effectively hidden from the Dashboard, protecting the user from bad buys.

### 3. Transparency & Logging
-   Added explicit warning logs in `smart_ingestor.py`:
    `WARNING: Stale Rescue: ASIN X updated but Profit is now $-5.00. It will be hidden from the dashboard.`
    This provides immediate feedback to the admin about *why* the deal count might drop after a rescue operation.

## Verification
-   **Regression Test:** Created `tests/test_stale_deal_rescue.py` which confirmed:
    -   Stale deals are successfully identified and updated (`last_seen_utc` refreshed).
    -   The Ceiling Check correctly clamps prices (Test case: $50 -> $27).
    -   The Janitor still functions correctly for truly dead deals.
-   **Production:** The user confirmed the deal count initially stabilized (414 -> 416). A subsequent drop to 324 was analyzed and confirmed to be the result of the Ceiling Check correctly filtering out unprofitable items, as evidenced by the new logs.

## Key Learnings
-   **Persistence vs. Visibility:** A drop in the "Deals Found" count is not always data loss. It is often the result of improved data quality filtering. Logging this distinction is critical for user confidence.
-   **Delta Fetch Limitations:** Relying solely on API delta fetches is insufficient for maintaining a persistent database with a TTL (Time To Live) policy. Active maintenance (Rescue) is required for stable items.
