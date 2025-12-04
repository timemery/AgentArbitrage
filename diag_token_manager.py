
import os
import logging
from dotenv import load_dotenv
from keepa_deals.token_manager import TokenManager

# Set up basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def diagnose_token_manager():
    """
    Diagnoses the TokenManager initialization and permission logic.
    """
    logging.info("--- Starting Token Manager Diagnostic Script ---")

    # --- 1. Load Environment Variables ---
    try:
        load_dotenv()
        api_key = os.getenv("KEEPA_API_KEY")
        if not api_key:
            logging.error("KEEPA_API_KEY not found in environment. Please check your .env file.")
            return
        logging.info("Successfully loaded KEEPA_API_KEY from .env file.")
    except Exception as e:
        logging.error(f"Failed to load environment variables: {e}")
        return

    # --- 2. Instantiate TokenManager ---
    try:
        logging.info("Instantiating TokenManager...")
        token_manager = TokenManager(api_key)
        logging.info(f"TokenManager instantiated. Initial token count (before sync): {token_manager.tokens}")
    except Exception as e:
        logging.error(f"Failed to instantiate TokenManager: {e}")
        return

    # --- 3. Synchronize Tokens with Keepa API ---
    try:
        logging.info("Attempting to synchronize tokens with Keepa API via sync_tokens()...")
        tokens_left, _ = token_manager.sync_tokens()
        if tokens_left is not None:
            logging.info(f"[SUCCESS] sync_tokens() completed. API reports {tokens_left} tokens remaining.")
            logging.info(f"Internal TokenManager count is now: {token_manager.tokens}")
        else:
            logging.error("[FAILURE] sync_tokens() failed to get a response from the API.")
            return
    except Exception as e:
        logging.error(f"An exception occurred during sync_tokens(): {e}", exc_info=True)
        return

    # --- 4. Simulate a Request for a Batch of 2 ASINs ---
    try:
        # This cost is based on the logic in backfiller.py
        # COST_PER_PRODUCT is a conservative estimate of API cost per ASIN.
        COST_PER_PRODUCT = 12
        num_asins = 2
        estimated_cost = num_asins * COST_PER_PRODUCT

        logging.info(f"\nSimulating a request for {num_asins} ASINs...")
        logging.info(f"Using an estimated cost of {COST_PER_PRODUCT} per ASIN.")
        logging.info(f"Total estimated cost for this call: {estimated_cost} tokens.")
        logging.info(f"Current token balance before request: {token_manager.tokens}")

        logging.info("Calling request_permission_for_call()...")
        permission_granted = token_manager.request_permission_for_call(estimated_cost, "Test Call")

        if permission_granted:
            logging.info("[RESULT] Permission GRANTED. The script would now proceed with an API call.")
        else:
            logging.warning("[RESULT] Permission DENIED. The script would pause. This is the source of the stall.")

    except Exception as e:
        logging.error(f"An exception occurred during request_permission_for_call(): {e}", exc_info=True)

    logging.info("--- Diagnostic Script Finished ---")

if __name__ == "__main__":
    diagnose_token_manager()
