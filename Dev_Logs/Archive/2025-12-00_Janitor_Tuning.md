# Dev Log: Janitor Grace Period Tuning & Touch Rate Verification

**Date:** December 2025 **Task:** Tune Janitor and Verify "Touch" Rate **Status:** **Success**

### 1. Overview

The primary objective was to reduce the aggressiveness of the "Janitor" task (`clean_stale_deals`), which is responsible for deleting deals from the database if they haven't been updated ("seen") for a set period. The previous default window of 24 hours was determined to be too short relative to the current backfill cycle time and the high rejection rate of the new pricing logic. This resulted in valid deals being prematurely deleted ("flapping") because the system couldn't re-scan and validate them fast enough to update their `last_seen_utc` timestamp.

### 2. Challenges & Analysis

- **The "Zombie" Deal Problem:** The system relies on a "Mark and Sweep" garbage collection strategy. For a deal to survive, it must be re-processed successfully to have its `last_seen_utc` timestamp updated. However, if a deal is *rejected* during re-processing (e.g., due to strict "Missing List at" logic), the `last_seen_utc` is **not** updated. This leaves the deal with a stale timestamp, making it a target for the Janitor despite still existing in the source data and potentially being valid.
- **Observability Gap:** It was previously unclear if existing deals were being "touched" (refreshed) or if they were being treated as entirely new or ignored. The existing logs only showed "Upserting X deals" without distinguishing between inserts (New) and updates (Refreshed).

### 3. Solutions Implemented

- **Extended Janitor Grace Period:** Modified `keepa_deals/janitor.py` to increase the default `grace_period_hours` from **24 to 72**. This provides a 3-day buffer, allowing the backfiller sufficient time to cycle through the database and for the user to address rejection logic issues without losing the existing dataset.

- Enhanced Backfill Logging:



  Updated



  ```
  keepa_deals/backfiller.py
  ```



  to inspect the batch before upserting.

  - **Logic:** The system now queries the `deals` table for the list of ASINs in the current chunk *before* performing the upsert.
  - **Metrics:** It calculates and logs `Count New` (ASINs not in DB) vs. `Count Refreshed` (ASINs already in DB).
  - **Benefit:** This explicitly verifies the "Touch Rate"—confirming that valid deals are being maintained in the database rather than silently dropped or re-added.

### 4. Outcome

The system is now significantly more resilient to slow backfill cycles. Deals will persist for 72 hours without updates before deletion, preventing the "empty dashboard" syndrome during long scans. The logs now provide clear visibility into data persistence, showing exactly how many items are being refreshed in each batch.

### 5. Files Changed

- `keepa_deals/janitor.py`
- `keepa_deals/backfiller.py`
