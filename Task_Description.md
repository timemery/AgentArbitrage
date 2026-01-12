# Investigation Report: Rejection Rate & Deals Leak

**Date:** 2026-01-12
**Status:** Investigation Complete - Critical Bug Found

## 1. Executive Summary
The investigation into the 91.71% rejection rate and the "slow leak" of deals has identified a **critical regression** in the data mapping logic. The `FUNCTION_LIST` in `keepa_deals/field_mappings.py` is out of sync with `keepa_deals/headers.json` by **2 items** (245 functions vs. 247 headers).

This misalignment causes the `get_list_at_price` function (and others) to populate the wrong columns in the internal data structure. Consequently, the safety check in `processing.py`, which verifies that `row_data['List at']` is present, fails for valid deals, causing them to be erroneously rejected.

This high rejection rate is the direct cause of the "Slow Leak." The system rejects valid deals during updates, preventing their `last_seen_utc` timestamps from being refreshed. As a result, the "Janitor" task correctly identifies these valid-but-unrefreshed deals as "stale" (>72 hours) and deletes them, causing the total deal count to plummet over time.

---

## 2. Detailed Findings

### A. The "List at" Rejection
-   **Symptom:** 100% of rejections were due to "Missing List at".
-   **Validation:** A reproduction script (`reproduce_rejection.py`) confirmed that even when `xAI` approved a deal (e.g., "Campbell Biology", ASIN `0134093410`) and a valid Peak Price was calculated ($28.39), the deal was still rejected with "List at is missing".
-   **Root Cause:**
    -   `keepa_deals/headers.json` contains **247** column definitions.
    -   `keepa_deals/field_mappings.py` contains **245** entries in `FUNCTION_LIST`.
    -   Because `processing.py` uses `enumerate(FUNCTION_LIST)` to map functions to `headers[i]`, the mismatch causes a shift. The value for `List at` is likely being written to a subsequent column (e.g., `Trough Season`), leaving `List at` empty or populated with invalid data.

### B. The "Slow Leak" Mechanism
1.  **Inflow Blocked:** The Backfiller and Upserter run the processing logic. Due to the rejection bug, valid deals (both new and existing) are rejected and **not saved** to the database.
2.  **Timestamps Stale:** Because existing deals are rejected during the "Refill" update cycle, their `last_seen_utc` timestamp is not updated.
3.  **Outflow Active:** The Janitor task runs every 4 hours and deletes any deal where `last_seen_utc > 72 hours`.
4.  **Result:** The database is being emptied by the Janitor because the Refiller cannot "touch" the records to keep them alive.

### C. Artificial Backfill Limiter & Profit Fix
-   These recent changes were investigated and cleared. They are not the cause of the issue. The Profit Fix logic handles negative fees correctly, and the Backfill Limiter logic works as intended (though it relies on the same broken processing pipeline).

### D. XAI Rejection
-   The investigation confirmed that the XAI Reasonableness Check is working correctly and *does* reject questionable items (e.g., an outdated "JavaScript & jQuery" book priced at $2.85 was correctly rejected by AI). This is expected behavior and distinct from the alignment bug.

---

## 3. Recommended Fix (Task Description)

**Task:** Fix Column Alignment Mismatch in Field Mappings

**Objective:** Synchronize `keepa_deals/field_mappings.py` with `keepa_deals/headers.json` to resolve the high rejection rate.

**Steps:**
1.  **Analyze Alignment:** Compare `headers.json` and `field_mappings.py` to identify exactly which 2 columns are missing from the `FUNCTION_LIST`.
    *   *Hint:* The columns `Offers 180` and `Offers 365` (or similar recent additions like `Drops 180`) are likely candidates.
2.  **Update Mappings:** Add `None` entries (or the correct function, if applicable) to `FUNCTION_LIST` in `keepa_deals/field_mappings.py` at the correct indices to restore alignment (Total count must match 247).
3.  **Verify:**
    *   Run a script to confirm the counts match.
    *   Run a reproduction script on a known valid ASIN (e.g., `0134093410`) to confirm it is now **Saved** instead of Rejected.
4.  **Monitor:** After deployment, verify that the "Rejection Rate" drops significantly and the "Deals Found" count begins to rise as the Backfiller/Refiller successfully processes items.
