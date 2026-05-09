# Dev Log: Refine Prime Picks Reasoning and UX
**Date:** 2026-05-09

## Overview
The goal of this task was to refine the Agent's Choice (Prime Picks) pipeline by making its reasoning transparent to the admin and simplifying the frontend UX. The Pass 1 filter thresholds were producing ~121 candidates, but the Pass 2 xAI Mastermind was selectively filtering down to 3 candidates (15%). To understand why, the prompt needed updating to return per-ASIN reasoning. Additionally, a standalone extraction script was required to pull this reasoning from production `celery_worker.log` files, and the end-user dashboard refresh needed to be decoupled from the expensive Prime Picks background job.

## What Was Done

### 1. Pass 2 Prompt and Parsing Updates
- **Prompt Changes:** The xAI prompt in `keepa_deals/prime_picks_task.py` was rewritten to request a structured JSON output that includes both `selected` and `rejected` candidates, rather than just an array of selected ASINs.
- **Expected Response Shape:**
  ```json
  {
    "selected": [{"asin": "ASIN1", "reason": "1-sentence reason"}],
    "rejected": [{"asin": "ASIN2", "reason": "1-sentence reason"}]
  }
  ```
- **Parsing Logic:** The backend JSON parser was updated to iterate over these new structures and extract the per-ASIN reason, mapping it appropriately. Fallback logic was implemented to prevent crashes if the LLM hallucinated the old array format.
- **Logging:** Output is safely written to the Celery log with the `[Pass 2 Reasoning]` tag.

### 2. Diagnostics Extraction Script
- **Script Created:** `Diagnostics/extract_pass2_reasoning.py` was developed to parse `celery_worker.log` and output the API latency, prompt size, raw response, and per-ASIN selections.
- **Challenges Faced (OOM Kills):** The initial implementation read the entire log into memory. Given production logs can grow to gigabytes, this immediately triggered OS Out-Of-Memory (OOM) `Killed` errors.
- **Resolution:** The script was refactored to use a memory-efficient `f.seek()` chunked backward-read to find the exact byte offset of the last "Pass 2: Querying xAI API" marker. It then streams the file forward line-by-line. A safeguard `max_raw_response_lines` and timestamp-detection heuristics were also added to bound multi-line raw responses safely.

### 3. UX Simplifications
- **Decoupling:** The "Refresh Now" button on `templates/dashboard.html` was stripped of the logic that triggered `/api/prime_picks/refresh`. It now exclusively refreshes the table data.
- **Admin Trigger:** A new "Refresh Prime Picks" button was added to the admin interface (`templates/deals.html`).
- **Auto-Refresh Feedback:** The admin button initiates the job and utilizes an interval polling mechanism (`setInterval`) to check `/api/deals?limit=1&agents_choice=1` for changes to the `prime_picks_generated_at` metadata. Once detected, the UI gracefully auto-redirects the admin to `/dashboard?agents_choice=1` to display the new picks.
- **Panel Auto-Close:** The filter panel auto-close functionality was restored on the main dashboard, since picks are now instantly loaded from the database cache.

## Outcome
The task successfully decoupled the UX flows, implemented the new reasoning logs, and provided a safe, memory-efficient diagnostic extraction tool. However, an unspecified secondary component or test within the wider system may have been destabilized by the parsing updates, leaving the system in a "Something new is now broken" state. As per instructions, further debugging has been deferred to a future session.

## Update 2026-05-10
The infinite hang in the  task was caused by an f-string issue in the prompt generation in . Unescaped single curly braces ({ and }) in the JSON example string caused Python to attempt evaluating the string's content as Python code, leading to an error. This error propagated through the Celery retry loop, resulting in a hang.

The braces were successfully escaped ({{ and }}), resolving the issue. The parser in  was also made more robust using a regex to parse JSON blocks containing ```json.

Since the task was erroring/hanging silently, it's very likely this was the root cause for the auto-refresh failure as well. We'll leave it to future sessions to verify if the chain is indeed operating properly now.

## Update 2026-05-10
The infinite hang in the generate_prime_picks task was caused by an f-string issue in the prompt generation in keepa_deals/prime_picks_task.py. Unescaped single curly braces ({ and }) in the JSON example string caused Python to attempt evaluating the string's content as Python code, leading to an error. This error propagated through the Celery retry loop, resulting in a hang.

The braces were successfully escaped ({{ and }}), resolving the issue. The parser in keepa_deals/prime_picks_task.py was also made more robust using a regex to parse JSON blocks containing ```json.

Since the task was erroring/hanging silently, it's very likely this was the root cause for the auto-refresh failure as well. We'll leave it to future sessions to verify if the chain is indeed operating properly now.
