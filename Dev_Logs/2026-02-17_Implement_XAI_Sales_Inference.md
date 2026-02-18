# Dev Log: Implement XAI Inferred Sales Rescue

**Date:** 2026-02-17
**Author:** Jules (AI Agent)
**Task:** Investigate and implement using xAI to find the inferred sale price to address high deal rejection rates.

## 1. Task Overview
The system was experiencing a rejection rate of over 95%, primarily because the rule-based algorithm in `stable_calculations.py` was too strict. It frequently missed "Hidden Sales" (sales that occur without the Offer Count dropping because the seller had multiple units in stock) or sales with complex rank patterns. The goal was to leverage xAI (Grok) to analyze the historical data (Rank, Price, Offer Count) and infer sales where the algorithm failed, acting as a "Rescue Mechanism."

## 2. Challenges Faced

1.  **High Rejection Rate:** The primary driver was the inability of the strict algorithm to detect sales for high-volume items (Stock Depth > 1) or items with sparse data.
2.  **Context Window Limits:** Sending 365 days of minute-by-minute Keepa history to an LLM would exceed token limits.
3.  **Data Structure Complexity:** Keepa stores data in uneven, event-based arrays (Timestamp, Value) which are difficult to align for time-series analysis.
4.  **Seasonality:** A short history window (e.g., 90 days) was insufficient to determine if a price was a "Peak" or "Trough," which is critical for Arbitrage decision-making. The user specifically requested a full 365-day view.
5.  **State Management:** The XAI token tracking file (`xai_token_state.json`) was inadvertently being tracked by git, causing commit friction.

## 3. Actions Taken

### A. Created `keepa_deals/xai_sales_inference.py`
This new module encapsulates all logic related to the XAI rescue mechanism.

*   **`format_history_for_xai(product, days=365)`**:
    *   **365-Day Window:** Captures a full year of history to provide seasonality context.
    *   **Data Alignment:** Uses `pandas.merge_asof` to synchronize the disjointed Rank, Price, and Offer Count arrays into a cohesive time-series table.
    *   **Smart Compression:** Implements a dynamic "skip factor" if the resulting table exceeds 400 lines. This downsamples the data to fit within the LLM's context window while preserving the overall trend and the critical start/end states.
    *   **Initial State Capture:** Explicitly handles the edge case where no data points exist *within* the window by carrying forward the last known value from before the window starts.

*   **`query_xai_sales_inference(history_text, product)`**:
    *   Constructs a prompt explaining the logic of "Hidden Sales" (Rank drop without Offer drop) and "Standard Sales" (Rank drop + Offer drop).
    *   Calls the xAI API (Grok) to analyze the markdown table.
    *   Parses the JSON response to extract confirmed sale events.

*   **`infer_sales_with_xai(product)`**:
    *   A safety wrapper that checks eligibility (e.g., skips "Dead Inventory" with Rank > 2,000,000 to save tokens).

### B. Updated `keepa_deals/stable_calculations.py`
Integrated the rescue mechanism into the `infer_sale_events` function.

*   **Logic Fork:** The system now attempts the XAI rescue in two specific failure scenarios:
    1.  **No Offer Drops Found:** Previously returned 0 sales immediately. Now calls XAI to check for "Hidden Sales."
    2.  **Drops Found but 0 Sales Confirmed:** If the algorithm filtered out all potential sales (e.g., due to weak rank correlation), it calls XAI to re-evaluate the data with "human-like" reasoning.

### C. Testing & Cleanup
*   Added `tests/test_xai_sales_inference.py` to verify the formatting logic, compression, and API response parsing.
*   Removed `xai_token_state.json` from the repository to prevent local runtime state from polluting the codebase.

## 4. Outcome
The task was **Successful**.

The new pipeline allows the system to "rescue" potentially profitable deals that were previously discarded. By providing 365 days of history, the AI can now discern seasonal peaks and identify sales patterns that the strict algorithmic approach missed. The implementation is robust, with error handling wrapping all external API calls, ensuring that the core ingestion process remains stable even if XAI is unavailable.

## 5. Technical Reference
*   **Key Files:** `keepa_deals/xai_sales_inference.py`, `keepa_deals/stable_calculations.py`
*   **Prompt Logic:** The prompt explicitly instructs the AI to look for *Rank Improvements* (drops) even when *Offer Counts* are stable, which is the definition of a "Hidden Sale."
*   **Safety Valve:** The mechanism automatically skips items with current Rank > 2M to preserve API tokens.
