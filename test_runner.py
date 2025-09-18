# test_runner.py
import logging
from keepa_deals.Keepa_Deals import run_keepa_script

# Configure logging to see the output
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# The API key from the prompt
api_key = "bg9037ndr2jrlore45acr8a3gustia0tusdfk5e54g1le917nspnk9jiktp7b08b"

if __name__ == "__main__":
    print("Starting test run of the Keepa script with a smaller deal limit...")
    # Call the task's run() method directly for a synchronous execution.
    # Use a smaller deal_limit to avoid timeouts in the test environment.
    run_keepa_script.run(api_key=api_key, no_cache=True, deal_limit=50)
    print("Test run finished.")
