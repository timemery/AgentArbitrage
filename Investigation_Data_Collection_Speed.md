# Investigation Report: Data Collection Speed & Scalability

**Date:** February 2026
**Topic:** Theoretical Investigation into Data Collection Limits
**Status:** Complete

---

## 1. Executive Summary

The current inability to sustain more than ~1,000 deals is **not a software bug or a process conflict**, but a mathematical certainty imposed by the current "Heavy Fetch" architecture and the standard Keepa token limit.

**The Findings:**
*   **Current Ceiling:** The system is mathematically capped at **~1,080 deals**. Any deals added beyond this number will inevitably be deleted by the Janitor before they can be refreshed.
*   **Root Cause:** The system currently pays the "New Deal Price" (20 tokens) to refresh *every* deal, even if it has been in the database for weeks.
*   **The Solution:** Implementing a **"Hybrid Ingestion Strategy"** (Lightweight Updates for existing deals) will raise the theoretical ceiling from ~1,000 to **~10,000 - 20,000 deals** without upgrading the Keepa plan.

---

## 2. The "Equilibrium Trap" (The Math)

To understand why the system stalls at 1,000 deals, we must look at the Token Budget as a daily allowance.

### A. The Budget
*   **Plan:** Standard Keepa Plan (5 tokens/minute).
*   **Daily Budget:** $5 \text{ tokens/min} \times 60 \text{ min} \times 24 \text{ hours} = \mathbf{7,200 \text{ tokens/day}}$.

### B. The Cost (Current Architecture)
Currently, both the Backfiller and the Refiller (Simple Task) fetch **Full Product History** (`history=1, days=365`) for every ASIN they process.
*   **Cost per Fetch:** ~20 Tokens.
*   **Max Daily Capacity:** $7,200 / 20 = \mathbf{360 \text{ fetches/day}}$.

### C. The Churn (The Janitor)
The Janitor deletes any deal that hasn't been updated in 72 hours (3 days). To maintain a pool of $N$ deals, the system must refresh all $N$ deals within that 3-day window.
*   **Required Refresh Rate:** $N / 3$ deals per day.

### D. The Ceiling
The system reaches equilibrium (stalls) when the *Required Refresh Rate* equals the *Max Daily Capacity*.

$$
\frac{N}{3} = 360 \implies N = 1,080
$$

**Conclusion:** It is mathematically impossible to maintain a database larger than **1,080 deals** with the current architecture. Adding more backfillers, pausing tasks, or optimizing loops will not solve this because the hard limit is the token budget itself.

---

## 3. The Solution: Hybrid Ingestion Strategy

To break the 1,000-deal ceiling, we must drastically reduce the cost of *maintaining* a deal. We can do this by distinguishing between "Discovery" and "Maintenance".

### The Concept
*   **Discovery (New Deals):** Requires full history to calculate "List At" price, Inferred Sales, and Seasonality.
    *   **Cost:** 20 Tokens ("Heavy").
*   **Maintenance (Existing Deals):** Only needs the current Price and Sales Rank to verify the deal is still live. The deep history analysis (Seasonality, List At) does not change daily.
    *   **Cost:** 1 Token ("Light").

### The New Math (Projected)
If we implement "Lightweight Updates" (fetching only the `stats` object) for existing deals:

*   **Cost per Refresh:** 1 Token.
*   **Target:** 10,000 Deals.
*   **Maintenance Cost:** $10,000 \text{ deals} / 3 \text{ days} = 3,333 \text{ refreshes/day}$.
    *   **Token Usage:** 3,333 Tokens.
*   **Budget Remaining:** $7,200 - 3,333 = 3,867 \text{ tokens}$.
*   **New Deal Capacity:** $3,867 / 20 = \mathbf{193 \text{ new deals/day}}$.

**Result:** A sustainable ecosystem of **10,000 deals** that refreshes itself completely every 3 days, while still having enough budget to find ~200 new deals every single day.

If we push to **20,000 deals**:
*   **Maintenance Cost:** $6,666 \text{ tokens/day}$.
*   **Budget Remaining:** $534 \text{ tokens}$.
*   **New Deal Capacity:** $26 \text{ new deals/day}$.
*   **Result:** Possible, but leaves little room for growth. **10,000-15,000 is the sweet spot.**

---

## 4. Technical Implementation Path

Moving to this architecture requires a significant refactor of the ingestion pipeline.

### Step 1: The "Lightweight" Fetcher
Modify `keepa_api.py` to support a "Stats Only" mode.
*   **API Call:** `domain=1&asin=...&stats=1&history=0&offers=20`
*   **Return:** A lightweight object containing only current `stats` (Price, Rank, Buy Box) without the massive `csv` history arrays.

### Step 2: The Forked Pipeline
In both `backfiller.py` and `simple_task.py`, split the ASINs into two queues before processing:

1.  **Queue A (New ASINs):** ASINs not found in the DB.
    *   Action: Perform **Heavy Fetch** (20 tokens).
    *   Process: Run full `_process_single_deal` logic (Inferred Sales, AI Analysis, etc.).
    *   Upsert: Insert full record.

2.  **Queue B (Existing ASINs):** ASINs already in the DB.
    *   Action: Perform **Light Fetch** (1 token).
    *   Process: **Bypass** `_process_single_deal`.
    *   Action: Run a new function `_update_existing_deal_lightweight(deal_data)`.
        *   Updates only: `Price Now`, `Sales Rank`, `last_seen_utc`.
        *   Preserves: `List At`, `Seasonality`, `Inferred Sales`, `1yr Avg`.
    *   Upsert: fast SQL UPDATE.

### Step 3: periodic "Deep Clean"
Since "List At" and "Seasonality" can change over months, we can implement a logic where an Existing Deal gets a "Heavy Fetch" if its `last_full_scan` date was > 30 days ago. This keeps the deep metrics reasonably fresh without bankrupting the token budget.

---

## 5. Alternatives Considered

*   **Server-Side Optimization (Second Database):**
    *   **Verdict:** Ineffective. The bottleneck is external (Keepa API), not internal (SQLite/Server).
*   **Keepa Plan Upgrade (20 tokens/min):**
    *   **Verdict:** Effective but costly. Would raise the "Heavy Fetch" ceiling to ~4,300 deals. To reach 20k deals with the current inefficient code, you would need a ~100 token/min plan (Enterprise tier).
*   **Pausing the Backfiller:**
    *   **Verdict:** Counter-productive. The system is already in a deficit. Pausing just delays the inevitable deletion of stale deals.

## 6. Conclusion & Recommendation

The "Lightweight Update" strategy is the only viable path to scaling the deal pool without significantly increasing monthly costs. While it requires code refactoring to decouple "Maintenance" from "Discovery," the ROI is a **10x-20x increase in system capacity**.

**Recommendation:** Proceed with the refactoring of `backfiller.py` and `simple_task.py` to implement the Hybrid Ingestion Strategy.
