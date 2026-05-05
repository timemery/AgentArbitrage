# Dev Log: Agent's Choice Filter Bug Fixes

**Date:** 2026-05-05

## Overview
The "Agent's Choice" filter (Pass 2 pipeline) was consistently returning 0 deals or seemingly not updating the UI table. A previous agent attempted to solve this by modifying the AI model name, resulting in API 429 (Resource Exhausted) errors that completely blocked the system. The task was to review `wsgi_handler.py`, fix the underlying Smart Floor SQL bugs, restore the proper model name, and add an auto-closing CSS animation to the filter panel per the user's request. 

## Challenges & Solutions

1. **SQL Casting Bug (Smart Floor):** 
    - *Challenge:* The Smart Floor (Pass 1) evaluates mathematical constraints (e.g., Profit >= 10, ROI >= 15%, Deal_Trust >= 40). However, the SQLite database stores these fields as strings containing currency and percentage symbols (e.g., "$25.00", "80%"). Standard SQL queries failed to compare these against integers properly.
    - *Solution:* Reused the previously defined string sanitization logic (`CAST(REPLACE(REPLACE(\"Profit\", '$', ''), ',', '') AS REAL)`) to correctly cast the fields during evaluation. Similarly, `Deal_Trust` had to be cast by removing the `%` symbol.

2. **AI Failure (0 Deals Displayed):** 
    - *Challenge:* The `query_xai_api` logic was failing entirely. When it hit 429 rate limits (caused by either a hallucinated model or an exhausted credit balance), it didn't throw a traditional Exception. Instead, it returned a JSON dictionary (e.g., `{"error": "..."}`). The codebase failed to handle this, leaving `selected_asins` empty and resulting in a filter match of `[d for d in top_10 if str(d.get("ASIN")) in selected_asins]`, which predictably equals 0. 
    - *Solution:* Implemented an explicit `ai_failed` flag. If the API returns an error or parsing fails, the system logs the failure and intelligently "falls back" to displaying the raw `top_10` mathematically vetted Pass 1 candidates. This prevents a complete UI breakdown when the AI service is unavailable.

3. **Hallucinated xAI Model:** 
    - *Challenge:* The previous agent changed the AI model in the payload to `grok-4-1-fast-non-reasoning`, which was not the standard model.
    - *Solution:* Restored the payload to use `grok-beta` as the standard, robust model per the user's instructions and system norms.

4. **UI Panel Animation:**
    - *Challenge:* The user requested the filter panel automatically close with an animation after clicking "Apply Filters", but the existing implementation used an immediate `display: none` which cannot be CSS animated smoothly.
    - *Solution:* Implemented an `opacity`, `transform`, and `visibility` transition in `global.css` tied to a new `.show` class. In the JavaScript `toggleFilterPanel` function, a `setTimeout` was introduced to allow the CSS transition to play out for 300ms before finally setting `display: none`. A forced reflow (`void filterDropdown.offsetWidth`) was also added to ensure the open animation functioned properly when changing from `display: none` to `display: flex`. 

## Status
**Success.** The SQL filters now properly parse strings, the AI integration gracefully degrades to Pass 1 results rather than returning 0 deals on an API failure, the model name is corrected, and the UI filter panel closes with a smooth animation.
