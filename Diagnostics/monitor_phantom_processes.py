import psutil
import time
from datetime import datetime
import os

LOG_FILE = "/var/www/agentarbitrage/phantom_process_monitor.log"

def log(msg):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    entry = f"{ts} - {msg}"
    print(entry)
    with open(LOG_FILE, 'a') as f:
        f.write(entry + "\n")

def check_phantom_processes():
    log("Scanning for Phantom Python Processes (Running > 1 hour)...")

    # Get current time
    now = time.time()

    found = False
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time', 'username']):
        try:
            if 'python' in proc.info['name'].lower():
                # Filter out system processes or legitimate long-runners if any
                cmdline = " ".join(proc.info['cmdline'] or [])

                # Ignore the monitor itself
                if "monitor_phantom_processes.py" in cmdline:
                    continue

                # Calculate age
                age_seconds = now - proc.info['create_time']
                age_hours = age_seconds / 3600.0

                if age_hours > 1.0:
                    found = True
                    log(f"[ALERT] Phantom Candidate Found: PID={proc.info['pid']}, Age={age_hours:.1f}h, Cmd={cmdline}")
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass

    if not found:
        log("No phantom processes detected.")

if __name__ == "__main__":
    check_phantom_processes()
