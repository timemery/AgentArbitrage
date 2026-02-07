import redis
import os
import json
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

    tokens = r.get(KEY_TOKENS)
    rate = r.get(KEY_RATE)
    recharge_active = r.get(KEY_RECHARGE)

    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Redis Connection: OK")

    print("\n[Token State]")
    print(f"  Tokens Available: {tokens if tokens is not None else 'Unknown (Key missing)'}")
    print(f"  Refill Rate:      {rate if rate is not None else 'Unknown (Key missing)'}/min")

    print("\n[Pause / Recharge Status]")
    if recharge_active == "1":
        print("  STATUS:  PAUSED (Recharge Mode Active)")
        print("  Reason:  Waiting for tokens to reach 280 (Burst Threshold).")
        if tokens:
            try:
                t_val = float(tokens)
                if t_val < 280:
                    needed = 280 - t_val
                    rate_val = float(rate) if rate else 5.0
                    mins_left = needed / rate_val
                    print(f"  Progress: {t_val:.1f} / 280.0")
                    print(f"  Est. Wait: {mins_left:.1f} minutes")
                else:
                    print(f"  Progress: {t_val:.1f} / 280.0 (Ready to Resume)")
            except:
                pass
    else:
        print("  STATUS:  RUNNING (Normal Operation)")
        print("  Note:    Recharge mode is NOT active.")

    print("\n[Lock Status]")
    locks = ["backfill_deals_lock", "simple_task_lock", "recalculate_deals_lock"]
    for lock in locks:
        val = r.get(lock)
        print(f"  {lock}: {'LOCKED' if val else 'Free'}")

if __name__ == "__main__":
    check_pause_status()
