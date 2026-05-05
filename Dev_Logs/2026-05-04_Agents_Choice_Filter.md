# Dev Log: Agent's Choice Filter Implementation

**Date:** 2026-05-04

## Overview
The goal of this task was to replace static "Optimal Filters" and deprecated "Exclude Conditions" in the UI with a new "Agent's Choice" (Prime Picks Only) filter. This filter utilizes a Two-Pass Pipeline:
1.  **Pass 1 (Smart Floor):** A mathematical strict floor implemented via SQL (`Profit >= 10`, `ROI >= 15%`, `Deal_Trust >= 40%`, `List_at <= 1500`), combined with a dynamic Time Decay scoring algorithm based on Sales Rank and Offer Count.
2.  **Pass 2 (xAI Mastermind):** A batch LLM evaluation of the top candidates (initially top 20, then reduced to 10) against business strategies stored in `strategies.json` to return a curated list of ASINs.

## Challenges & Solutions
1.  **Empty State Messaging:** Implemented custom JS logic to replace the generic "No deals found" message with a specific message when `agents_choice=true` returns zero deals.
2.  **AI Hallucination & Intelligence Conflict:** Initially, the AI was prompted with both `strategies.json` and `intelligence.json`. The abstract nature of `intelligence.json` caused the AI to reject deals arbitrarily. The prompt was updated to rely strictly on actionable `strategies.json` and softened to not demand "perfect" alignment with every strategy.
3.  **SQL Type Casting Failures:** The initial Smart Floor returned 0 deals because `Profit`, `All_in_Cost`, `Deal_Trust`, and `List_at` were improperly cast or evaluated.
    - *Solution:* Updated the SQL query to treat `Profit` and `All_in_Cost` as raw `REAL` floats matching the schema, stripped `%` from `Deal_Trust` before casting to `REAL`, and stripped `$` formatting from `List_at`.
4.  **UI Counter Synchronization:** The background `/api/deal-count` polling caused the UI to display the total number of deals passing Pass 1 (e.g., 299 deals) instead of the final AI-vetted count.
    - *Solution:* Added JS to abort the background polling interval if `agents_choice` is true, forcing the UI to rely strictly on the array length returned by the `api_deals` endpoint.
5.  **Agent Hallucination & Timeout Confusion:** Toward the end of the session, the agent hallucinated that a provided screenshot contained a "504 Gateway Timeout" error in red text. Based on this hallucination, the agent aggressively pursued optimizations (changing the model to `grok-4-1-fast-non-reasoning` and reducing batch size to 10) that were likely unnecessary or misaligned with the actual state of the application.

## Status
**Failed / Partially Complete.** The core logic for Pass 1 and Pass 2 is implemented in `wsgi_handler.py`, and the UI updates are present in `templates/dashboard.html`. However, the final few commits proposed and pushed by the agent were driven by hallucinations regarding a non-existent 504 error and UI state. The filter's current live behavior is unverified and likely requires debugging by a fresh agent.

---
