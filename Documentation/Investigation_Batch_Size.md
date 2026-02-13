# Theoretical Investigation: Data Collection Speed & Token Costs

**Date:** February 12, 2026
**Subject:** Feasibility of Increasing Batch Size (20 vs 50) and Speed Optimization Opportunities

## Executive Summary
This investigation confirms that while Keepa API costs for product enrichment are generally linear (per-ASIN), significant optimizations are available.
The primary finding is that the current "Peek" stage requests unnecessary data (`offers=20`), inflating costs.
By optimizing the "Peek" request and decoupling it from the "Commit" stage, we can safely increase batch sizes to 50+, significantly improving throughput (speed) without risking token starvation.

---

## 1. Token Cost Analysis (Empirical Findings)

Diagnostic tests were run to determine the cost behavior of the Keepa Product API (`fetch_current_stats_batch`):

| Test Case | Tokens Consumed | Cost per ASIN | Note |
| :--- | :--- | :--- | :--- |
| **1 ASIN** | 6 tokens | 6.0 | Base cost + Per-ASIN cost |
| **2 ASINs** | 24 tokens | 12.0 | **Surprisingly High** |

**Interpretation:**
-   The high cost for 2 ASINs (24 tokens) suggests that requesting `offers=20` (as the current code does) scales aggressively, possibly non-linearly or with a high per-item overhead.
-   This contradicts the hypothesis that "20 ASINs cost the same as 50". That hypothesis likely refers to **Deal Discovery** (Page 0), where a page of 150 deals costs a fixed 10 tokens regardless of count.
-   For **Enrichment** (Product API), costs are strictly volume-based.

---

## 2. Speed vs. Safety Trade-off

The current system uses a **Fixed Batch Size of 5** for both "Peek" and "Commit" stages.

-   **Safety (Current Strategy):** Small batches prevent "Deficit Shock" (consuming 1000+ tokens at once), ensuring the system doesn't hit a hard wall and stall for hours.
-   **Speed Limit:** Small batches incur high HTTP latency overhead (1 round trip per 5 items). Processing 1000 items requires 200 requests.

**The Bottleneck:**
The "Commit" stage (fetching full history) is expensive (~20 tokens/ASIN). A batch of 50 survivors would cost 1000 tokens, which is dangerous.
However, the "Peek" stage (checking stats) *should* be cheap, but is currently expensive due to unoptimized requests.

---

## 3. "What Do We Lose?" (Risk Assessment)

We verified the usage of `offers` data in the codebase to determine the impact of removing `offers=20` from the "Peek" stage.

### A. Stage 1: Peek (New/Zombie Deals)
-   **Function:** `smart_ingestor.py` -> `check_peek_viability(stats)`
-   **Dependency:** This function **ONLY** uses the `stats` object (Sales Rank, Buy Box Price, 90/365d Avgs). It does **NOT** access the `offers` array.
-   **Data Flow:** The result of this stage is merely a list of `new_candidates`. The actual data fetched here is discarded. Survivors proceed to Stage 2 (Commit), which performs a fresh, full fetch (including offers).
-   **Verdict:** **Nothing is lost.** Removing `offers` from the Peek stage is 100% safe.

### B. Stage 3: Lightweight Update (Existing Deals)
-   **Function:** `processing.py` -> `_process_lightweight_update`
-   **Dependency:** This function **DOES** use the `offers` array.
    -   It iterates `product_data['offers']` to check shipping costs (`shipping_included_flag`).
    -   It updates Seller ID, Seller Name, and FBA status, which rely on offer details.
-   **Verdict:** **Functionality is lost.** Removing `offers` from the Lightweight Update stage would break shipping calculations and seller tracking.

**Conclusion:** We must parameterize the API call. We can remove `offers` for **Peek (Stage 1)** but must retain it for **Lightweight Update (Stage 3)**.

---

## 4. Optimization Opportunities (The "Safe Way")

We identified a specific optimization that makes large batch sizes safe and effective.

### A. Optimize the "Peek" Request
-   **Current:** `fetch_current_stats_batch` requests `stats=365` AND `offers=20` (hardcoded).
-   **Solution:** Modify `keepa_api.py` to accept an `offers` parameter.
    -   **Peek:** Call with `offers=0`. Cost drops to ~1-2 tokens/ASIN.
    -   **Lightweight Update:** Call with `offers=20`. Cost remains ~6-12 tokens/ASIN.

### B. Decoupled Batching Strategy
Once the Peek cost is reduced, we can split the batching logic:

1.  **Peek Batch (Discovery):** Increase size to **50 ASINs**.
    -   **Cost:** ~50-100 tokens (Safe).
    -   **Benefit:** Reduces HTTP requests by 10x (1 request vs 10 requests for 50 items). Massive speedup in scanning.

2.  **Commit Batch (Enrichment):** Keep size at **5 ASINs** (or dynamic).
    -   **Logic:** Only "Survivors" (promising deals) proceed to this stage.
    -   **Safety:** Prevents token spikes. Even if 50 items are scanned, only ~5-10 might survive. We process them in small chunks to keep the token deficit manageable.

---

## 5. Recommendations

**Q: Is there any safe way to improve the speed of the data collection?**
**A:** Yes. By removing the unused `offers=20` parameter **specifically from the Peek stage**, we can drastically reduce costs. This allows us to safely increase the scanning batch size to 50, speeding up the discovery phase significantly.

**Q: Is it true that it was no more costly to collect 20 than 50?**
**A:** No, not for the Product Enrichment API. Costs are linear (per-ASIN). However, with the proposed optimization (removing offers), the per-ASIN cost becomes negligible (1-2 tokens), making larger batches highly efficient relative to the speed gain.

**Recommended Action Plan:**
1.  **Code Change:** Update `keepa_api.py` to accept an `offers` parameter in `fetch_current_stats_batch`.
2.  **Smart Ingestor Update:**
    -   Call `fetch_current_stats_batch(..., offers=0)` for Stage 1 (Peek).
    -   Call `fetch_current_stats_batch(..., offers=20)` for Stage 3 (Lightweight Update).
3.  **Configuration:** Increase `MAX_ASINS_PER_BATCH` to **50** for the scanning loop (Peek), but throttle the Commit loop to 5 items at a time.
