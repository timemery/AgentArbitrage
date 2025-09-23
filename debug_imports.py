import traceback
import sys
import os

# Ensure the current directory is in the path, just like mod_wsgi does.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

log_file = '/var/www/agentarbitrage/import_error.log'

print("--- Starting Import Debugger ---")
print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")

try:
    print("\nAttempting to import the Celery task from 'worker.py'...")
    from worker import run_keepa_script
    print("--> Import successful!")

    success_message = "Import was successful. The issue is likely not with the Python modules themselves."
    print(success_message)
    with open(log_file, 'w') as f:
        f.write(success_message)

except Exception as e:
    print(f"\n--> An error occurred during import: {e}")

    error_message = f"""
Import failed. This is the cause of the 500 Internal Server Error.

Traceback:
{traceback.format_exc()}
"""
    print(error_message)
    with open(log_file, 'w') as f:
        f.write(error_message)

print(f"\n--- Debugging complete. Results written to {log_file} ---")
