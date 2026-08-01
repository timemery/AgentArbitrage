#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil
import sqlite3
from datetime import datetime

# --- Formatting Helpers ---
def print_header(title):
    print("\n" + "=" * 80)
    print(f" {title.upper()} ".center(80, "="))
    print("=" * 80)

def print_sub_header(title):
    print(f"\n--- {title} ---")

def print_result(label, status, details=""):
    if status == "OK":
        print(f"  [ \033[92mPASS\033[0m ] {label}")
    elif status == "WARNING":
        print(f"  [ \033[93mWARN\033[0m ] {label}")
        if details:
            print(f"           👉 {details}")
    else:
        print(f"  [ \033[91mFAIL\033[0m ] {label}")
        if details:
            print(f"           👉 \033[91m{details}\033[0m")

# --- Command Runner ---
def run_command(cmd, shell=False):
    try:
        res = subprocess.run(cmd, shell=shell, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        return res.returncode, res.stdout.strip(), res.stderr.strip()
    except Exception as e:
        return -1, "", str(e)

# --- Core Diagnostic Suite ---
def main():
    print_header("AgentArbitrage VPS Outage Diagnostics")
    print(f"Execution Time (UTC): {datetime.utcnow().isoformat()}")
    print(f"Run as User: {run_command(['whoami'])[1]}")
    print(f"Python Executable: {sys.executable}")

    # -------------------------------------------------------------
    # 1. Apache Service Check
    # -------------------------------------------------------------
    print_header("1. Apache Web Server Checks")

    apache_service_exists = shutil.which("apache2") is not None
    if not apache_service_exists:
        print_result("Apache installed", "FAIL", "Apache executable 'apache2' not found on the system path.")
        sys.exit(1)
    else:
        print_result("Apache installed", "OK")

    code, out, err = run_command(["sudo", "systemctl", "is-active", "apache2"])
    if out == "active":
        print_result("Apache status", "OK", "apache2 service is ACTIVE and running.")
    else:
        print_result("Apache status", "FAIL", f"apache2 service is NOT active. Status: {out} | Error: {err}")

    # Check if Apache config test passes
    code, out, err = run_command(["sudo", "apache2ctl", "configtest"])
    if code == 0:
        print_result("Apache configuration test", "OK", "Config test passed cleanly.")
    else:
        print_result("Apache configuration test", "FAIL", f"Config syntax error: {out} {err}")

    # Check port bindings for 80/443
    print_sub_header("Port Bindings (80 & 443)")
    code, out, err = run_command("sudo ss -tulnp | grep -E ':80|:443'", shell=True)
    if out:
        print("Active Bindings:")
        for line in out.splitlines():
            print(f"  {line}")
        print_result("Port bindings active", "OK")
    else:
        print_result("Port bindings active", "FAIL", "No services bound to Port 80 or 443. Apache might not be listening.")

    # Local Curl Response Checks
    print_sub_header("Local HTTP/HTTPS Response Checks")
    code, out, err = run_command(["curl", "-I", "-k", "https://127.0.0.1/"])
    if code == 0:
        response_line = out.splitlines()[0] if out else ""
        print_result("Local HTTPS connection (https://127.0.0.1/)", "OK", f"Response: {response_line}")
        if "302" in response_line or "200" in response_line:
            print("\n  \033[92m🚀 LOCAL SELF-TEST SUCCESSFUL! The AgentArbitrage site is UP, responding, and running perfectly on the server.\033[0m")
            print("  If you still see ERR_CONNECTION_CLOSED in your browser, it is due to a client-side firewall, DNS cache, browser cache, or Cloudflare/CDN issue.\n")
    else:
        print_result("Local HTTPS connection (https://127.0.0.1/)", "FAIL", f"Could not connect locally to Flask/Apache: {err}")

    # -------------------------------------------------------------
    # 2. SSL / HTTPS Certificates Checks
    # -------------------------------------------------------------
    print_header("2. SSL & HTTPS Certificate Checks")
    cert_path = "/etc/letsencrypt/live/agentarbitrage.co/fullchain.pem"
    key_path = "/etc/letsencrypt/live/agentarbitrage.co/privkey.pem"

    if os.path.exists(cert_path):
        print_result("SSL Certificate File found", "OK", f"Found certificate at {cert_path}")
        # Check expiry
        code, out, err = run_command(f"sudo openssl x509 -enddate -noout -in {cert_path}", shell=True)
        if code == 0:
            print_result("SSL Expiry Date", "OK", out)
            # Check if expired
            try:
                expiry_str = out.replace("notAfter=", "").strip()
                expiry_dt = datetime.strptime(expiry_str, "%b %d %H:%M:%S %Y %Z")
                if expiry_dt < datetime.utcnow():
                    print_result("SSL Validity", "FAIL", f"The SSL certificate has EXPIRED on {expiry_str}!")
                else:
                    days_left = (expiry_dt - datetime.utcnow()).days
                    print_result("SSL Validity", "OK", f"Certificate valid for another {days_left} days.")
            except Exception as ex:
                print_result("Parse SSL date", "WARNING", f"Could not parse certificate date: {ex}")
        else:
            print_result("SSL Expiry Check", "FAIL", f"Failed to inspect cert: {err}")
    else:
        print_result("SSL Certificate File", "FAIL", f"SSL certificate NOT found at {cert_path}!")

    if os.path.exists(key_path):
        print_result("SSL Private Key File found", "OK", f"Found private key at {key_path}")
    else:
        print_result("SSL Private Key File", "FAIL", f"SSL private key NOT found at {key_path}!")

    # -------------------------------------------------------------
    # 3. Apache Config Location & Directive Integrity
    # -------------------------------------------------------------
    print_header("3. Apache Virtual Host & WSGI Directive Checks")
    active_conf_path = "/etc/apache2/sites-enabled/agentarbitrage.conf"
    if not os.path.exists(active_conf_path):
        # Fallback search in sites-available
        active_conf_path = "/etc/apache2/sites-available/agentarbitrage.conf"

    if os.path.exists(active_conf_path):
        print_result("Apache site configuration found", "OK", f"Found virtual host at {active_conf_path}")
        with open(active_conf_path, "r") as f:
            conf_content = f.read()

        if "WSGIApplicationGroup %{GLOBAL}" in conf_content:
            print_result("WSGIApplicationGroup directive", "OK", "Found 'WSGIApplicationGroup %{GLOBAL}' correctly configured.")
        else:
            print_result("WSGIApplicationGroup directive", "FAIL", "Missing 'WSGIApplicationGroup %{GLOBAL}'. C-extension modules like sqlite3 or numpy will deadlock inside sub-interpreters!")

        if "python-home=" in conf_content:
            print_result("python-home virtualenv definition", "OK", "Found virtual environment path definition.")
            # Extract python-home path
            match = re.search(r'python-home=([^\s]+)', conf_content)
            if match:
                venv_path = match.group(1)
                if os.path.exists(venv_path):
                    print_result("Virtual Environment path exists", "OK", f"Accessible at {venv_path}")
                else:
                    print_result("Virtual Environment path exists", "FAIL", f"Virtualenv path '{venv_path}' defined in Apache config does not exist!")
        else:
            print_result("python-home virtualenv definition", "WARNING", "No 'python-home=' path found in configuration.")
    else:
        print_result("Apache site configuration", "FAIL", "Virtual host config file 'agentarbitrage.conf' not found in Apache directory.")

    # -------------------------------------------------------------
    # 4. Redis and Celery Process Verification
    # -------------------------------------------------------------
    print_header("4. Redis & Celery Background Service Checks")

    # Redis Ping
    redis_ping_rc, redis_ping_out, redis_ping_err = run_command(["redis-cli", "ping"])
    if redis_ping_out == "PONG":
        print_result("Redis Server connection", "OK", "Redis responded with PONG.")
    else:
        print_result("Redis Server connection", "FAIL", f"Redis ping failed. Out: {redis_ping_out} | Err: {redis_ping_err}")

    # Check for Celery processes
    code, out, err = run_command("ps aux | grep -E 'celery worker|celery beat|monitor_and_restart' | grep -v grep", shell=True)
    if out:
        print("Active Background Processes:")
        for line in out.splitlines():
            print(f"  {line}")
        print_result("Celery / Monitor processes", "OK")
    else:
        print_result("Celery / Monitor processes", "WARNING", "No active Celery workers, beat schedulers, or resiliency monitor processes detected.")

    # -------------------------------------------------------------
    # 5. Database Integrity and Permissions Check
    # -------------------------------------------------------------
    print_header("5. Database Permissions & SQLite Integrity Checks")
    db_path = "deals.db"
    if os.path.exists(db_path):
        print_result("deals.db file exists", "OK", f"Database size: {os.path.getsize(db_path) / 1024 / 1024:.2f} MB")

        # Test sqlite3 read
        try:
            conn = sqlite3.connect(db_path, timeout=5)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            print_result("SQLite database connection", "OK", f"Successfully read master. Tables found: {', '.join(tables)}")

            # Simple query on deals count
            if 'deals' in tables:
                cursor.execute("SELECT COUNT(*) FROM deals")
                count = cursor.fetchone()[0]
                print_result("Deals table query", "OK", f"Found {count} records in 'deals' table.")
            else:
                print_result("Deals table exists", "FAIL", "The 'deals' table does not exist in the database.")
            conn.close()
        except sqlite3.Error as e:
            print_result("SQLite database connection", "FAIL", f"SQLite read failed: {e}")

        # Check permissions for www-data
        stat_info = os.stat(db_path)
        uid, gid = stat_info.st_uid, stat_info.st_gid
        # Get owners
        import pwd, grp
        try:
            owner_name = pwd.getpwuid(uid).pw_name
            group_name = grp.getgrgid(gid).gr_name
            print_result("deals.db Owner/Group", "OK", f"Owner: {owner_name} | Group: {group_name}")
            if owner_name != "www-data":
                print_result("deals.db Owner", "WARNING", f"db file owned by '{owner_name}', NOT 'www-data'. If celery or apache runs as www-data, they might fail to write!")
        except Exception:
            print_result("deals.db Owner/Group", "WARNING", f"UID: {uid} | GID: {gid}")
    else:
        print_result("deals.db file exists", "FAIL", "Database 'deals.db' not found in repo root directory.")

    # -------------------------------------------------------------
    # 6. Apache Error Log Inspection (THE SMOKING GUN)
    # -------------------------------------------------------------
    print_header("6. Apache Error Log Investigation (Last 20 Entries)")
    error_log_path = "/var/log/apache2/agentarbitrage_error.log"
    global_error_log_path = "/var/log/apache2/error.log"

    log_loaded = False

    if os.path.exists(error_log_path):
        print_sub_header(f"Inspecting Custom Error Log: {error_log_path}")
        code, out, err = run_command(["sudo", "tail", "-n", "20", error_log_path])
        if out:
            print(out)
            log_loaded = True
        else:
            print("Log file is empty.")
    else:
        print_result(f"Custom error log '{error_log_path}'", "WARNING", "File does not exist.")

    if os.path.exists(global_error_log_path):
        print_sub_header(f"Inspecting Global Error Log: {global_error_log_path}")
        code, out, err = run_command(["sudo", "tail", "-n", "20", global_error_log_path])
        if out:
            print(out)
            log_loaded = True
        else:
            print("Log file is empty.")
    else:
        print_result(f"Global error log '{global_error_log_path}'", "WARNING", "File does not exist.")

    if not log_loaded:
        print_result("Apache Error Logs", "FAIL", "Could not locate or read any Apache error log files. Please make sure you have sudo privileges.")

    print_header("Diagnostic Execution Completed")
    print("If you see any FAILED checks above, please address them to restore your site uptime.")

if __name__ == "__main__":
    import re
    main()
