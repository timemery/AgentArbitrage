# Dev Log: Investigate Dwindling Deals

**Date:** 2026-01-21
**Author:** Jules (AI Agent)
**Status:** Successful
**Related Files:** `keepa_deals/stable_calculations.py`, `Documentation/INFERRED_PRICE_LOGIC.md`, `keepa_query.json`

## Task Overview
The goal was to investigate a critical issue where the number of deals in the dashboard was "dwindling" to zero, with new deals being rejected at a rate of ~95% due to "Missing 'List at'". The user explicitly suspected a "fallback" mechanism might be to blame and advised against using fallback data.

## Investigation & Findings

1.  **Reproduction:**
    -   I created a script (`investigate_rejection.py`) to process live Keepa data.
    -   I successfully reproduced the rejection on ASIN `0878873414` (Sales Rank ~4.9M).
    -   **Finding:** The system calculated a "List at" price of **$414.05**. The AI Reasonableness Check (`grok-4-fast-reasoning`) correctly flagged this as unreasonable, causing the deal to be rejected.

2.  **The "Zombie Listing" Mechanism:**
    -   I identified a **fallback logic** in `keepa_deals/stable_calculations.py` that triggers when no inferred sales are found but `monthlySold > 20`.
    -   **The Flaw:** `monthlySold` measures **Total** velocity (New + Used). If a book sells well as New ($50) but has a stale "Used" listing at $400, the fallback erroneously grabs the $400 Used price (`avg90`) as the "Peak Price".
    -   **The Impact:** The system "fills in the blank" with $400. The AI sees "$400 for a book" and rejects it. This consumes tokens and processing time only to reject the deal.

3.  **Source of Dwindling:**
    -   The `keepa_query.json` allowed Sales Ranks up to **5,000,000**.
    -   This flooded the system with low-velocity items where "Zombie" listings are common.
    -   The high rejection rate (95%) meant the Backfiller (limited to 5 tokens/min) could not replenish deals fast enough to keep up with the Janitor (which deletes deals > 72h old).

## Actions Taken

1.  **Documentation Update (Critical Warning):**
    -   Updated `Documentation/INFERRED_PRICE_LOGIC.md` with a "Critical Warning" about the dangers of fallback data.
    -   Updated `Documentation/Data_Logic.md` and `AGENTS.md` to reinforce this principle.

2.  **Next Steps Definition:**
    -   Created `NEXT_TASK_BRIEF.md` detailing exactly how to fix the code:
        1.  **Remove** the dangerous fallback in `stable_calculations.py`.
        2.  **Tighten** the `keepa_query.json` to cap Sales Rank at 1,000,000.

## Outcome
The investigation was **Successful**. The root cause (Bad Fallback + Loose Query) was identified and documented. No code changes were made to the logic, preserving the "fresh perspective" for the next agent as requested.
