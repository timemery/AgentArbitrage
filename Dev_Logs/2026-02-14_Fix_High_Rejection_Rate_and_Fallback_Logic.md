# Fix High Rejection Rate & Restore Fallback Pricing Logic

**Date:** 2026-02-14
**Status:** Success
**Modules Modified:** `keepa_deals/stable_calculations.py`, `keepa_deals/smart_ingestor.py`, `tests/test_stable_calculations.py`
**New Scripts:** `Diagnostics/analyze_rejection_reasons.py`, `tests/test_xai_fallback_context.py`

---

## 1. Task Overview
The user reported an excessively high rejection rate (97.30%) during deal ingestion. The primary cause (64% of rejections) was "Missing 'List at' price." The user suspected that the system was failing to infer sale prices for valid books due to sparse data and that valid fallback data (historical averages) was being ignored or rejected. The goal was to investigate, provide a deep-dive diagnostic, and fix the rejection rate by ensuring valid fallback prices are accepted.

## 2. Investigation & Root Cause
### A. The "Missing List at" Problem
The "List at" price is primarily derived from "Inferred Sales" (Keepa drops). For slow-moving items (e.g., long-tail books), recent drops are rare.
The system *had* a fallback mechanism ("Keepa Stats Fallback") to use `avg365` (1-year average price) when drops were missing. However, this fallback was failing for two reasons:
1.  **Code Defect:** The logic accessing `stats.avg90[2]` and `stats.avg365[2]` lacked `is not None` checks. If Keepa returned `None` for these specific indices (common for sparse items), the comparison `> 0` raised a `TypeError`, causing the function to crash/exit before setting a price.
2.  **AI Rejection:** Even when a fallback price was calculated, it was passed to the `_query_xai_for_reasonableness` function. Since fallback items often lack "Season" or "Trend" data (passed as `-` or `Insufficient data`), the AI model frequently rejected the price as "unreasonable" due to lack of supporting context. This resulted in a False Negative rejection of valid "Silver Standard" deals.

### B. Safety Audit ("Highest/Lowest" Concern)
The user was concerned that the system might be using "All Time High" or "All Time Low" metrics, which are dangerous for pricing.
*   **Audit Result:** Confirmed that the codebase **strictly** uses time-bounded averages (`avg90`, `avg365`) and current prices. No `min`, `max` (unbound), `lowest`, or `highest` fields from the Keepa API are used for pricing calculations.

## 3. Solution Implementation
### A. Hardening Fallback Logic (`stable_calculations.py`)
*   Added explicit `is not None` checks when reading Keepa stats arrays to prevent `TypeError` crashes.
*   Confirmed that the fallback logic correctly prioritizes the *highest* of the *averages* (max of `avg90` and `avg365` for Used conditions) to avoid underpricing seasonal items during off-peak periods.

### B. Skipping XAI for Fallbacks
*   Modified `analyze_sales_performance` to explicitly **skip** the XAI Reasonableness Check if the price source is `'Keepa Stats Fallback'`.
*   **Rationale:** The "Silver Standard" price is a historical average, which is inherently stable. The XAI model lacks the necessary context (specific recent sales) to judge it accurately, leading to false rejections. The Amazon Ceiling check (90% of New Price) remains active as the primary safety guard.

### C. Diagnostic Tools
*   Created `Diagnostics/analyze_rejection_reasons.py`: A script that fetches a batch of deals and explicitly reports whether "Inferred Sales" were found, or if a "Fallback Candidate" exists. This allows visibility into *why* a deal was rejected (e.g., "No drops AND no fallback").

## 4. Verification & Results
*   **Unit Tests:**
    *   `tests/test_xai_fallback_context.py`: Verified that XAI is *not* called when a fallback price is used.
    *   `tests/test_stable_calculations.py`: Updated to assert that items with stats but no sales now return a valid price (e.g., 40000) instead of -1.
*   **Live Diagnostics:**
    *   `Diagnostics/verify_fix_logic.py` confirmed the fix in the deployed environment: `SUCCESS: Fallback logic calculated 40000 and XAI check was skipped.`
*   **Throughput Analysis:**
    *   The user noted "slow" deal accumulation (5 deals in ~10 hours).
    *   Analysis of `Diagnostics/estimate_ingestion_time.py` and `check_pause_status.py` confirmed this is the mathematical limit of the user's Keepa plan (5 tokens/min).
    *   The system correctly enters "Recharge Mode" to prevent API bans. The "TokenRechargeError" seen in logs is a confirmation of successful safety throttling, not a bug.

## 5. Conclusion
The high rejection rate was due to a combination of fragile code (missing None checks) and over-aggressive AI filtering on fallback data. Both issues were resolved. The system now accepts "Silver Standard" deals safely, which should significantly improve deal volume over time, limited only by the Keepa API refill rate.
