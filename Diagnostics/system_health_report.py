#!/usr/bin/env python3
import os
import sys
import json
import sqlite3
import subprocess
import requests
import redis
import time
from datetime import datetime, timezone
from dotenv import load_dotenv

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Load environment variables
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# --- Configuration ---
DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'deals.db')
WORKER_LOG = os.path.join(os.path.dirname(__file__), '..', 'celery_worker.log')
BEAT_LOG = os.path.join(os.path.dirname(__file__), '..', 'celery_beat.log')
MONITOR_LOG = os.path.join(os.path.dirname(__file__), '..', 'celery_monitor.log')
REPORT_FILE = os.path.join(os.path.dirname(__file__), 'health_report.json')

# Colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'
BOLD = '\033[1m'

class HealthChecker:
    def __init__(self):
        self.results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "environment": {},
            "infrastructure": {},
            "database": {},
            "api_connectivity": {},
            "application_state": {},
            "logs": {}
        }
        self.overall_status = "PASS"

    def log_result(self, category, check, status, message=""):
        self.results[category][check] = {"status": status, "message": message}
        icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        color = GREEN if status == "PASS" else RED if status == "FAIL" else YELLOW
        print(f"{icon} {color}{check:<30}: {status} {RESET}- {message}")
        if status == "FAIL":
            self.overall_status = "FAIL"
        elif status == "WARN" and self.overall_status != "FAIL":
            self.overall_status = "WARN"

    def check_environment(self):
        print(f"\n{BOLD}--- Environment Checks ---{RESET}")

        # Check .env
        if os.path.exists(os.path.join(os.path.dirname(__file__), '..', '.env')):
            self.log_result("environment", ".env File", "PASS", "Found")
        else:
            self.log_result("environment", ".env File", "FAIL", "Missing")

        # Check Python Version
        py_ver = sys.version.split()[0]
        self.log_result("environment", "Python Version", "PASS", py_ver)

        # Check API Keys existence
        keys = ["KEEPA_API_KEY", "XAI_TOKEN", "SP_API_CLIENT_ID"]
        for key in keys:
            if os.getenv(key):
                mask = os.getenv(key)[:4] + "****"
                self.log_result("environment", key, "PASS", f"Present ({mask})")
            else:
                self.log_result("environment", key, "FAIL", "Missing")

        # Disk Space (Root)
        try:
            shutil = __import__('shutil')
            total, used, free = shutil.disk_usage("/")
            free_gb = free // (2**30)
            status = "PASS" if free_gb > 1 else "WARN"
            self.log_result("environment", "Disk Space", status, f"{free_gb} GB Free")
        except Exception as e:
            self.log_result("environment", "Disk Space", "WARN", str(e))

    def check_infrastructure(self):
        print(f"\n{BOLD}--- Infrastructure Checks ---{RESET}")

        # Redis
        try:
            r = redis.Redis.from_url('redis://127.0.0.1:6379/0', socket_connect_timeout=2)
            r.ping()
            self.log_result("infrastructure", "Redis Connectivity", "PASS", "Connected")
        except Exception as e:
            self.log_result("infrastructure", "Redis Connectivity", "FAIL", str(e))

        # Celery Processes
        try:
            res = subprocess.run(['pgrep', '-af', 'celery'], capture_output=True, text=True)
            procs = res.stdout

            if 'celery worker' in procs or 'celery@' in procs:
                self.log_result("infrastructure", "Celery Worker", "PASS", "Running")
            else:
                self.log_result("infrastructure", "Celery Worker", "FAIL", "Not Found")

            if 'celery beat' in procs:
                self.log_result("infrastructure", "Celery Beat", "PASS", "Running")
            else:
                self.log_result("infrastructure", "Celery Beat", "FAIL", "Not Found")

            # Check Monitor Process
            monitor_res = subprocess.run(['pgrep', '-f', 'monitor_and_restart'], capture_output=True, text=True)
            if monitor_res.stdout.strip():
                self.log_result("infrastructure", "Monitor Process", "PASS", "Running")
            else:
                self.log_result("infrastructure", "Monitor Process", "FAIL", "Not Found")

        except Exception as e:
            self.log_result("infrastructure", "Process Check", "FAIL", str(e))

    def check_database(self):
        print(f"\n{BOLD}--- Database Checks ---{RESET}")

        if not os.path.exists(DB_PATH):
            self.log_result("database", "DB File Existence", "FAIL", f"Not found at {DB_PATH}")
            return

        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            # Integrity Check
            cursor.execute("PRAGMA integrity_check")
            integrity = cursor.fetchone()[0]
            if integrity == "ok":
                self.log_result("database", "Integrity Check", "PASS", "OK")
            else:
                self.log_result("database", "Integrity Check", "FAIL", str(integrity))

            # Table Counts
            tables = ["deals", "system_state", "user_credentials", "user_restrictions"]
            for table in tables:
                try:
                    cursor.execute(f"SELECT count(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    self.log_result("database", f"Table: {table}", "PASS", f"{count} rows")
                except sqlite3.OperationalError:
                    self.log_result("database", f"Table: {table}", "WARN", "Missing")

            conn.close()
        except Exception as e:
            self.log_result("database", "Connection", "FAIL", str(e))

    def check_api_connectivity(self):
        print(f"\n{BOLD}--- API Connectivity ---{RESET}")

        # Keepa
        try:
            # Import here to avoid crash if env is bad
            from keepa_deals.token_manager import TokenManager
            api_key = os.getenv("KEEPA_API_KEY")
            if api_key:
                tm = TokenManager(api_key)
                tm.sync_tokens()
                self.log_result("api_connectivity", "Keepa API", "PASS", f"Tokens: {tm.tokens}, Rate: {tm.REFILL_RATE_PER_MINUTE}")
            else:
                self.log_result("api_connectivity", "Keepa API", "FAIL", "Key Missing")
        except Exception as e:
            self.log_result("api_connectivity", "Keepa API", "FAIL", str(e))

        # xAI
        try:
            xai_key = os.getenv("XAI_TOKEN")
            if xai_key:
                payload = {
                    "messages": [{"role": "user", "content": "Hello"}],
                    "model": "grok-4-fast-reasoning",
                    "max_tokens": 5
                }
                headers = {"Authorization": f"Bearer {xai_key}", "Content-Type": "application/json"}
                resp = requests.post("https://api.x.ai/v1/chat/completions", json=payload, headers=headers, timeout=10)
                if resp.status_code == 200:
                    self.log_result("api_connectivity", "xAI API", "PASS", "Connected")
                else:
                    self.log_result("api_connectivity", "xAI API", "FAIL", f"Status {resp.status_code}: {resp.text[:50]}...")
            else:
                self.log_result("api_connectivity", "xAI API", "FAIL", "Key Missing")
        except Exception as e:
            self.log_result("api_connectivity", "xAI API", "FAIL", str(e))

    def check_application_state(self):
        print(f"\n{BOLD}--- Application State ---{RESET}")

        # DB State
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            try:
                cursor.execute("SELECT key, value FROM system_state")
                rows = dict(cursor.fetchall())

                bf_page = rows.get('backfill_page', 'N/A')
                watermark = rows.get('watermark_iso', 'N/A')

                self.log_result("application_state", "Backfill Page", "PASS" if bf_page != 'N/A' else "WARN", bf_page)
                self.log_result("application_state", "Watermark", "PASS" if watermark != 'N/A' else "WARN", watermark)
            except:
                self.log_result("application_state", "System State", "FAIL", "Could not read system_state")

            conn.close()
        except:
            pass

        # Locks
        try:
            r = redis.Redis.from_url('redis://127.0.0.1:6379/0')
            lock_key = "backfill_deals_lock"
            if r.exists(lock_key):
                ttl = r.ttl(lock_key)
                self.log_result("application_state", "Backfill Lock", "WARN", f"Active (TTL: {ttl}s)")
            else:
                self.log_result("application_state", "Backfill Lock", "PASS", "Free")
        except:
            pass

    def check_logs(self):
        print(f"\n{BOLD}--- Log Analysis ---{RESET}")

        # 1. Check Monitor Log (Priority if infrastructure failed)
        if os.path.exists(MONITOR_LOG):
            try:
                with open(MONITOR_LOG, 'r') as f:
                    lines = f.readlines()[-20:] # Last 20 lines

                # Check for specific failure keywords
                monitor_errors = 0
                for line in lines:
                    if "CRITICAL" in line or "Failed" in line or "Aborting" in line:
                        monitor_errors += 1

                status = "WARN" if monitor_errors > 0 else "PASS"
                self.log_result("logs", "Monitor Log", status, f"{monitor_errors} critical events")

                # If infrastructure is failing, print the log tail
                if self.results["infrastructure"].get("Celery Worker", {}).get("status") == "FAIL":
                    print(f"\n{YELLOW}--- Tail of Monitor Log ---{RESET}")
                    for line in lines:
                        print(line.strip())
                    print(f"{YELLOW}-----------------------------{RESET}\n")

            except Exception as e:
                self.log_result("logs", "Monitor Log Read", "FAIL", str(e))
        else:
            self.log_result("logs", "Monitor Log", "WARN", "File not found")

        # 2. Check Worker Log
        if os.path.exists(WORKER_LOG):
            try:
                with open(WORKER_LOG, 'r') as f:
                    lines = f.readlines()[-50:] # Last 50 lines

                errors = 0
                for line in lines:
                    if "ERROR" in line or "CRITICAL" in line or "Traceback" in line:
                        errors += 1

                if errors == 0:
                    self.log_result("logs", "Recent Errors", "PASS", "None in last 50 lines")
                else:
                    self.log_result("logs", "Recent Errors", "WARN", f"{errors} errors in last 50 lines")

                # If infrastructure is failing, print the log tail
                if self.results["infrastructure"].get("Celery Worker", {}).get("status") == "FAIL":
                    print(f"\n{YELLOW}--- Tail of Worker Log ---{RESET}")
                    for line in lines[-20:]:
                        print(line.strip())
                    print(f"{YELLOW}-----------------------------{RESET}\n")

            except Exception as e:
                self.log_result("logs", "Log Read", "FAIL", str(e))
        else:
            self.log_result("logs", "Worker Log", "WARN", "File not found")

        # 3. Check Beat Log (If infrastructure failing)
        if self.results["infrastructure"].get("Celery Beat", {}).get("status") == "FAIL":
            if os.path.exists(BEAT_LOG):
                try:
                    with open(BEAT_LOG, 'r') as f:
                        lines = f.readlines()[-20:]
                    print(f"\n{YELLOW}--- Tail of Beat Log ---{RESET}")
                    for line in lines:
                        print(line.strip())
                    print(f"{YELLOW}-----------------------------{RESET}\n")
                except Exception as e:
                    print(f"Could not read Beat Log: {e}")
            else:
                print(f"\n{YELLOW}--- Tail of Beat Log ---{RESET}")
                print("File not found")
                print(f"{YELLOW}-----------------------------{RESET}\n")

    def run(self):
        print(f"{BOLD}Starting System Health Diagnostic...{RESET}")
        self.check_environment()
        self.check_infrastructure()
        self.check_database()
        self.check_api_connectivity()
        self.check_application_state()
        self.check_logs()

        print(f"\n{BOLD}--- Summary ---{RESET}")
        color = GREEN if self.overall_status == "PASS" else RED if self.overall_status == "FAIL" else YELLOW
        print(f"Overall Status: {color}{self.overall_status}{RESET}")

        with open(REPORT_FILE, 'w') as f:
            json.dump(self.results, f, indent=4)
        print(f"Report saved to {REPORT_FILE}")

if __name__ == "__main__":
    checker = HealthChecker()
    checker.run()
