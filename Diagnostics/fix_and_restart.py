#!/usr/bin/env python3
import subprocess
import time
import os
import sys

def run_command(cmd, shell=True):
    print(f"Executing: {cmd}")
    try:
        result = subprocess.run(cmd, shell=shell, check=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {e}")
        print(f"STDERR: {e.stderr}")
        return False

def main():
    print("--- Starting Automated System Fix & Restart ---")

    # Check if we are in the right directory
    cwd = os.getcwd()
    print(f"Current Directory: {cwd}")

    # 1. Run Cleanup
    print("\n[Step 1] Running Forceful Cleanup...")
    # Note: sudo might fail in sandbox, but we try. If in production, it's needed.
    if os.path.exists("./kill_everything_force.sh"):
        success = run_command("bash kill_everything_force.sh")
    else:
        print("Error: kill_everything_force.sh not found!")
        success = False

    if not success:
        print("Cleanup failed. Attempting to proceed regardless (might be permission issues in sandbox).")

    # 2. Run Start
    print("\n[Step 2] Restarting Services...")
    if os.path.exists("./start_celery.sh"):
        success = run_command("bash start_celery.sh")
    else:
        print("Error: start_celery.sh not found!")
        success = False

    if not success:
        print("Startup script failed. If you are in a sandbox, this is expected due to missing /var/www paths.")

    # 3. Wait for services to spin up
    print("\n[Step 3] Waiting 15 seconds for services to initialize...")
    time.sleep(15)

    # 4. Run Diagnostic
    print("\n[Step 4] Verifying System Health...")
    if os.path.exists("Diagnostics/system_health_report.py"):
        run_command("python3 Diagnostics/system_health_report.py")
    else:
        print("Diagnostic script not found!")

if __name__ == "__main__":
    main()
