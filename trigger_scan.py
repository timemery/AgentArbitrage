from keepa_deals.Keepa_Deals import run_keepa_script
import os

# The API key from the problem description
api_key = "bg9037ndr2jrlore45acr8a3gustia0tusdfk5e54g1le917nspnk9jiktp7b08b"

# Set the output directory
output_dir = os.path.abspath("data")

# Trigger the task
print("Triggering Celery task...")
run_keepa_script.delay(api_key=api_key, no_cache=True, output_dir=output_dir, deal_limit=3)
print("Task triggered.")