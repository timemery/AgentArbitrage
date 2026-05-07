# Dev Log: Agent's Choice Filter 504 Timeout Investigation Part 2
**Date:** 2026-05-07

## Task Overview
The goal of this task was to resolve an ongoing 504 Gateway Timeout error that occurs when applying the "Agent's Choice" (Prime Picks) filter on the web application dashboard. A previous agent had already attempted to fix this by swapping the HTTP client to `requests` and ensuring the fallback logic was sound, but the task had failed entirely and the timeout persisted. This task also ultimately failed entirely.

## Challenges Faced
- **Payload Size:** It was discovered that during the "Pass 2: The xAI Mastermind" evaluation in `wsgi_handler.py`, the system was loading the entirety of `strategies.json` as a raw JSON string into the prompt payload. Since the file is over 8MB on disk and contains over 14,000 strategies, the resulting JSON string sent to the API was around 7.5MB.
- **Model Constraints:** The required model for Pass 2 (`grok-4-fast-reasoning`) has strict limits. When attempting to send massive payloads, the xAI API either rejects them immediately if they exceed max prompt lengths (e.g., `grok-4-0709` limit is 256k tokens, the payload was 1.7M tokens) or silently times out trying to process the sheer volume of data, resulting in a 504 error on the web end.
- **Persistent Timeout Despite Reductions:** The `ava_advisor.py` module contained a helper function `load_strategies()` designed to format these strategies into a more concise string. Even when utilizing this function instead of raw JSON parsing (which reduced the string size from 7.5MB to roughly 2.7MB), and completely excluding `intelligence.json` from the prompt, the application still threw a 504 Gateway Timeout when executing through the UI (as seen in the provided screenshot).

## Actions Taken
- **Diagnostic Scripts:** Multiple test scripts were run locally to measure the xAI API's response to payloads of varying sizes. This confirmed that passing even subsets of the 14,000+ strategies caused connection timeouts after 20 to 60 seconds depending on the model and volume.
- **Payload Optimization:** Modified `wsgi_handler.py` to stop using `json.load()` and `json.dumps()` for the `strategies_data`. Replaced it with the `load_strategies()` helper function to strip JSON boilerplate and inject raw text rules.
- **Prompt Alteration:** Updated the Mastermind prompt to instruct the AI to evaluate based on the provided "text rules" rather than "JSON rules", and explicitly excluded `intelligence.json` to save tokens.
- **Verification:** Ran the local diagnostic test suite successfully. However, the manual UI test still resulted in a 504 Gateway Timeout on the frontend.

## Outcome
**Task Status:** Unsuccessful.

Despite significantly reducing the payload size by formatting the data and excluding non-actionable intelligence, the volume of strategies (14k+) remains too large for the xAI API to process within the typical HTTP timeout window of the WSGI application. The task failed, and the next agent will need to investigate further strategies to handle the massive dataset (e.g., semantic search, vector embeddings, RAG, or further aggressive deduplication/chunking) to bring the payload size down to a manageable limit for the xAI API.
