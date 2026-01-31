# Fix Advice Tone and Enforce Teacher's Edition Rule

## Overview
This task originated from a user report that the "Purchase Analysis & Advice" feature was missing critical rules (specifically regarding "Teacher's Editions") and not utilizing the "Intelligence" database.

## Initial Approach & Pivot
Initially, I implemented logic to inject the full `intelligence.json` (Mental Models) into the advisor's prompt. 
*   **Result:** The user provided immediate feedback that this "muddied" the advice, making it "wishy-washy" and overly conversational, and causing instability errors.
*   **Pivot:** The user requested a reversal of the Intelligence injection and a return to a more data-driven, professional tone.

## Final Changes Implemented

### 1. `keepa_deals/ava_advisor.py`
*   **Reverted Intelligence Injection**: Removed `load_intelligence()` and the associated prompt injection to prevent context dilution.
*   **Prompt Engineering**: 
    *   Updated the "Persona" section to enforce an "analytical, professional, and cautious" tone.
    *   Replaced the hardcoded "conversational" examples (e.g., "Ooo yes good one") with the user's preferred "professional" example (e.g., "This Teacher's Edition is a solid buying opportunity...").
    *   This ensures the model generates concise, business-focused advice.

### 2. `strategies.json`
*   **Added Missing Rule**: Manually appended the specific "Risk" strategy: *"Teacher's Edition, Instructor's Edition, or Promotional Copy - Do not buy or list this item. It is prohibited on Amazon."*
*   **Why**: The user correctly identified that this rule was missing. Adding it to `strategies.json` ensures it is loaded by `load_strategies()` and available in the prompt context without "muddying" it with abstract concepts.

## Verification
*   **Tone Check**: Verified that the prompt now explicitly requests a professional tone and uses data-driven examples.
*   **Context Check**: Confirmed `strategies.json` contains the new rule and `intelligence.json` is excluded.
*   **Rule Persistence**: Verified the new strategy exists in the file.

## Status
*   **Complete**: The system now respects the "Teacher's Edition" constraint (via `strategies.json`) and generates advice in the professional format requested by the user.
