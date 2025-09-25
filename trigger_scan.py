import os
from dotenv import load_dotenv
from keepa_deals.Keepa_Deals import run_keepa_script

# Load environment variables from .env file
load_dotenv()

# Get the API key from the environment
keepa_api_key = os.getenv("KEEPA_API_KEY")

if keepa_api_key:
    # Send the task to the Celery worker with the API key and a deal limit
    run_keepa_script.delay(api_key=keepa_api_key, deal_limit=3)
    print("Scan task with a limit of 3 deals has been sent to the Celery worker.")
else:
    print("Error: KEEPA_API_KEY not found in .env file.")