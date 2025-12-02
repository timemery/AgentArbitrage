import time
import math
import logging

logger = logging.getLogger(__name__)

class TokenManager:
    """
    Manages Keepa API tokens, rate limiting, and refills.
    """
    def __init__(self, api_key):
        self.api_key = api_key
        
        # Constants
        self.REFILL_RATE_PER_MINUTE = 5
        self.MIN_TIME_BETWEEN_CALLS_SECONDS = 60
        
        # State variables
        self.tokens = 100 # Start with a reasonable guess, will be corrected on first response
        self.max_tokens = 300
        self.last_api_call_timestamp = time.time() - self.MIN_TIME_BETWEEN_CALLS_SECONDS
        self.last_refill_timestamp = time.time()
        self.proactive_refill_threshold = 100 # If a call needs more than we have and we have less than this, wait.


        logger.info("TokenManager initialized without a blocking API call.")

    def _simulate_refill(self):
        """
        Calculates and adds tokens that have been refilled since the last check.
        This is a simulation based on time elapsed.
        """
        now = time.time()
        seconds_elapsed = now - self.last_refill_timestamp
        
        if seconds_elapsed > 0:
            # Refill rate is per minute, so calculate per second and multiply.
            refill_amount = (self.REFILL_RATE_PER_MINUTE / 60) * seconds_elapsed
            
            if refill_amount > 0:
                self.tokens = min(self.max_tokens, self.tokens + refill_amount)
                self.last_refill_timestamp = now
                logger.debug(f"Simulated refill of {refill_amount:.2f} tokens. Current tokens: {self.tokens:.2f}")

    def has_enough_tokens(self, estimated_cost):
        """
        Checks if there are enough tokens for a call without waiting.
        Also triggers a refill check.
        """
        self._simulate_refill()
        return self.tokens >= estimated_cost

    def request_permission_for_call(self, estimated_cost, reason=""):
        """
        Checks if enough tokens are available. If not, it might wait.
        A 'controlled deficit' is allowed, but if it gets too large,
        this function will block and wait for a full refill.
        """
        # First, ensure minimum time has passed since the last actual API call.
        now = time.time()
        time_since_last_call = now - self.last_api_call_timestamp
        if time_since_last_call < self.MIN_TIME_BETWEEN_CALLS_SECONDS:
            wait_duration = self.MIN_TIME_BETWEEN_CALLS_SECONDS - time_since_last_call
            logger.info(f"Rate limit: Pausing for {wait_duration:.2f} seconds before '{reason}'.")
            time.sleep(wait_duration)

        # Simulate token refill that occurred during the pause or since the last check
        self._simulate_refill()

        # Proactive long wait to prevent deep deficit
        if self.tokens < estimated_cost and self.tokens < self.proactive_refill_threshold:
            tokens_needed_for_max = self.max_tokens - self.tokens
            # Calculate wait time in seconds to reach max tokens
            wait_time_seconds = (tokens_needed_for_max / self.REFILL_RATE_PER_MINUTE) * 60 if self.REFILL_RATE_PER_MINUTE > 0 else 3600

            # Ensure we wait at least a minute to avoid rapid loops on miscalculation
            wait_time_seconds = max(60, wait_time_seconds)

            logger.warning(
                f"Insufficient tokens for '{reason}' (Have: {self.tokens:.2f}, Need: {estimated_cost}). "
                f"Proactively waiting for {wait_time_seconds:.0f} seconds to perform a full refill."
            )
            time.sleep(wait_time_seconds)
            self.sync_tokens() # Authoritatively re-sync after a long wait

        # Standard wait loop if still not enough tokens
        while self.get_tokens_left() < estimated_cost:
            # Wait for one minute, then check again
            logger.info(f"Waiting for 60s for tokens to refill for: {reason}")
            time.sleep(60)
            self._simulate_refill()

        logger.info(f"Permission granted for API call '{reason}'. Estimated cost: {estimated_cost}. Current tokens: {self.tokens:.2f}")


    def sync_tokens(self):
        """
        Authoritatively fetches the current token status from the Keepa API
        and updates the internal state.
        """
        from .keepa_api import get_token_status
        logger.info("Performing authoritative token sync with Keepa API...")
        status_data = get_token_status(self.api_key)
        if status_data and 'tokensLeft' in status_data:
            self._sync_tokens_from_response(status_data['tokensLeft'])
        else:
            logger.error("Failed to sync tokens. API did not return valid token data.")

    def _sync_tokens_from_response(self, tokens_left_from_api):
        """
        Authoritatively sets the token count from a provided API response value.
        """
        old_token_count = self.tokens
        self.tokens = float(tokens_left_from_api)
        # Reset the refill timer to now, since the API's value is the most current truth.
        self.last_refill_timestamp = time.time()
        logger.info(
            f"Token count authoritatively synced from API response. "
            f"Previous estimate: {old_token_count:.2f}, New value: {self.tokens:.2f}"
        )

    def update_after_call(self, tokens_left_from_api):
        """
        Updates the token count and timestamp after an API call using the authoritative response.
        """
        self.last_api_call_timestamp = time.time()
        if tokens_left_from_api is not None:
             self._sync_tokens_from_response(tokens_left_from_api)
        else:
            logger.warning("API response did not include tokensLeft. Cannot sync token count.")

    def get_tokens_left(self):
        """Returns the current token count after simulating a refill."""
        self._simulate_refill()
        return self.tokens
