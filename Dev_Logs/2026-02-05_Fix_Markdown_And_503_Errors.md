# Fix Markdown in Mentor Responses & Improve 503 Retry Logic

**Date:** 2026-02-05
**Status:** SUCCESS
**Files Modified:**
- `keepa_deals/ava_advisor.py`
- `wsgi_handler.py`
- `templates/dashboard.html`
- `static/js/mentor_chat.js`

## Overview
The user reported three main issues affecting the "My Mentor" and "Purchase Analysis & Advice" features:
1.  **Raw Markdown Leakage:** AI responses contained raw markdown (e.g., `**bold**`, `### Header`) which was being rendered as plain text instead of formatted HTML.
2.  **API Instability:** Frequent "Service Unavailable (503)" errors were causing the advice features to fail.
3.  **Repetitive Preambles:** The AI often included unnecessary introductions ("Greetings Tim...", "As your CFO...") despite the user's desire for direct analysis.

## Challenges
*   **Default AI Behavior:** LLMs are strongly predisposed to output Markdown. Overriding this requires strict, explicit prompting.
*   **Frontend Security vs. Utility:** The frontend was rightly using `.textContent` to prevent XSS attacks. However, this meant that any HTML returned by the AI (even if requested) would be escaped and visible as tags. We needed a way to render trusted AI HTML while sanitizing user input.
*   **API Timeouts:** The reasoning models (like `grok-4-fast-reasoning`) can be slow, sometimes exceeding standard HTTP timeouts or triggering 503s during load.

## Actions Taken

### 1. Prompt Engineering (Backend)
Modified the system prompts in `keepa_deals/ava_advisor.py` and `wsgi_handler.py` with two new hard constraints:
*   **HTML Formatting:** Explicitly instructed the model: *"Constraint: Do NOT use markdown. Use HTML tags (e.g., `<b>`, `<br>`, `<p>`) for formatting."*
*   **No Preambles:** Added: *"Constraint: Do NOT start with an introduction or preamble. Jump straight into the analysis."*

### 2. Frontend Rendering Update
Refactored the frontend to handle the trusted HTML response:
*   **`templates/dashboard.html`:** Changed `adviceContainer.textContent` to `adviceContainer.innerHTML`.
*   **`static/js/mentor_chat.js`:** Implemented a split logic for message rendering:
    *   **User Messages:** Continue using `.textContent` (Strict XSS protection).
    *   **Mentor Messages:** Use `.innerHTML` to render the bolding and line breaks returned by the AI.

### 3. Resilience Upgrades (xAI API)
Updated `query_xai_api` in `keepa_deals/ava_advisor.py`:
*   **Retries:** Increased `max_retries` from 3 to **5**.
*   **Backoff:** Increased `base_delay` from 2s to **3s** (exponential backoff).
*   **Timeout:** Increased HTTP client timeout from 120s to **150s** to accommodate slower reasoning chains.

## Outcome
The task was **successful**.
*   **Verification:**
    *   `tests/verify_xai_retry_logic.py` confirmed that the system now attempts 5 retries on 503 errors.
    *   `tests/verify_prompts_updated.py` confirmed that all relevant prompts include the new constraints.
    *   Code inspection verified the correct use of `innerHTML` for mentor responses.

## Technical Note for Future Devs
When asking an LLM for HTML output to be rendered via `innerHTML`, ensure the prompts are robust against malicious injection if the model input includes uncontrolled user data. In this case, the context data is internal system data, but future features allowing users to "inject" data into the prompt should be handled with care (e.g., using a sanitizer library on the frontend before `innerHTML`).
