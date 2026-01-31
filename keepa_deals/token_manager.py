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
        self.MIN_TOKEN_THRESHOLD = 50 # New aggressive threshold

        # State variables
        self.tokens = 100 # Start with a reasonable guess, will be corrected on first response
        self.max_tokens = 300
        self.last_api_call_timestamp = time.time() - self.MIN_TIME_BETWEEN_CALLS_SECONDS
        self.last_refill_timestamp = time.time()

        logger.info("TokenManager initialized without a blocking API call.")

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

    def has_enough_tokens(self, estimated_cost):
        """
        Checks if there are enough tokens for a call without waiting.
        Also triggers a refill check.
        """
        self._refill_tokens()
        return self.tokens >= estimated_cost

    def request_permission_for_call(self, estimated_cost):
        """
        Checks if an API call can be made and waits if necessary. This method
        implements a "controlled deficit" strategy based on Keepa API behavior.

        Keepa API Rule: A call can be made as long as the token balance is positive.
        The call is allowed to drive the balance into a negative value.

        Our Strategy (Optimized):
        1.  **Hard Stop at Zero:** If tokens are <= 0, we must wait until they
            refill to a positive number.
        2.  **Aggressive Consumption:** If `current_tokens` > `MIN_TOKEN_THRESHOLD` (50),
            we allow the call immediately, even if it creates a deficit. We do NOT wait
            for a full bucket. This prevents "starvation" when an upserter task is
            simultaneously consuming the refill trickle.
        3.  **Smart Recovery:** If `current_tokens` drops below the threshold, we wait
            only until it recovers to (`threshold + buffer`), not `max_tokens`.
        """
        now = time.time()
        time_since_last_call = now - self.last_api_call_timestamp
        if time_since_last_call < self.MIN_TIME_BETWEEN_CALLS_SECONDS:
            wait_duration = self.MIN_TIME_BETWEEN_CALLS_SECONDS - time_since_last_call
            logger.info(f"Rate limit: Pausing for {wait_duration:.2f} seconds.")
            time.sleep(wait_duration)

        self._refill_tokens()

        wait_time_seconds = 0
        recovery_target = 0 # Target token count to reach before resuming

        # --- SYNC CHECK: Verify with API before deciding to wait ---
        # If our local count suggests a wait, we verify with the server first.
        # This fixes drift caused by concurrent workers.
        if self.tokens < self.MIN_TOKEN_THRESHOLD:
            logger.info(f"Local token count ({self.tokens:.2f}) is low. Syncing with Keepa API to verify...")
            self.sync_tokens()
            # Note: self.tokens is now updated to the authoritative value.

        # Scenario 1: Hard Stop (Zero or Negative)
        if self.tokens <= 0:
            # Must wait to get back to a safe positive balance (e.g., 10 tokens)
            recovery_target = 10
            tokens_needed = recovery_target - self.tokens
            wait_time_seconds = math.ceil((tokens_needed / self.REFILL_RATE_PER_MINUTE) * 60)
            logger.warning(
                f"Zero or negative tokens. Have: {self.tokens:.2f}. "
                f"Waiting for {wait_time_seconds} seconds to recover {tokens_needed:.2f} tokens at {self.REFILL_RATE_PER_MINUTE} tokens/min."
            )

        # Scenario 2: Below Threshold (Recovery Mode)
        elif self.tokens < self.MIN_TOKEN_THRESHOLD:
            # Wait until we are back comfortably above the threshold
            recovery_target = self.MIN_TOKEN_THRESHOLD + 5 # Buffer
            tokens_needed = recovery_target - self.tokens
            wait_time_seconds = math.ceil((tokens_needed / self.REFILL_RATE_PER_MINUTE) * 60)
            logger.warning(
                f"Low tokens (Below Threshold {self.MIN_TOKEN_THRESHOLD}). Have: {self.tokens:.2f}. "
                f"Waiting for {wait_time_seconds} seconds to recover to {recovery_target}."
            )

        # Scenario 3: Above Threshold (Proceed, even if deficit spending)
        else:
            # We have > 50 tokens. Even if estimated cost is 100, we proceed.
            # Keepa allows negative balance.
            pass

        if wait_time_seconds > 0:
            if self.REFILL_RATE_PER_MINUTE > 0:
                # Optimized Wait Loop: Smart Polling
                # Instead of sleeping the full duration blindly, we sleep in chunks and re-sync.
                # This prevents "Drift" where the app thinks it has fewer tokens than reality
                # (e.g., if the user upgraded their plan or another process stopped).
                # It also provides frequent log updates to the user.

                remaining_wait = wait_time_seconds

                while remaining_wait > 0:
                    # Sleep for 30s or the remaining time, whichever is smaller
                    sleep_chunk = min(remaining_wait, 30)
                    time.sleep(sleep_chunk)

                    # Update local estimate (linear refill fallback)
                    self._refill_tokens()

                    # Force sync every chunk (30s) to be authoritative.
                    # This call is free (0 tokens) and fixes the "Out of Sync" user perception.
                    self.sync_tokens()

                    # Check if we have recovered enough to proceed early
                    # Use the dynamically set recovery_target from above
                    if self.tokens >= recovery_target:
                         logger.info(f"Tokens recovered sufficiently ({self.tokens:.2f} >= {recovery_target}). Resuming operation early.")
                         break

                    # Re-calculate needed wait time based on NEW authoritative token count
                    tokens_needed = recovery_target - self.tokens
                    if tokens_needed <= 0:
                        break

                    new_wait_total = math.ceil((tokens_needed / self.REFILL_RATE_PER_MINUTE) * 60)

                    # We have already slept 'sleep_chunk'. The 'new_wait_total' is the estimated time FROM NOW
                    # required to reach the recovery target, based on the *current* rate and token count.
                    # We update 'remaining_wait' to this new authoritative estimate.
                    # This handles both rate increases (shortening wait) and rate decreases (extending wait).
                    if new_wait_total != remaining_wait:
                         logger.info(f"Wait time updated: Tokens={self.tokens:.2f}/{recovery_target}, Rate={self.REFILL_RATE_PER_MINUTE}, New Wait={new_wait_total}s (was {remaining_wait}s)")
                    else:
                         logger.info(f"Still waiting for tokens... Current: {self.tokens:.2f}/{recovery_target}. Remaining wait: ~{new_wait_total}s")

                    remaining_wait = new_wait_total

            else:
                logger.error("Zero refill rate, cannot wait for tokens. Pausing for 15 minutes as a fallback.")
                time.sleep(900)
                self._refill_tokens()

        logger.info(f"Permission granted for API call. Estimated cost: {estimated_cost}. Current tokens: {self.tokens:.2f}")

    def sync_tokens(self):
        """
        Authoritatively fetches the current token status from the Keepa API
        and updates the internal state.
        """
        from .keepa_api import get_token_status
        logger.info("Performing authoritative token sync with Keepa API...")
        status_data = get_token_status(self.api_key)
        if status_data and 'tokensLeft' in status_data:
            refill_rate = status_data.get('refillRate')
            self._sync_tokens_from_response(status_data['tokensLeft'], refill_rate=refill_rate)
        else:
            logger.error("Failed to sync tokens. API did not return valid token data.")

    def _sync_tokens_from_response(self, tokens_left_from_api, refill_rate=None):
        """
        Authoritatively sets the token count from a provided API response value.
        Also updates the refill rate if provided.
        """
        old_token_count = self.tokens
        self.tokens = float(tokens_left_from_api)
        self.last_refill_timestamp = time.time()

        if refill_rate is not None:
            try:
                new_rate = float(refill_rate)
                if new_rate != self.REFILL_RATE_PER_MINUTE:
                    logger.info(f"Updating refill rate from {self.REFILL_RATE_PER_MINUTE} to {new_rate} based on API response.")
                    self.REFILL_RATE_PER_MINUTE = new_rate
            except (ValueError, TypeError):
                logger.warning(f"Invalid refill rate received from API: {refill_rate}")

        logger.info(
            f"Token count authoritatively synced from API response. "
            f"Previous estimate: {old_token_count:.2f}, New value: {self.tokens:.2f}"
        )

    def update_after_call(self, tokens_left_from_api):
        """
        Updates the token count and timestamp after an API call using the authoritative response.
        Note: Standard API responses (headers/metadata) typically only give tokensLeft,
        so we don't update refill_rate here unless we parse the full status object elsewhere.
        """
        self.last_api_call_timestamp = time.time()
        self._sync_tokens_from_response(tokens_left_from_api)
