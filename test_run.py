# test_run.py
import os
from keepa_deals.Keepa_Deals import run_keepa_script
from dotenv import load_dotenv

print("--- Triggering Test Scan ---")
load_dotenv()
KEEPA_API_KEY = os.getenv("KEEPA_API_KEY")

if not KEEPA_API_KEY:
    print("FATAL: KEEPA_API_KEY not found in .env file.")
else:
    print("API key loaded. Sending task to Celery worker...")
    run_keepa_script.delay(api_key=KEEPA_API_KEY, deal_limit=20)
    print("Task 'run_keepa_script' has been sent to the queue.")
    print("Monitor celery.log for progress.")

print("--- Script Finished ---")