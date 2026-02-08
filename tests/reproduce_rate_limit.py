import sys
import os
from dotenv import load_dotenv

# Ensure we can import from the root
sys.path.append(os.getcwd())

from keepa_deals.token_manager import TokenManager

def main():
    load_dotenv()
    api_key = os.getenv("KEEPA_API_KEY")
    if not api_key:
        print("KEEPA_API_KEY not set. Using dummy key for testing.")
        api_key = "dummy_key"

    tm = TokenManager(api_key)
    print(f"TokenManager initialized.")
    print(f"MIN_TIME_BETWEEN_CALLS_SECONDS: {tm.MIN_TIME_BETWEEN_CALLS_SECONDS}")

    if tm.MIN_TIME_BETWEEN_CALLS_SECONDS == 60:
        print("FAIL: Rate limit is set to 60 seconds (The Stall Bug).")
        sys.exit(1)
    else:
        print(f"PASS: Rate limit is {tm.MIN_TIME_BETWEEN_CALLS_SECONDS} seconds.")
        sys.exit(0)

if __name__ == "__main__":
    main()
