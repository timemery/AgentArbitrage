import sys
import os
from celery import Celery
import redis

# Add project root to path
sys.path.append(os.getcwd())

from worker import celery_app

def check_system_status():
    print("--- System Status Diagnostic ---")

    # 1. Check Redis Locks
    r = redis.Redis.from_url('redis://127.0.0.1:6379/0')
    backfill_lock_key = "backfill_deals_lock"
    simple_lock_key = "update_recent_deals_lock"

    bf_lock = r.get(backfill_lock_key)
    st_lock = r.get(simple_lock_key)

    print(f"Backfill Lock ({backfill_lock_key}): {'LOCKED' if bf_lock else 'FREE'}")
    if bf_lock:
        print(f"  -> Lock Value: {bf_lock}")
        ttl = r.ttl(backfill_lock_key)
        print(f"  -> TTL: {ttl} seconds")

    print(f"Simple Task Lock ({simple_lock_key}): {'LOCKED' if st_lock else 'FREE'}")

    # 2. Check Active Celery Tasks
    print("\n--- Active Celery Tasks ---")
    i = celery_app.control.inspect()
    active = i.active()

    if not active:
        print("No active tasks found (or worker not responding).")
    else:
        for worker, tasks in active.items():
            print(f"Worker: {worker}")
            if not tasks:
                print("  (Idle)")
            for task in tasks:
                print(f"  - Name: {task['name']}")
                print(f"    ID: {task['id']}")
                print(f"    Args: {task['args']}")
                print(f"    Started: {task.get('time_start')}")

if __name__ == "__main__":
    check_system_status()
