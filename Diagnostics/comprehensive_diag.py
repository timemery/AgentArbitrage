import os
import sys
import sqlite3
import subprocess
import json

# Ensure we can import modules from the root directory
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)

try:
    from wsgi_handler import app, api_deals, deal_count
    from flask import session
except ImportError:
    print("Warning: Could not import wsgi_handler. API verification will be skipped.")
    app = None

def find_file(filename, search_paths):
    for path in search_paths:
        full_path = os.path.join(path, filename)
        if os.path.exists(full_path):
            return full_path
    return None

def get_grep_count(pattern, filepath):
    """
    Uses subprocess to run grep -c for efficient counting in large files.
    Returns 0 if pattern not found or file error.
    """
    try:
        # -c counts matches
        result = subprocess.run(
            ['grep', '-c', pattern, filepath],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return int(result.stdout.strip())
        return 0
    except Exception:
        return 0

def run_diagnostic():
    # 1. Locate Files
    db_path = find_file("deals.db", [root_dir, os.path.join(root_dir, "data"), current_dir])
    log_path = find_file("celery_worker.log", [root_dir, current_dir])

    if not db_path:
        print("Error: deals.db not found.")
        return

    # 2. Log Statistics (Rejections)
    reason_no_offer = 0
    reason_list_at = 0
    reason_1yr_avg = 0
    rejected_count = 0

    if log_path:
        # Updated patterns for Smart Ingestor v3
        reason_peek = get_grep_count("Peek Rejected: ASIN", log_path)
        reason_no_offer = get_grep_count("No used offer found", log_path)
        # Matches both "missing" and "Profit is zero or negative" which effectively means List at/Cost failed
        reason_list_at_missing = get_grep_count("Excluding deal because 'List at' is missing", log_path)
        reason_profit_neg = get_grep_count("Profit is zero or negative", log_path)
        reason_list_at = reason_list_at_missing + reason_profit_neg

        reason_1yr_avg = get_grep_count("Excluding deal because '1yr. Avg.' is missing", log_path)
        rejected_count = reason_peek + reason_no_offer + reason_list_at + reason_1yr_avg
    else:
        print("Warning: celery_worker.log not found. Rejection stats will be 0.")

    # 3. Database Statistics
    raw_db_count = 0
    dashboard_visible_count = 0

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Raw Count
        cursor.execute("SELECT COUNT(*) FROM deals")
        raw_db_count = cursor.fetchone()[0]

        # Filtered Count (Dashboard Logic: Margin >= 0)
        # Note: We check if Margin column exists first to be safe, though it should.
        try:
            cursor.execute("SELECT COUNT(*) FROM deals WHERE Margin >= 0")
            dashboard_visible_count = cursor.fetchone()[0]
        except sqlite3.OperationalError:
            # Fallback if Margin column is missing (old DB schema)
            dashboard_visible_count = 0

        conn.close()
    except Exception as e:
        print(f"Error reading database: {e}")

    total_processed = raw_db_count + rejected_count
    rejection_rate = (rejected_count / total_processed * 100) if total_processed > 0 else 0.0

    # 4. Output: Deal Processing Stats
    print("========================================")
    print("          DEAL PROCESSING STATS         ")
    print("========================================")

    # Check Scheduler
    try:
        # Robust check using strict regex to avoid matching 'tail' commands
        res = subprocess.run(['pgrep', '-f', 'celery.*-A.*beat'], capture_output=True, text=True)
        scheduler_running = (res.returncode == 0)
    except Exception:
        scheduler_running = False

    if scheduler_running:
        print("[OK] Scheduled Upserter (Celery Beat) is RUNNING.")
    else:
        print("[WARNING] Scheduled Upserter (Celery Beat) is NOT RUNNING.")
    print("----------------------------------------")

    print(f"Total Processed:       {total_processed}")
    print(f"Successfully Saved:    {raw_db_count}")
    print(f"Dashboard Visible:     {dashboard_visible_count}  <-- (Margin >= 0%)")
    print(f"Total Rejected:        {rejected_count}")
    print(f"Rejection Rate:        {rejection_rate:.2f}%")
    print("")
    print("--- Rejection Breakdown ---")

    if rejected_count > 0:
        p_peek = (reason_peek / rejected_count * 100)
        p_no_offer = (reason_no_offer / rejected_count * 100)
        p_list_at = (reason_list_at / rejected_count * 100)
        p_1yr_avg = (reason_1yr_avg / rejected_count * 100)

        print(f"1. Peek Filter:         {reason_peek} ({p_peek:.1f}%)")
        print("   (Rejected early for bad ROI/Spread/Price)")
        print("")
        print(f"2. No Used Offer Found: {reason_no_offer} ({p_no_offer:.1f}%)")
        print("   (Deal has no valid used offers to analyze)")
        print("")
        print(f"3. Missing 'List at':   {reason_list_at} ({p_list_at:.1f}%)")
        print("   (Could not determine a safe listing price or AI rejected it)")
        print("")
        print(f"4. Missing '1yr Avg':   {reason_1yr_avg} ({p_1yr_avg:.1f}%)")
        print("   (Insufficient sales history/data points)")
    else:
        print("No rejections found (or log missing).")

    print("========================================")
    print("")

    # 5. API Verification
    if app:
        print("--- DATA INTEGRITY VERIFICATION ---")
        os.environ["DATABASE_URL"] = db_path

        # Verify Raw Count
        with app.test_request_context('/api/deal-count'):
            session['logged_in'] = True
            try:
                response = deal_count()
                if hasattr(response, 'get_json'):
                    data = response.get_json()
                else:
                    data = json.loads(response.data)

                api_raw_count = data.get('count', -1)

                if api_raw_count == raw_db_count:
                    print(f"[MATCH] DB Raw Count ({raw_db_count}) matches API Total ({api_raw_count})")
                else:
                    print(f"[MISMATCH] DB Raw Count ({raw_db_count}) != API Total ({api_raw_count})")
            except Exception as e:
                print(f"Error checking API raw count: {e}")

        # Verify Filtered Count
        with app.test_request_context('/api/deal-count?margin_gte=0'):
            session['logged_in'] = True
            try:
                response = deal_count()
                if hasattr(response, 'get_json'):
                    data = response.get_json()
                else:
                    data = json.loads(response.data)

                api_filtered_count = data.get('count', -1)

                if api_filtered_count == dashboard_visible_count:
                    print(f"[MATCH] DB Filtered Count ({dashboard_visible_count}) matches Dashboard API ({api_filtered_count})")
                else:
                    print(f"[MISMATCH] DB Filtered Count ({dashboard_visible_count}) != Dashboard API ({api_filtered_count})")
            except Exception as e:
                print(f"Error checking API filtered count: {e}")
        print("========================================")

if __name__ == "__main__":
    run_diagnostic()
