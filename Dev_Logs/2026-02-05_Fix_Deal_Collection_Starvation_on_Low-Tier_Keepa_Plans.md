# 2026-02-05: Fix Deal Collection Starvation on Low-Tier Keepa Plans

## Overview

The "Deal Collection" pipeline was failing to ingest new data on the production environment, which operates on the lowest tier Keepa API plan (5 tokens/minute). Despite diagnostics reporting system health as "PASS", the deal count remained stagnant (stuck at 62 deals).

## Root Cause Analysis

### 1. Token Starvation (The "Livelock")

The system consists of two main deal collection tasks:

- **Upserter (`simple_task`)**: Frequent, low-cost updates.
- **Backfiller (`backfiller`)**: Less frequent, high-cost historical data fetches.

The `TokenManager` implemented a "Priority Pass" feature designed to allow small tasks (cost < 10 tokens) to run even if the token bucket was low. **The Problem:** On a 5 token/min plan, the Upserter would constantly consume incoming tokens via the Priority Pass. This kept the token bucket permanently near zero. The Backfiller, requiring a larger buffer (e.g., 60 tokens) to start safely, never accumulated enough tokens to run. It was effectively starved by the Upserter.

### 2. Inefficient "Sipping" vs. "Bursting"

With a refill rate of 5 tokens/min, processing a standard batch of 2 ASINs (Cost ~40 tokens) required waiting ~8 minutes. The system was spending 99% of its time sleeping and 1% working. This inefficient "sipping" behavior increased the likelihood of timeouts and reduced overall throughput.

### 3. Data Loss via In-Memory Batching

To compound the issue, both tasks were configured to fetch and process large batches (e.g., 200 deals) *completely* in memory before performing a database upsert. **The Problem:** With the mandatory wait times introduced to respect the rate limit, processing a single batch could take 14+ hours. If the system was restarted (e.g., via a deploy or crash) during this window, **all progress was lost**. This explained why the deal count never increased despite logs showing activity.

## Solutions Implemented

### 1. "Refill-to-Full" (Burst) Strategy

We modified `keepa_deals/token_manager.py` to implement a "Recharge Mode".

- **Logic:** When tokens drop below a critical threshold (`20`) on a low-tier plan (`< 10/min`), the system sets a Redis flag (`keepa_recharge_mode_active`).
- **Behavior:** All workers pause execution and reject token requests until the bucket refills to **280 tokens** (near max).
- **Benefit:** This transforms the workflow from an inefficient trickle to a powerful hourly "Burst", allowing ~15-20 deals to be processed concurrently with high efficiency.

### 2. Starvation Prevention

- **Disable Priority Pass:** We disabled the "Priority Pass" for low-tier plans. Now, *all* tasks, regardless of size, must respect the `MIN_TOKEN_THRESHOLD`. This ensures fair competition and prevents the Upserter from monopolizing the stream.
- **Dynamic Batch Sizing:** We modified `backfiller.py` and `simple_task.py` to detect the low refill rate and automatically reduce their batch size to **1 ASIN**. This lowers the "activation energy" required to run a task from ~40 tokens to ~20 tokens.

### 3. Incremental Upserts

We refactored `keepa_deals/simple_task.py` and `keepa_deals/backfiller.py` to **interleave** fetching and upserting.

- **Old Flow:** `Fetch All (200) -> Process All -> Upsert All`. (Risk: Data loss if crash occurs after 10 hours).
- **New Flow:** `Loop Chunk (Size 1): Fetch -> Process -> Upsert`. (Benefit: Data is secured immediately after processing).

## Outcome

The task was **successful**.

- **Verification:** Unit tests (`tests/verify_token_starvation_fix.py`, `tests/verify_burst_logic.py`) confirmed the logic.
- **Observability:** Logs now clearly show the system entering "Recharge Mode", waiting for the full bucket, and then executing a "Burst", with deal counts increasing incrementally in the database.