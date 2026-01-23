# Optimize AI Price Validation to Reduce False Rejections
**Date:** 2026-01-23
**Status:** SUCCESS

## Overview
Addressed a high rejection rate (~24%) caused by "Missing 'List at'" errors. Diagnosis revealed that while some rejections were valid "Zombie Prices" (e.g., $1500 workbooks), others were strict rejections of moderately priced books due to lack of historical context.

## Challenges
*   **Token Limits:** The Keepa API token limit was hit during diagnosis, requiring an offline analysis of `xai_cache.json` to identify rejection patterns.
*   **Data Context:** The AI was rejecting prices like $33 for a book because it didn't know if that was a normal price or a spike.

## Resolution
1.  **Extended History:** Updated `simple_task.py` to fetch 3 years (1095 days) of product history instead of 1 year.
2.  **Trend Analysis:** Implemented `calculate_long_term_trend` (using linear regression) and `calculate_3yr_avg` in `stable_calculations.py`.
3.  **Context Injection:** Updated `_query_xai_for_reasonableness` to include the 3-year trend and average price in the prompt sent to Grok.
4.  **Prompt Tuning:** Modified the AI prompt to explicitly define its role as an "Arbitrage Advisor" and instructed it that "slight premiums above the average are expected in peak season" to reduce strictness.
5.  **Logging:** Enhanced logging to capture the exact context of AI rejections for future debugging.

## Technical Details
*   **Linear Regression:** Used `scipy.stats.linregress` to calculate the slope of price over time.
*   **Prompt Engineering:**
    *   Injected context: "3-Year Trend: UP/DOWN/FLAT (+X%)" and "3-Year Average Price: $Y".
    *   Added Persona: "You are an expert Arbitrage Advisor. Slight premiums above the average are expected in peak season."
