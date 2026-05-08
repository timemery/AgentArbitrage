# Dev Log: Agent's Choice Filter 504 Timeout Investigation
**Date:** 2026-05-06

## Task Overview
The goal of this task was to investigate and fix a persistent issue where applying the "Agent's Choice" (Prime Picks) filter on the frontend caused the web application to hang for approximately 5 minutes, ultimately resulting in a `504 Gateway Timeout` error.

## Challenges Faced
- The xAI API key and network connection were verified to be healthy and fast using a standalone script (`Diagnostics/test_xai_connection.py`), returning results in under 3 seconds.
- The hanging issue was strictly isolated to the web application (Flask/WSGI) context when calling the xAI API.
- The frontend UI automatically closed the filter panel upon clicking "Apply Filters", hiding the "Loading..." indicator and leaving the user without feedback during the 5-minute hang.
- The `query_xai_api` function in `keepa_deals/ava_advisor.py` was utilizing `httpx` to make synchronous network calls within the Flask app.

## Actions Taken
- **UI Loading State Visibility:** Modified `templates/dashboard.html` to prevent the filter panel from auto-closing when the "Apply Filters" button is clicked. This allowed the user to see the updated "Loading..." text on the button.
- **Fallback Logic Patch:** Updated `wsgi_handler.py` to ensure that if the AI evaluation (Pass 2 Mastermind) returns an empty array `[]` (instead of just returning an explicit error), the system gracefully falls back to the top 10 Smart Floor candidates.
- **Model Correction:** Verified and enforced the use of the correct AI model (`grok-4-fast-reasoning`) across `wsgi_handler.py` and `ava_advisor.py`, resolving an earlier hallucination issue with `grok-beta`.
- **HTTP Client Swap:** Replaced `httpx.Client` with the standard `requests` library inside the `query_xai_api` function (`keepa_deals/ava_advisor.py`). `httpx` was suspected of causing indefinite hangs in the WSGI environment. The new implementation included robust retry logic and timeout settings matching the original code.

## Outcome
**Task Status:** Unsuccessful.

While the Mentor chat feature (which also uses `keepa_deals/ava_advisor.py`) is working correctly, the "Agent's Choice" filter still fails and throws an error. The core issue of the filter failing to return results has not been fully resolved despite the UI changes, fallback additions, and HTTP client swap. The next agent will need to investigate the remaining issues from a fresh perspective.
