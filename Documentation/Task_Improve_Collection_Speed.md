# Task: Improve Data Collection Speed (Decoupled Batching)

**Objective:**
Optimize the Keepa ingestion pipeline to significantly increase scanning throughput (speed) without compromising data accuracy or token safety.

**Reference:**
-   `Documentation/Investigation_Batch_Size.md` (Detailed analysis of costs and safety)

**Context:**
The current `Smart Ingestor` uses a fixed batch size of 5 for both "Peek" (Discovery) and "Commit" (Ingestion) stages. This is safe but slow due to HTTP latency.
The investigation confirmed that the "Peek" stage (`fetch_current_stats_batch`) fetches unnecessary `offers` data, inflating costs (e.g., 6 tokens/ASIN instead of ~1).
By removing `offers` from the Peek stage, we can safely increase the batch size to **50**, speeding up the discovery of new deals by ~10x.

**Constraints (CRITICAL):**
1.  **Stage 1 (Peek):** Remove `offers` (set to 0). This is safe because we only filter by stats here.
2.  **Stage 3 (Lightweight Update):** **DO NOT** remove `offers`. We MUST retain `offers=20` to calculate accurate shipping costs and track seller IDs.
3.  **Stage 2 (Commit):** No change needed (already fetches full data).

---

## Implementation Plan

### 1. Update `keepa_deals/keepa_api.py`
-   Modify `fetch_current_stats_batch` to accept an optional `offers` parameter.
-   **Default:** `offers=20` (to maintain backward compatibility and safety for existing calls).
-   **Logic:** Pass this parameter into the API URL string.

### 2. Update `keepa_deals/smart_ingestor.py`
-   **Stage 1 (Peek):**
    -   Update the call to `fetch_current_stats_batch` to use `offers=0`.
    -   Update the loop logic to process **chunks of 50** (instead of 5) for this specific stage.
    -   *Note:* Ensure the `check_peek_viability` function still receives the `stats` object correctly.
-   **Stage 2 (Commit):**
    -   **Important:** The survivors from Stage 1 (Peek) must be processed in **smaller sub-batches** (e.g., 5) to prevent "Deficit Shock" (consuming 1000+ tokens at once).
    -   *Logic:* Iterate through the `new_candidates` list in chunks of 5 and call `fetch_product_batch`.
-   **Stage 3 (Lightweight Update):**
    -   Update the loop to process chunks of **50** (since we are only fetching stats + offers, not full history).
    -   *Constraint:* Ensure the call to `fetch_current_stats_batch` uses `offers=20` (explicitly or via default).

### 3. Verification Steps
-   **Unit Test:** Create a script `Diagnostics/verify_peek_optimization.py` that calls `fetch_current_stats_batch` with `offers=0` for 5 ASINs and confirms `tokensConsumed` is low (~1-2 per ASIN).
-   **Integration Test:** Run the `smart_ingestor` manually and verify:
    -   Scanning logs show batches of 50.
    -   "Peek Rejected" logs appear (proving the filter works).
    -   "Ingested" deals (Commit) still have valid Shipping and Seller data in the database (proving we didn't lose data).
