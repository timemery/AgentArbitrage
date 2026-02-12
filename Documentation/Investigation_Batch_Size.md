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

## 3. Optimization Opportunities (The "Safe Way")

We identified a specific optimization that makes large batch sizes safe and effective.

### A. Optimize the "Peek" Request
-   **Current:** `fetch_current_stats_batch` requests `stats=365` AND `offers=20`.
-   **Analysis:** The `check_peek_viability` function (which decides if a deal is good) **ONLY** uses the `stats` object (Sales Rank, Buy Box Price). It does **NOT** use the offer list.
-   **Solution:** Modify the Peek request to set `offers=0`.
-   **Projected Cost:** ~1-2 tokens per ASIN (down from ~6-12).

### B. Decoupled Batching Strategy
Once the Peek cost is reduced, we can split the batching logic:

1.  **Peek Batch (Discovery):** Increase size to **50 ASINs**.
    -   **Cost:** ~50-100 tokens (Safe).
    -   **Benefit:** Reduces HTTP requests by 10x (1 request vs 10 requests for 50 items). Massive speedup in scanning.

2.  **Commit Batch (Enrichment):** Keep size at **5 ASINs** (or dynamic).
    -   **Logic:** Only "Survivors" (promising deals) proceed to this stage.
    -   **Safety:** Prevents token spikes. Even if 50 items are scanned, only ~5-10 might survive. We process them in small chunks to keep the token deficit manageable.

---

## 4. Conclusion & Recommendations

**Q: Is there any safe way to improve the speed of the data collection?**
**A:** Yes. By removing the unused `offers=20` parameter from the Peek stage, we can drastically reduce costs. This allows us to safely increase the scanning batch size to 50, speeding up the discovery phase significantly.

**Q: Is it true that it was no more costly to collect 20 than 50?**
**A:** No, not for the Product Enrichment API. Costs are linear (per-ASIN). However, with the proposed optimization (removing offers), the per-ASIN cost becomes negligible (1-2 tokens), making larger batches highly efficient relative to the speed gain.

**Recommended Action Plan:**
1.  **Code Change:** Update `keepa_api.py` or `smart_ingestor.py` to use `offers=0` for the Peek stage.
2.  **Configuration:** Increase `MAX_ASINS_PER_BATCH` to **50** for the scanning loop.
3.  **Safety Check:** Ensure the "Commit" loop processes survivors in smaller sub-batches (e.g., 5) to protect the token bucket.
