# Fix Smart Ingestor 100% Rejection (Sparse Data)

## Overview
The Smart Ingestor pipeline, which consolidates all data collection into a single Celery task (`keepa_deals.smart_ingestor.run`), was failing to collect any deals (0 saved deals over several days). Diagnostics revealed a 100% rejection rate, with 90% of deals failing due to "Missing 'List at'" and 6% failing due to "Missing '1yr Avg'".

Upon investigation, the root cause was identified as overly strict data validation on **Sparse Data** items (low-velocity books). The "Inferred Sales" logic, which attempts to calculate a precise market price based on rank drops, was returning `None` for items with insufficient recent history. This caused valid, profitable inventory to be discarded.

Additionally, a critical logic order bug in `processing.py` was prematurely rejecting deals *before* their analytics were even calculated, and a `TypeError` in `stable_deals.py` was causing intermittent crashes.

## Challenges
1.  **100% Rejection Rate:** The system was correctly fetching deals but rejecting all of them. The logs showed "Ingestion Rejected - Invalid 'List at'" for nearly every item.
2.  **Sparse Data Reality:** Many profitable books have low sales velocity (e.g., 1 sale per month). The previous logic required dense data to infer a price, which these items inherently lack.
3.  **Pipeline Logic Error:** In `keepa_deals/processing.py`, a validation block checking for `1yr. Avg.` was placed *before* the function `get_1yr_avg_sale_price()` was called. This guaranteed rejection for any deal that didn't already have this value populated (which is all new deals).
4.  **Legacy Compatibility:** A helper function `last_update` in `stable_deals.py` was updated to require a `logger` argument, but legacy calls in the codebase were not updated, leading to `TypeError: missing 1 required positional argument`.
5.  **External Dependency Failure:** The xAI API began returning `429 Too Many Requests` (insufficient credits), which threatened to block the pipeline if not handled gracefully.

## Actions Taken

### 1. Implemented Sparse Data Fallback (The "Silver Standard")
We recognized that while "Inferred Sales" (Gold Standard) are best, we cannot afford to discard inventory when they are missing.
-   **Modified `keepa_deals/stable_calculations.py`:** Updated `infer_sale_events` to look for rank drops over longer windows (up to 30 days lookahead) to catch sales in sparse data trails.
-   **Modified `keepa_deals/new_analytics.py`:** Implemented a fallback for `get_1yr_avg_sale_price`. If inferred sales are insufficient, the system now defaults to Keepa's pre-calculated `stats.avg365` (Used Price) or `stats.avg90`.
-   **Result:** Deals that would have been rejected for "Missing Data" are now accepted using the fallback price.

### 2. Implemented Trust Rating System
To maintain user trust while using estimated data:
-   **Modified `keepa_deals/processing.py`:** When a fallback price is used, the system flags the deal with `price_source: 'Keepa Stats Fallback'`.
-   **UI Impact:** The `List at` price is appended with `(Est.)` (e.g., "$45.00 (Est.)"), and the `Profit Confidence` score is automatically capped/downgraded to "Low (Est.)". This ensures the user knows the data is an estimate.

### 3. Fixed Pipeline Logic Order
-   **Modified `keepa_deals/processing.py`:** Moved the critical validation checks for `List at` and `1yr. Avg.` to the very end of the `_process_single_deal` function, ensuring they only run *after* all attempts to calculate these values (including fallbacks) have completed.

### 4. Fixed Infrastructure Crashes
-   **Modified `keepa_deals/stable_deals.py`:** Updated the `last_update` function signature to `def last_update(deal_object, logger_param=None, ...)` to make the logger optional, restoring compatibility with legacy code.
-   **XAI Handling:** Confirmed that the system fails open (logs the error but proceeds) when xAI returns 429, preventing a hard stop on billing issues.

## Outcome
**SUCCESS.**
-   The diagnostic tool `Diagnostics/investigate_ingestion_failure.py` confirmed that ASIN `1454919108` (previously rejected) is now **ACCEPTED** with a valid profit calculation.
-   The "Stop Trigger" in the logs confirmed the Smart Ingestor is running, processing pages, and successfully catching up to the watermark.
-   The system is healthy and collecting deals again.

## Reference
-   **Diagnostic Tool:** `Diagnostics/investigate_ingestion_failure.py` (Use this to trace specific ASIN rejections).
-   **Key Concept:** "Sparse Data Fallback" allows processing low-velocity inventory by accepting Keepa's statistical averages when granular rank data is missing, but marks them as lower confidence.
