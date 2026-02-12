import redis
import os
import json
import time
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

def check_pause_status():
    print("--- Keepa Token & Pause Status Diagnostic ---")

    redis_url = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')
    try:
        r = redis.Redis.from_url(redis_url, decode_responses=True)
        r.ping()
    except Exception as e:
        print(f"[ERROR] Could not connect to Redis: {e}")
        return

    # Keys from TokenManager
    KEY_TOKENS = "keepa_tokens_left"
    KEY_RATE = "keepa_refill_rate"
    KEY_RECHARGE = "keepa_recharge_mode_active"
    KEY_START_TIME = "keepa_recharge_start_time"

    tokens = r.get(KEY_TOKENS)
    rate = r.get(KEY_RATE)
    recharge_active = r.get(KEY_RECHARGE)
    start_time_str = r.get(KEY_START_TIME)

    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Redis Connection: OK")

    print("\n[Token State]")
    print(f"  Tokens Available: {tokens if tokens is not None else 'Unknown (Key missing)'}")
    print(f"  Refill Rate:      {rate if rate is not None else 'Unknown (Key missing)'}/min")

    print("\n[Pause / Recharge Status]")
    if recharge_active == "1":
        print("  STATUS:  PAUSED (Recharge Mode Active)")

        # Determine dynamic burst threshold (Logic from TokenManager)
        burst_threshold = 280
        try:
            rate_val = float(rate) if rate else 5.0
            if rate_val < 10:
                burst_threshold = 40
        except ValueError:
            rate_val = 5.0

        print(f"  Reason:  Waiting for tokens to reach {burst_threshold} (Burst Threshold).")

        # Display Recharge Timer Info
        if start_time_str:
            try:
                start_ts = float(start_time_str)
                elapsed = time.time() - start_ts
                limit = 3600 # 60 minutes
                print(f"  Recharge Duration: {elapsed/60:.1f} minutes (Limit: 60m)")
                if elapsed > limit:
                     print("  CRITICAL: TIMEOUT EXCEEDED. System should force resume shortly.")
            except:
                pass
        else:
             print("  Recharge Duration: Unknown (Key missing - will be adopted on next check)")

        if tokens:
            try:
                t_val = float(tokens)
                if t_val < burst_threshold:
                    needed = burst_threshold - t_val
                    mins_left = needed / rate_val
                    print(f"  Progress: {t_val:.1f} / {burst_threshold}.0")
                    print(f"  Est. Wait (Refill): {mins_left:.1f} minutes")
                else:
                    print(f"  Progress: {t_val:.1f} / {burst_threshold}.0 (Ready to Resume)")
            except:
                pass
    else:
        print("  STATUS:  RUNNING (Normal Operation)")
        print("  Note:    Recharge mode is NOT active.")

    print("\n[Lock Status]")
    # Updated to reflect Smart Ingestor Refactor
    locks = ["smart_ingestor_lock", "recalculate_deals_lock"]
    for lock in locks:
        val = r.get(lock)
        print(f"  {lock}: {'LOCKED' if val else 'Free'}")

if __name__ == "__main__":
    check_pause_status()
