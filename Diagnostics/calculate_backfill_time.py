#!/usr/bin/env python3
import math

# --- Simulation Constants ---
TOTAL_DEALS_TARGET = 24000  # Updated to reflect "TONS o Deals" query volume
DEALS_PER_CHUNK = 20
REFILL_RATE_PER_MINUTE = 5
MAX_TOKENS = 300

# Cost Models
COST_PER_DEAL_NEW = 20     # High Cost: Full history fetch (3 years)
COST_PER_DEAL_EXISTING = 1 # Low Cost: "Lightweight" update (Current stats only)

# Upserter Constants
UPSERTER_MIN_TOKENS = 20
UPSERTER_COST_PER_MIN = 2 # Assuming minimal activity

def simulate_backfill(strategy="standard", maintenance_ratio=0.0):
    """
    Simulates time to process deals.
    maintenance_ratio: Percentage of deals (0.0 to 1.0) that are 'Existing' and eligible for cheap updates.
    """
    label = f"{strategy.upper()} (Maintenance: {int(maintenance_ratio*100)}%)"
    print(f"\n--- Simulating Strategy: {label} ---")

    current_tokens = 300.0
    deals_processed = 0
    minutes_elapsed = 0

    # Calculate Average Cost Per Chunk based on ratio
    # e.g., if 50% are existing: (10 * 20) + (10 * 1) = 210 tokens per chunk
    avg_cost_per_chunk = (DEALS_PER_CHUNK * (1 - maintenance_ratio) * COST_PER_DEAL_NEW) + \
                         (DEALS_PER_CHUNK * maintenance_ratio * COST_PER_DEAL_EXISTING)

    # Round up because tokens are integers in practice
    avg_cost_per_chunk = math.ceil(avg_cost_per_chunk)

    print(f"  > Avg Cost Per Chunk ({DEALS_PER_CHUNK} deals): {avg_cost_per_chunk} tokens")

    # Optimization Thresholds
    OPTIMIZED_THRESHOLD = 50
    OPTIMIZED_REFILL_TARGET = 55
    waiting_for_threshold = False

    MAX_MINUTES = 60 * 24 * 365 # 1 year timeout

    while deals_processed < TOTAL_DEALS_TARGET:
        minutes_elapsed += 1
        if minutes_elapsed > MAX_MINUTES:
            print("TIMEOUT: Simulation exceeded 1 year.")
            return float('inf')

        # 1. Refill
        current_tokens += REFILL_RATE_PER_MINUTE
        if current_tokens > MAX_TOKENS:
            current_tokens = MAX_TOKENS

        # 2. Upserter Run (Every minute)
        # Prioritize Upserter: It eats first
        if current_tokens >= UPSERTER_MIN_TOKENS:
            current_tokens -= UPSERTER_COST_PER_MIN

        # 3. Backfiller Logic (Optimized 'Deficit' Strategy)
        if waiting_for_threshold:
            if current_tokens >= OPTIMIZED_REFILL_TARGET:
                waiting_for_threshold = False
            else:
                continue

        # Check if we have enough tokens for *ONE* chunk (or are allowed to go into deficit)
        # The 'Optimized' strategy allows dipping into negative if we are above threshold
        if current_tokens > OPTIMIZED_THRESHOLD:
            current_tokens -= avg_cost_per_chunk
            deals_processed += DEALS_PER_CHUNK

            # If we went below threshold (or negative), trigger wait
            if current_tokens < OPTIMIZED_THRESHOLD:
                waiting_for_threshold = True
        else:
            waiting_for_threshold = True
            continue

    hours = minutes_elapsed / 60
    days = hours / 24
    print(f"Time to process {TOTAL_DEALS_TARGET} deals: {minutes_elapsed} minutes")
    print(f"Hours: {hours:.2f}")
    print(f"Days: {days:.2f}")

    return minutes_elapsed

if __name__ == "__main__":
    print(f"Running Diagnostic Simulation for {TOTAL_DEALS_TARGET} Deals...")
    print(f"Refill Rate: {REFILL_RATE_PER_MINUTE} tokens/min")

    # Scenario 1: Fresh Start (Everything is New)
    t_fresh = simulate_backfill(strategy="standard", maintenance_ratio=0.0)

    # Scenario 2: 50% Maintenance (Half the deals are already in DB)
    t_mixed = simulate_backfill(strategy="optimized", maintenance_ratio=0.5)

    # Scenario 3: 90% Maintenance (Most deals in DB, just refreshing)
    t_maint = simulate_backfill(strategy="optimized", maintenance_ratio=0.9)

    print("\n--- SUMMARY ---")
    print(f"1. Fresh Start (0% Existing): {t_fresh/60/24:.1f} days")
    print(f"2. Mixed Mode (50% Existing): {t_mixed/60/24:.1f} days")
    print(f"3. Maintenance (90% Existing): {t_maint/60/24:.1f} days")

    if t_fresh != float('inf') and t_maint != float('inf'):
        print(f"\nPotential Speedup (Fresh vs Maintenance): {t_fresh/t_maint:.1f}x")
