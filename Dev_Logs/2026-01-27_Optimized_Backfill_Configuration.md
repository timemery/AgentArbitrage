# Optimized Backfill Configuration & Concurrency

## 1. Goal: Increasing Deal Volume
The primary objective was to increase the volume of deals in the database, targeting ~10,000+ active deals. Previous strict filters limited the pool to <2,000.

### The "TONS o Deals" Configuration
We updated `keepa_query.json` with the following parameters:
-   **Sales Rank:** 10,000 - 10,000,000
-   **Current Price:** $20 - $451
-   **Drop Percent:** > 10%
-   **Drop Value:** > $0 (Fixed `deltaRange` to allow drops > $100)
-   **Date Range:** 4 (All History)

### The "Ancient Data" Risk
Using `dateRange: 4` (All History) previously caused the ingestion of invalid deals from 2015.
-   **Fix:** We enforced `sortType: 4` (Last Update) in the API call.
-   **Verification:** `Diagnostics/test_keepa_query.py` was updated to decode Keepa timestamps.
-   **Result:** Confirmed that the API returns deals updated **today** (2026-01-27), ensuring data freshness despite the wide date window.

## 2. The Equilibrium Problem
We identified a mathematical ceiling for the database size based on the Keepa Plan (5 tokens/min).
-   **Income:** 7,200 tokens/day.
-   **Cost:** ~20 tokens to refresh a deal (Full History).
-   **Capacity:** 360 refreshes/day.
-   **Janitor:** Deletes deals after 3 days.
-   **Max Database Size:** ~1,100 deals (360 * 3).

### Solution: Concurrent Refiller & Lightweight Updates
To break this ceiling, we made two architectural changes:

1.  **Concurrent Execution:**
    -   **Change:** `simple_task.py` (Refiller) no longer checks the `backfill_deals_lock`.
    -   **Benefit:** The Refiller can now run *while* the Backfiller is churning through history. This ensures that fresh deals (Page 0) are ingested immediately.
    -   **Safety:** Both tasks rely on `TokenManager`. If tokens run out, they both block (sleep) until the bucket refills. There is a risk of the Backfiller "starving" the Refiller, but the Refiller's blocking wait ensures it eventually gets served.

2.  **Optimized Backfiller (Phase 1):**
    -   **Change:** `backfiller.py` now separates `New` vs `Existing` ASINs in each batch.
    -   **Future Work:** Currently, both types trigger a "Heavy" fetch (20 tokens) because `stable_products.py` requires full history arrays to function.
    -   **Roadmap:** To achieve the 24,000 deal target, we must refactor `stable_products.py` to accept "Lightweight" updates (1 token `stats` fetch) for existing deals. This will increase maintenance capacity from 360/day to ~7,000/day.

## 3. Diagnostic Tools
-   **`Diagnostics/test_keepa_query.py`:** Now validates timestamp freshness (human-readable dates).
-   **`Diagnostics/test_keepa_query_params.py`:** Benchmarks different query configurations.
-   **`Diagnostics/calculate_backfill_time.py`:** Simulates backfill duration with different "Maintenance Efficiency" ratios.
