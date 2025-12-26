import math

# Simulation Constants
TOTAL_DEALS_TARGET = 10000
DEALS_PER_CHUNK = 20
COST_PER_DEAL = 12  # Estimated in backfiller.py
COST_PER_CHUNK = DEALS_PER_CHUNK * COST_PER_DEAL # 240 tokens
REFILL_RATE_PER_MINUTE = 5
MAX_TOKENS = 300

# Upserter Constants
UPSERTER_MIN_TOKENS = 20
UPSERTER_COST_PER_MIN = 1 # Minimum cost (1 call). If it processes deals, it's higher.

def simulate_backfill(strategy="conservative", with_upserter=True):
    print(f"\n--- Simulating Strategy: {strategy.upper()} (Upserter: {'ON' if with_upserter else 'OFF'}) ---")

    current_tokens = 300.0 # Start full
    deals_processed = 0
    minutes_elapsed = 0

    # State for conservative strategy
    waiting_for_full = False

    # State for optimized strategy
    waiting_for_threshold = False
    OPTIMIZED_THRESHOLD = 50
    OPTIMIZED_REFILL_TARGET = 55

    MAX_MINUTES = 60 * 24 * 365 # 1 year timeout

    while deals_processed < TOTAL_DEALS_TARGET:
        minutes_elapsed += 1
        if minutes_elapsed > MAX_MINUTES:
            print("TIMEOUT: Simulation exceeded 1 year. System is stuck.")
            return float('inf')

        # 1. Refill
        current_tokens += REFILL_RATE_PER_MINUTE
        if current_tokens > MAX_TOKENS:
            current_tokens = MAX_TOKENS

        # 2. Upserter Run (Every minute)
        if with_upserter:
            if current_tokens >= UPSERTER_MIN_TOKENS:
                current_tokens -= UPSERTER_COST_PER_MIN

        # 3. Backfiller Logic

        # Determine effective cost (actual consumption vs estimation logic)
        # Backfiller logic uses ESTIMATED cost to decide to wait.
        # But assumes 'deficit spending' allowed by API.

        if strategy == "conservative":
            # Logic: if tokens < estimated_cost: wait for max

            if waiting_for_full:
                if current_tokens >= MAX_TOKENS * 0.99: # Allow float tolerance
                    waiting_for_full = False
                else:
                    continue # Keep waiting

            if current_tokens < COST_PER_CHUNK:
                waiting_for_full = True
                continue
            else:
                # Process Chunk
                # We assume actual cost matches estimated for simplicity, or slightly less
                # But the DECISION to proceed is based on estimate.
                current_tokens -= COST_PER_CHUNK
                deals_processed += DEALS_PER_CHUNK

        elif strategy == "optimized":
            # Logic: if tokens > 50: allow call
            # if tokens < 50: wait for 55

            if waiting_for_threshold:
                if current_tokens >= OPTIMIZED_REFILL_TARGET:
                    waiting_for_threshold = False
                else:
                    continue

            if current_tokens > OPTIMIZED_THRESHOLD:
                current_tokens -= COST_PER_CHUNK # Allow going negative
                deals_processed += DEALS_PER_CHUNK

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
    print("Running Diagnostic Simulation for 10,000 Deals...")

    t_current = simulate_backfill(strategy="conservative", with_upserter=True)
    t_opt = simulate_backfill(strategy="optimized", with_upserter=True)

    print("\n--- SUMMARY ---")
    if t_current == float('inf'):
        print(f"Current Estimated Time: INFINITE (Stuck in Loop)")
    else:
        print(f"Current Estimated Time: {t_current/60:.1f} hours ({t_current/60/24:.1f} days)")

    print(f"Optimized Estimated Time: {t_opt/60:.1f} hours ({t_opt/60/24:.1f} days)")

    if t_current != float('inf'):
        print(f"Speedup Factor: {t_current/t_opt:.2f}x")
