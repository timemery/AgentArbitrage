# keepa_deals/token_manager.py
import time
import math
import logging
from .keepa_api import get_token_status

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
        self.tokens = 0
        self.max_tokens = 300 # A default, will be updated from API if possible
        self.last_api_call_timestamp = 0
        self.last_refill_timestamp = time.time()

        # Initialize token count from Keepa
        self._initialize_tokens()

    def _initialize_tokens(self):
        """
        Makes an initial call to the Keepa API to get the current token count.
        """
        logger.info("Initializing TokenManager: Fetching initial token status...")
        status = get_token_status(self.api_key)
        if status and 'tokensLeft' in status:
            self.tokens = status['tokensLeft']
            # Some subscriptions might have different max tokens, but API doesn't expose it directly.
            # We can infer it if the current tokens are high.
            if self.tokens > self.max_tokens:
                self.max_tokens = self.tokens
            logger.info(f"TokenManager initialized. Starting tokens: {self.tokens}")
        else:
            logger.error("Could not fetch initial token status. Assuming 0 tokens.")
            self.tokens = 0

        self.last_api_call_timestamp = time.time() - self.MIN_TIME_BETWEEN_CALLS_SECONDS # Allow first call immediately

    def _refill_tokens(self):
        """
        Calculates and adds tokens that have been refilled since the last check.
        """
        now = time.time()
        seconds_elapsed = now - self.last_refill_timestamp

        if seconds_elapsed > 0:
            refill_amount = (seconds_elapsed / 60) * self.REFILL_RATE_PER_MINUTE

            if refill_amount > 0:
                self.tokens = min(self.max_tokens, self.tokens + refill_amount)
                self.last_refill_timestamp = now
                logger.debug(f"Refilled {refill_amount:.2f} tokens. Current tokens: {self.tokens:.2f}")

    def request_permission_for_call(self, estimated_cost):
        """
        Checks if an API call can be made, waits if necessary.
        This is the main public method for controlling API access.
        """
        # 1. Enforce time-based rate limit
        now = time.time()
        time_since_last_call = now - self.last_api_call_timestamp
        if time_since_last_call < self.MIN_TIME_BETWEEN_CALLS_SECONDS:
            wait_duration = self.MIN_TIME_BETWEEN_CALLS_SECONDS - time_since_last_call
            logger.info(f"Rate limit: Pausing for {wait_duration:.2f} seconds.")
            time.sleep(wait_duration)

        # 2. Update token count with any refills that occurred
        self._refill_tokens()

        # 3. Check if we have enough tokens and wait if we don't
        if self.tokens < estimated_cost:
            tokens_needed = estimated_cost - self.tokens
            if self.REFILL_RATE_PER_MINUTE > 0:
                # Calculate the minimum time required to get enough tokens
                wait_time_seconds = math.ceil((tokens_needed / self.REFILL_RATE_PER_MINUTE) * 60)
                logger.warning(
                    f"Insufficient tokens. Have: {self.tokens:.2f}, Need an estimated: {estimated_cost}. "
                    f"Waiting for {wait_time_seconds} seconds to refill."
                )
                time.sleep(wait_time_seconds)
                # Refill tokens again after waiting
                self._refill_tokens()
            else:
                # This case should not happen with a positive refill rate, but as a fallback.
                logger.error("Zero refill rate, cannot wait for tokens. Pausing for 15 minutes as a fallback.")
                time.sleep(900)
                self._refill_tokens()

        logger.info(f"Permission granted for API call. Estimated cost: {estimated_cost}. Current tokens: {self.tokens:.2f}")
        # The actual deduction will happen after the call, using update_from_response

    def update_from_response(self, api_response):
        """
        Updates the token count based on the actual 'tokensLeft' from the API response.
        This is the most reliable way to stay in sync.
        """
        self.last_api_call_timestamp = time.time() # Mark the time of the successful call

        if api_response and 'tokensLeft' in api_response:
            tokens_before = self.tokens
            self.tokens = api_response['tokensLeft']
            logger.info(f"Updated token count from API response. Before: {tokens_before:.2f}, After: {self.tokens}")
        else:
            logger.warning("Could not update token count from API response, 'tokensLeft' key not found.")
