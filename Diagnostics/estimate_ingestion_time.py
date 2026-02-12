#!/usr/bin/env python3
import math
import sys

# --- Constants ---
TOTAL_DEALS_TARGET = 10000  # Updated to reflect "TONS o Deals" query volume
BATCH_SIZE = 5
REFILL_RATE_PER_MINUTE = 5
MAX_TOKENS = 300
MIN_THRESHOLD = 1
BURST_THRESHOLD = 40

# Cost Models (Smart Ingestor V3)
COST_PEEK = 2     # Stage 1: Peek (Stats=365) - 2 tokens per ASIN
COST_COMMIT = 20  # Stage 2: Commit (Full History) - 20 tokens per ASIN (Only for Survivors)

def simulate_ingestion(survivor_rate=0.2):
    """
    Simulates time to ingest deals using the Smart Ingestor logic.
    survivor_rate: Percentage of deals (0.0 to 1.0) that pass the Peek filter and require full commit.
    """
    print(f"\n--- Simulating Smart Ingestor (Survivor Rate: {int(survivor_rate*100)}%) ---")

    current_tokens = 300.0
    deals_processed = 0
    minutes_elapsed = 0
    is_paused = False

    # Calculate Average Cost Per Batch
    # Batch Cost = (BatchSize * PEEK) + (BatchSize * SurvivorRate * COMMIT)
    # e.g., Batch 5, Survivor 20%: (5 * 2) + (5 * 0.2 * 20) = 10 + 20 = 30 tokens
    avg_cost_per_batch = (BATCH_SIZE * COST_PEEK) + (BATCH_SIZE * survivor_rate * COST_COMMIT)
    avg_cost_per_batch = math.ceil(avg_cost_per_batch)

    print(f"  > Batch Size: {BATCH_SIZE}")
    print(f"  > Avg Cost Per Batch: {avg_cost_per_batch} tokens")
    print(f"  > Tokens per Deal: {avg_cost_per_batch / BATCH_SIZE:.1f}")

    while deals_processed < TOTAL_DEALS_TARGET:
        minutes_elapsed += 1

        # 1. Refill
        current_tokens += REFILL_RATE_PER_MINUTE
        if current_tokens > MAX_TOKENS:
            current_tokens = MAX_TOKENS

        # 2. Pause / Resume Logic
        if is_paused:
            if current_tokens >= BURST_THRESHOLD:
                is_paused = False # Resume!
            else:
                continue # Still waiting

        # 3. Processing Logic
        # Try to process as many batches as possible in this minute
        # Assumption: API calls are fast relative to 1 minute, but limited by tokens.

        # While we have tokens above MIN_THRESHOLD
        while current_tokens >= MIN_THRESHOLD and deals_processed < TOTAL_DEALS_TARGET:
            # Check cost
            # Deficit Logic: We can spend if we start above MIN_THRESHOLD (1).
            # We subtract the full cost.
            current_tokens -= avg_cost_per_batch
            deals_processed += BATCH_SIZE

            # If we drop below threshold, we must pause for next cycle
            if current_tokens < MIN_THRESHOLD:
                is_paused = True
                break

    hours = minutes_elapsed / 60
    days = hours / 24

    print(f"  > Time: {minutes_elapsed} min ({hours:.1f} hours / {days:.1f} days)")
    return minutes_elapsed

def analyze_token_bucket():
    print("\n--- Theoretical Analysis: Will we reach 300 tokens? ---")
    print("Q: With the 40 token trigger, will we ever reach the full 300 tokens?")
    print("A: NO. And that is INTENTIONAL.")

    print("\nExplanation:")
    print("1. The Token Bucket (300) is a 'Buffer', not a 'Speed Limit'.")
    print("2. Your speed is strictly limited by the Refill Rate (5 tokens/min).")
    print("3. Filling the bucket to 300 tokens takes 60 minutes of doing NOTHING.")
    print("4. Emptying the bucket allows you to work. Sitting at 300 means you wasted time.")
    print("5. By triggering at 40, we start working sooner (8 mins wait vs 60 mins wait).")
    print("6. Result: You process the EXACT SAME amount of data per day (7200 tokens worth), just spread out more evenly.")
    print("   - Old Way: Wait 1 hr, Burst for 5 mins, Wait 1 hr.")
    print("   - New Way: Wait 8 mins, Burst for 1 min, Wait 8 mins.")
    print("   - Total Throughput: Identical.")
    print("   - Latency/Stall Perception: Much better (Dashboard updates frequently).")

if __name__ == "__main__":
    print(f"=== Keepa Ingestion Estimator ===")
    print(f"Target: {TOTAL_DEALS_TARGET} Deals")
    print(f"Refill Rate: {REFILL_RATE_PER_MINUTE} tokens/min")

    # Scenario 1: High Selectivity (Only 10% worth saving) - "Smart"
    t_smart = simulate_ingestion(survivor_rate=0.1)

    # Scenario 2: Moderate Selectivity (20% worth saving) - "Normal"
    t_normal = simulate_ingestion(survivor_rate=0.2)

    # Scenario 3: Low Selectivity (50% worth saving) - "Loose Filters"
    t_loose = simulate_ingestion(survivor_rate=0.5)

    # Scenario 4: Worst Case (100% need full fetch) - "Dumb / Old Way"
    t_dumb = simulate_ingestion(survivor_rate=1.0)

    print("\n=== SUMMARY ===")
    print(f"1. Smart Mode (10% Survivors): {t_smart/60:.1f} hours")
    print(f"2. Normal Mode (20% Survivors): {t_normal/60:.1f} hours")
    print(f"3. Loose Mode (50% Survivors): {t_loose/60:.1f} hours")
    print(f"4. Legacy Mode (100% Full Fetch): {t_dumb/60:.1f} hours")

    analyze_token_bucket()
