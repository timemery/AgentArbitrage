#!/usr/bin/env python3
import math
import sys

# --- Constants ---
TOTAL_DEALS_TARGET = 10000
MAX_TOKENS = 300.0
MIN_THRESHOLD = 1.0

# Cost Models (Smart Ingestor V3.1)
COST_PEEK_PER_ASIN = 2.0     # Stage 1: Peek (Stats=365)
COST_COMMIT_PER_ASIN = 20.0  # Stage 2: Commit (Full History)
COMMIT_BATCH_SIZE = 5        # Always 5 for heavy commits

def simulate_ingestion(label, refill_rate, peek_batch_size, burst_threshold, survivor_rate=0.1):
    """
    Simulates time to ingest deals using the Smart Ingestor v3.1 logic.
    """
    print(f"\n--- Simulation: {label} ---")
    print(f"  > Refill Rate: {refill_rate}/min")
    print(f"  > Peek Batch Size: {peek_batch_size}")
    print(f"  > Burst Threshold: {burst_threshold}")
    print(f"  > Survivor Rate: {int(survivor_rate*100)}% (Rejection Rate: {int((1-survivor_rate)*100)}%)")

    current_tokens = MAX_TOKENS # Start full
    deals_processed = 0
    minutes_elapsed = 0
    is_paused = False

    # Track stats
    total_peek_cost = 0
    total_commit_cost = 0

    while deals_processed < TOTAL_DEALS_TARGET:
        minutes_elapsed += 1

        # 1. Refill
        current_tokens += refill_rate
        if current_tokens > MAX_TOKENS:
            current_tokens = MAX_TOKENS

        # 2. Pause / Resume Logic (Burst Mode)
        if is_paused:
            if current_tokens >= burst_threshold:
                is_paused = False # Resume!
            else:
                continue # Still waiting

        # 3. Processing Logic
        # Try to process as many batches as possible in this minute
        while current_tokens >= MIN_THRESHOLD and deals_processed < TOTAL_DEALS_TARGET:

            # --- Calculate Cost for ONE Peek Batch ---
            # 1. Peek Cost
            # If remaining deals < batch size, just take remaining
            actual_batch_size = min(peek_batch_size, TOTAL_DEALS_TARGET - deals_processed)
            cost_peek = actual_batch_size * COST_PEEK_PER_ASIN

            # 2. Commit Cost (Survivors)
            # Statistical expectation of survivors
            # Note: We use float here to represent the 'Average Case' over many iterations.
            # Using ceil() for batch_size=1 would incorrectly assume EVERY deal needs commitment (Cost 22).
            expected_survivors = actual_batch_size * survivor_rate

            # Cost is simply 20 per survivor (batching logic is internal to prevent shock, but cost is linear)
            cost_commit = expected_survivors * COST_COMMIT_PER_ASIN

            total_batch_cost = cost_peek + cost_commit

            # Check if we can afford this batch (Deficit Spending allowed down to -180, but here we simplify)
            # The TokenManager allows us to go negative if we start positive.
            # So if current_tokens >= MIN_THRESHOLD, we can spend.

            current_tokens -= total_batch_cost
            deals_processed += actual_batch_size

            total_peek_cost += cost_peek
            total_commit_cost += cost_commit

            # If we drop below threshold, we pause for next cycle
            # Note: We can go negative here, simulating the deficit.
            # In reality, if we go below -180 we stop, but Smart Ingestor manages batch sizes to avoid this.
            if current_tokens < MIN_THRESHOLD:
                is_paused = True
                break

    hours = minutes_elapsed / 60
    days = hours / 24

    avg_tokens_per_deal = (total_peek_cost + total_commit_cost) / TOTAL_DEALS_TARGET

    print(f"  > Time: {minutes_elapsed} min ({hours:.1f} hours)")
    print(f"  > Efficiency: {avg_tokens_per_deal:.1f} tokens/deal")

    return minutes_elapsed

if __name__ == "__main__":
    print(f"=== Smart Ingestor v3.1 Performance Estimator ===")
    print(f"Target: {TOTAL_DEALS_TARGET} Deals")
    print(f"Assumption: {int((1-0.1)*100)}% Rejection Rate (10% Survivors)")

    # Scenario 1: Fast Connection (Upgrade)
    t_fast = simulate_ingestion(
        label="Fast / Upgraded Plan",
        refill_rate=20,
        peek_batch_size=50,
        burst_threshold=280,
        survivor_rate=0.1
    )

    # Scenario 2: Standard/Slow Connection
    t_slow = simulate_ingestion(
        label="Standard / Safe Mode",
        refill_rate=5,
        peek_batch_size=20,
        burst_threshold=40,
        survivor_rate=0.1
    )

    # Scenario 3: Critically Low (worst case)
    t_critical = simulate_ingestion(
        label="Critically Low Refill (<10/min)",
        refill_rate=5, # Still 5, but logic forces small batches
        peek_batch_size=1,
        burst_threshold=40,
        survivor_rate=0.1
    )

    print("\n=== SUMMARY ===")
    print(f"1. Fast Mode (20/min): {t_fast/60:.1f} hours")
    print(f"2. Safe Mode (5/min):  {t_slow/60:.1f} hours")
    print(f"3. Critical Mode (Batch 1): {t_critical/60:.1f} hours")

    print("\n=== NOTE ON REJECTION RATES ===")
    print("The 90% rejection rate is the primary driver of speed.")
    print("By filtering 90% of deals at the 'Peek' stage (Cost 2), we save massive amounts of tokens.")
    print("Old Logic: 1000 deals * 20 tokens = 20,000 tokens.")
    print("New Logic: (1000 * 2) + (100 * 20) = 2,000 + 2,000 = 4,000 tokens.")
    print("Result: 5x Faster Ingestion.")
