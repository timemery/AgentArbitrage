# Fix Strategies and Intelligence Not Being Applied in Advice

## Overview
This task addressed a critical issue where "Strategies" and "Intelligence" (Mental Models) were not being correctly applied during the "Purchase Analysis & Advice" generation. Specifically, a rule about "Teacher's Editions" being prohibited was missing from the analysis, and the system was failing to utilize the conceptual knowledge stored in `intelligence.json`.

## Changes Implemented

### 1. `keepa_deals/ava_advisor.py`
*   **Added `INTELLIGENCE_FILE`**: Defined the path to `intelligence.json`.
*   **Added `load_intelligence()`**: Created a function to read and format conceptual ideas from `intelligence.json`.
*   **Updated `generate_ava_advice()`**: Modified the prompt generation logic to call `load_intelligence()` and inject the "Mental Models" into the system prompt sent to xAI. This ensures the advisor considers high-level concepts (e.g., "Seasonality", "Risk Management") alongside specific strategies.

### 2. `strategies.json`
*   **Added Missing Rule**: Manually appended a specific "Risk" strategy regarding "Teacher's Editions, Instructor's Editions, and Promotional Copies" being prohibited on Amazon. This directly addresses the user's reported missing rule.

## Verification
*   **Prompt Verification**: Created a test script `verify_advice.py` that mocked the `query_xai_api` function.
*   **Success Criteria**: The script confirmed that both the new "Teacher's Edition" strategy AND the content from `intelligence.json` were present in the prompt constructed by `generate_ava_advice`.

## Challenges
*   **Missing Data**: The specific rule about "Teacher's Editions" was not found in the existing `strategies.json` or `intelligence.json` files, despite the user's belief it was added via the Guided Learning tool. This required manual intervention to add the rule to ensure the system behaved as expected.
*   **Code Review Confusion**: Initial code review flagged a potential JSON syntax error due to how the change was presented (diff vs script execution), but verification confirmed the JSON structure remains valid.

## Status
*   **Complete**: The advisor now has access to the full knowledge base (Strategies + Intelligence), and the specific missing rule has been restored.
