# 2026-01-25 - Fix Keepa Epoch Bug and API Date Range (The "Ancient Data" Fix)

## Task Overview

The system was experiencing a critical stall where the ingestion pipeline (Upserter and Backfiller) was getting clogged with data from 2015. Despite visible "activity," the system was rejecting almost all deals because the AI Reasonableness Check correctly flagged 2015 prices as irrelevant for 2026.

This task focused on diagnosing why "Ancient Data" was being fetched and correcting the system's time perception.

## Challenges Faced

1. **The "Time Machine" Bug (Keepa Epoch):**
   - **Symptom:** The system was calculating timestamps (e.g., `7924816` minutes) as being from January 2015.
   - **Root Cause:** The codebase was using a **Keepa Epoch of January 1, 2000**. However, for the specific API endpoints/data fields we are using, Keepa actually uses an epoch of **January 1, 2011**.
   - **Impact:** This 11-year offset caused fresh 2026 data to be interpreted as 2015 data, leading the system to believe it was constantly processing a backlog of ancient history.
2. **API Rate Limiting (429s):**
   - During diagnosis, the Keepa API aggressively rate-limited requests (429 Errors), making it difficult to verify live data timestamps.
   - **Solution:** We enhanced `Diagnostics/manual_watermark_reset.py` to be robust against 429s. Instead of relying on a live API call to find the "newest deal" to set the watermark, it now defaults to forcing the watermark to **24 hours prior to Server Time (UTC)**. This allows the system to recover even when the API is uncooperative.
3. **API Configuration:**
   - The `keepa_query.json` was configured with `"dateRange": 4` (All Combined), which theoretically allows fetching historical data. While not the primary cause of the date *interpretation* error, restricting this to 90 days was a key requirement to prevent true backlog issues.

## Actions Taken

1. **Fixed Keepa Epoch:**

   - Updated

      

     ```
     KEEPA_EPOCH
     ```

      

     /

      

     ```
     datetime(2000, 1, 1)
     ```

      

     to

      

     `datetime(2011, 1, 1)`

      

     in four critical files:

     - `keepa_deals/simple_task.py`
     - `keepa_deals/backfiller.py`
     - `keepa_deals/stable_products.py`
     - `Diagnostics/manual_watermark_reset.py`

2. **Restricted API Query:**

   - Updated `keepa_query.json` to use **`"dateRange": 3`** (90 Days) instead of `4`.

3. **Forced Watermark Reset:**

   - Ran the updated `manual_watermark_reset.py` to set the system's `watermark_iso` to "Yesterday". This ensures the Upserter (`simple_task.py`) starts its delta-sync from a relevant point in time.

## Verification & Results

- **Timestamp Verification:** Using `Diagnostics/test_keepa_query.py` (after the fix), we confirmed that raw Keepa timestamps (e.g., `7924816`) now correctly resolve to **January 2026**.
- **System Unblocked:** The diagnostic tool `diagnose_dwindling_deals.py` confirmed that the Upserter lock was active and processing deals, indicating the pipeline is no longer stalled on ancient data.
- **Backfiller Triggered:** The Backfill task was successfully queued to begin populating the historical data for the fresh 2026 deals.

## Success Status

**SUCCESS**

The system's "internal clock" has been corrected. It now correctly identifies 2026 data as current and has been configured to ignore older history. The ingestion pipeline is unblocked and running.