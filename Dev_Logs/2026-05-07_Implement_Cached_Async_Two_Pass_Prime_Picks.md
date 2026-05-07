# Dev Log: Implement Cached Async Two-Pass Prime Picks
**Date:** 2026-05-07

## Overview
The goal of this task was to resolve the 504 Gateway Timeouts occurring when users attempted to filter deals using the "Agent's Choice" (Prime Picks) toggle. The existing implementation executed a synchronous two-pass pipeline on the fly: Pass 1 (SQL/math floor) to find 20 candidates, and Pass 2 (xAI evaluation against the `strategies.json` and `intelligence.json` files) to select the final picks. Pass 2 was failing because injecting the entirety of `strategies.json` (~14,000 rules, ~8.4MB) into the xAI prompt exceeded the context window and timeout limits of the UI request.

To fix this, the architectural decision was to:
1. Move the Two-Pass pipeline to an asynchronous Celery background task (`generate_prime_picks`).
2. Implement a payload reduction strategy to dramatically shrink the `strategies.json` payload sent to xAI in Pass 2.
3. Cache the final selected Prime Picks in a new database table (`prime_picks`).
4. Modify the dashboard read path to read exclusively from the cached table when the toggle is active.

## Challenges
**Context Token Limit & Payload Reduction:**
The primary blocker was the sheer volume of rules in `strategies.json` (~14,000 distinct entries), which mathematically guarantees a timeout or context overflow in `grok-4-fast-reasoning`. Since editing or permanently consolidating `strategies.json` was out of scope, a dynamic in-memory solution was required.

I initially evaluated doing semantic TF-IDF/Jaccard RAG in memory to reduce the size. However, upon analyzing the data distribution of the strategies, it was clear that four categories (General, Buying, Pricing, Risk) comprised 93% of the rules (~13,300). Taking a random slice or arbitrary first 100 rules was not optimal.

## Solution & Implementation
To address the challenges, I implemented **"Tiered Strategy Injection"**.

1. **Payload Reduction via Quality Caps:**
   Instead of arbitrary slices, the strategy parser (`get_tiered_strategies()`) now iterates through `strategies.json` and selects only rules marked with `"confidence": "High"`. It limits the core universal categories (General, Risk, Buying, Pricing) to a strict cap of 30 High-confidence strategies each.
2. **Dynamic Context Matching:**
   The parser extracts a concatenated string of keywords from the top 20 candidates (Title, Seasonality). If a specific category rule (e.g., "Seasonality") triggers based on those keywords (e.g. "textbook"), it dynamically injects up to 30 High-confidence rules from that specific category. This brings the final prompt size down to ~400-500 targeted rules, which Grok processes successfully in under 30 seconds.
3. **Pass 1 Thresholds (Smart Floor):**
   The SQL math floor was enforced with the following baseline criteria:
   - `Profit >= $10.00` (Lowered to 10 dynamically in logic)
   - `ROI >= 15% AND ROI <= 300%` (Hard 300% cap added to prevent outlier/manipulated spikes).
   - `Deal_Trust >= 40`
   - `List_At > 0 AND List_At <= 1500`
   - `1yr_Avg` is valid and non-zero.
4. **Asynchronous Execution & Caching:**
   - Created a new Celery task `keepa_deals.prime_picks_task.generate_prime_picks`.
   - Chained this task to run immediately after the `janitor.clean_stale_deals` task.
   - Updated `keepa_deals/db_utils.py` to create a new `prime_picks` table (`asin`, `rank`, `score`, `generated_at`, `run_id`). The table uses an atomic transaction to wipe old runs and replace them with the latest UUID run.
5. **Dashboard Read Path & UX:**
   - `wsgi_handler.py` `api_deals` route now intercepts `agents_choice=True` and issues a fast SQL JOIN against the `prime_picks` table.
   - A new route `/api/prime_picks/refresh` allows users to manually trigger the background task without blocking the UI.
   - Modified `dashboard.html` JS to track the `prime_picks_generated_at` metadata variable via the existing background poller, showing a non-intrusive "New Prime Picks available" toast notification when the background job finishes.

## Outcome
**Success.** The pipeline now runs flawlessly in the background. In local testing with an actual populated database backup, Pass 1 successfully evaluated and scored candidates, Pass 2 queried xAI successfully with the reduced semantic payload, and the results were cached atomically in `prime_picks`. The frontend polling successfully surfaces the new picks without any 504 errors.
