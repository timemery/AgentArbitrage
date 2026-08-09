# Task: Implement Hybrid Ingestion Strategy (Lightweight Updates)

**Objective:**
Break the current system ceiling of ~1,000 deals by reducing the API token cost for maintaining existing deals. This will allow the system to scale to 10,000+ deals on the standard Keepa plan.

**Context:**
Currently, the system fetches full product history (Cost: ~20 tokens) for *every* deal, even if it's just refreshing the price of an item we already know about. The math dictates that with a 72-hour retention policy and a 7,200 daily token budget, we can only maintain ~1,080 deals.

**The Solution:**
Implement a **Hybrid Ingestion Pipeline** where:
1.  **New Deals** get a "Heavy Fetch" (Full History, AI Analysis).
2.  **Existing Deals** get a "Light Fetch" (Current Stats Only).

---

## Technical Implementation Steps

### 1. Modify `keepa_deals/keepa_api.py`
Create a new function `fetch_current_stats_batch(api_key, asins_list)` optimized for low token usage.
*   **Parameters:** `stats=1`, `history=0` (or minimum required), `offers=20`.
*   **Goal:** Retrieve `current` Price, `salesRank`, and `buyBox` data.
*   **Verification:** Ensure this call consumes significantly fewer tokens (Target: ~1-2 tokens/ASIN) compared to the full history fetch (~20 tokens).

### 2. Refactor `keepa_deals/backfiller.py`
Modify the main processing loop in `backfill_deals`:
*   **Split the Batch:** Before fetching product data, check the database (`deals` table) to see which ASINs in the current chunk already exist.
*   **Branch A (New ASINs):**
    *   Call: `fetch_product_batch` (Existing "Heavy" function).
    *   Process: Run `_process_single_deal` (Full Logic: Inferred Sales, AI Analysis).
    *   Action: Insert new record.
*   **Branch B (Existing ASINs):**
    *   Call: `fetch_current_stats_batch` (New "Light" function).
    *   Process: **SKIP** `_process_single_deal`.
    *   Action: Perform a lightweight SQL update.
        *   **UPDATE:** `Price Now`, `Sales Rank`, `last_seen_utc`, `last_price_change`, `Offers`, `Drops`.
        *   **PRESERVE:** `List at`, `1yr Avg`, `Detailed_Seasonality`, `Profit Confidence`.
        *   **Recalculate:** Update `Margin` and `Profit` based on the *new* Price Now and the *preserved* List At.

### 3. Refactor `keepa_deals/simple_task.py` (The Refiller)
Apply the same "Split Batch" logic to the `update_recent_deals` task.
*   This task runs frequently (every minute) and is the primary consumer of tokens. Optimizing this is critical.
*   Ensure that `last_seen_utc` is updated for existing deals so the Janitor doesn't delete them.

### 4. Database Optimization
*   Ensure the `UPDATE` query for existing deals is efficient.
*   Avoid triggering unnecessary "New Deal" notifications for simple price updates (unless the price dropped significantly).

---

## Acceptance Criteria

1.  **Token Usage:**
    *   Verify that processing a batch of 10 *existing* deals consumes significantly fewer tokens than a batch of 10 *new* deals.
2.  **Data Integrity:**
    *   Verify that updating an existing deal **does not wipe out** its calculated fields (List At, Seasonality).
    *   Verify that `last_seen_utc` is updated, preventing Janitor deletion.
3.  **Scale:**
    *   The system should be able to "refresh" the entire database much faster, allowing the deal count to grow beyond 1,000.

## Warnings
*   **Do not break the AI Logic:** The `_process_single_deal` function relies on history arrays (`csv`). Do not attempt to run this function on the "Lightweight" data objects, as it will crash or produce garbage. You must write a separate, simpler update path for existing deals.
*   **Janitor Safety:** If `last_seen_utc` is not updated correctly during the light fetch, the Janitor will wipe out the database after 3 days. Test this carefully.
