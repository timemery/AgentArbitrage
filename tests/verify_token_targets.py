import math

def calculate_wait_time(current_tokens, cost, threshold, refill_rate=5.0):
    target = threshold + cost
    tokens_needed = target - current_tokens

    if tokens_needed <= 0:
        return 0, target

    wait_minutes = tokens_needed / refill_rate
    wait_seconds = math.ceil(wait_minutes * 60)
    return wait_seconds, target

def run_verification():
    current_tokens = 24.0
    refill_rate = 5.0

    print(f"--- Simulation: Tokens={current_tokens}, Refill={refill_rate}/min ---\n")

    # Scenario A: Current Upserter
    cost_a = 200 # 10 ASINs * 20
    threshold_a = 50
    wait_a, target_a = calculate_wait_time(current_tokens, cost_a, threshold_a, refill_rate)
    print(f"Scenario A (Current Upserter): Cost={cost_a}, Threshold={threshold_a}")
    print(f"  -> Target: {target_a}")
    print(f"  -> Wait: {wait_a} seconds ({wait_a/60:.1f} minutes)")

    # Scenario B: Current Backfiller
    cost_b = 100 # 5 ASINs * 20
    threshold_b = 80
    wait_b, target_b = calculate_wait_time(current_tokens, cost_b, threshold_b, refill_rate)
    print(f"Scenario B (Current Backfiller): Cost={cost_b}, Threshold={threshold_b}")
    print(f"  -> Target: {target_b}")
    print(f"  -> Wait: {wait_b} seconds ({wait_b/60:.1f} minutes)")

    # Scenario C: Proposed Upserter
    cost_c = 100 # 5 ASINs * 20
    threshold_c = 50
    wait_c, target_c = calculate_wait_time(current_tokens, cost_c, threshold_c, refill_rate)
    print(f"Scenario C (Proposed Upserter): Cost={cost_c}, Threshold={threshold_c}")
    print(f"  -> Target: {target_c}")
    print(f"  -> Wait: {wait_c} seconds ({wait_c/60:.1f} minutes)")

    print("\n--- Analysis ---")

    # Check Starvation
    if wait_a > wait_b:
        print(f"[CONFIRMED] Starvation: Upserter (A) waits {wait_a}s > Backfiller (B) {wait_b}s.")
        print("  The Backfiller will likely snatch the tokens before Upserter can run.")
    else:
        print("[FAILED] Starvation not observed.")

    # Check Fix
    if wait_c < wait_b:
        print(f"[CONFIRMED] Priority Fix: Proposed Upserter (C) waits {wait_c}s < Backfiller (B) {wait_b}s.")
        print("  The Upserter will now have priority.")
    else:
        print("[FAILED] Priority fix failed.")

if __name__ == "__main__":
    run_verification()
