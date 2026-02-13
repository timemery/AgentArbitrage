import time
import math
import logging
import os
import redis
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class TokenRechargeError(Exception):
    """Raised when the system must pause for a long recharge duration."""
    pass

class TokenManager:
    """
    Manages Keepa API tokens, rate limiting, and refills using Redis for shared state.
    Uses Atomic Reservation (Check-Then-Act mitigation) to prevent race conditions.
    """
    REDIS_KEY_TOKENS = "keepa_tokens_left"
    REDIS_KEY_RATE = "keepa_refill_rate"
    REDIS_KEY_RECHARGE_MODE = "keepa_recharge_mode_active"
    REDIS_KEY_TIMESTAMP = "keepa_token_timestamp"

    def __init__(self, api_key):
        self.api_key = api_key

        # Constants
        self.REFILL_RATE_PER_MINUTE = 5.0 # Default, will be updated from Redis/API
        # FIX: Reduced from 60 to 1 to allow Burst Mode. Keepa is token-based, not time-based.
        self.MIN_TIME_BETWEEN_CALLS_SECONDS = 1
        self.MIN_TOKEN_THRESHOLD = 1
        # Dynamic Burst Threshold: For low-tier plans, waiting for 280 takes too long (~1hr).
        # We start with 280 but will adjust based on refill rate.
        self.BURST_THRESHOLD = 280
        self.MAX_DEFICIT = -180  # Safety limit to prevent Keepa API lockout

        # Throttling for sync calls (to prevent drain)
        self.last_sync_request_timestamp = 0

        # State variables
        self.tokens = 100 # Local cache/fallback
        self.max_tokens = 300
        self.last_api_call_timestamp = time.time() - self.MIN_TIME_BETWEEN_CALLS_SECONDS
        self.last_refill_timestamp = 0

        # Redis Setup
        redis_url = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')
        try:
            self.redis_client = redis.Redis.from_url(redis_url, decode_responses=True)
            # Verify connection
            self.redis_client.ping()
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}. Falling back to local token management.")
            self.redis_client = None

        logger.info("TokenManager initialized with Redis shared state.")
        # Try to load initial state from Redis
        self._load_state_from_redis()
        self._adjust_burst_threshold()

    def _adjust_burst_threshold(self):
        """
        Dynamically adjusts the Burst Threshold based on refill rate.
        For low rates (<10/min), waiting for 280 tokens creates a perception of 'stalling' (50+ min wait).
        We lower it to improve responsiveness while still allowing efficient batch processing.
        """
        if self.REFILL_RATE_PER_MINUTE < 10:
            # 80 tokens takes ~16 mins to refill at 5/min.
            # This allows for ~4 heavy updates (20 tokens each) or ~40 light checks.
            self.BURST_THRESHOLD = 40
            # logger.info(f"Low Refill Rate ({self.REFILL_RATE_PER_MINUTE}/min) detected. Adjusted Burst Threshold to {self.BURST_THRESHOLD} to improve responsiveness.")
        else:
            self.BURST_THRESHOLD = 280

    def _get_shared_tokens(self):
        if not self.redis_client:
            return None
        try:
            val = self.redis_client.get(self.REDIS_KEY_TOKENS)
            return float(val) if val is not None else None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None

    def _set_shared_tokens(self, tokens, rate=None):
        if not self.redis_client:
            return
        try:
            self.redis_client.set(self.REDIS_KEY_TOKENS, str(tokens))
            self.redis_client.set(self.REDIS_KEY_TIMESTAMP, str(time.time()))
            if rate:
                self.redis_client.set(self.REDIS_KEY_RATE, str(rate))
        except Exception as e:
            logger.error(f"Redis set error: {e}")

    def _load_state_from_redis(self):
        if not self.redis_client:
            return
        try:
            tokens = self._get_shared_tokens()
            if tokens is not None:
                self.tokens = tokens

            rate = self.redis_client.get(self.REDIS_KEY_RATE)
            if rate:
                self.REFILL_RATE_PER_MINUTE = float(rate)
                self._adjust_burst_threshold()

            ts = self.redis_client.get(self.REDIS_KEY_TIMESTAMP)
            if ts:
                self.last_refill_timestamp = float(ts)
        except Exception as e:
            logger.error(f"Redis load state error: {e}")

    def get_projected_tokens(self):
        """
        Estimates current tokens based on last known value and elapsed time.
        """
        if not self.redis_client:
            return self.tokens

        try:
            self._load_state_from_redis()
            elapsed_minutes = (time.time() - self.last_refill_timestamp) / 60.0
            if elapsed_minutes < 0: elapsed_minutes = 0

            projected = self.tokens + (elapsed_minutes * self.REFILL_RATE_PER_MINUTE)
            return min(projected, self.max_tokens)
        except Exception as e:
            logger.error(f"Error projecting tokens: {e}")
            return self.tokens

    def should_skip_sync(self):
        """
        Returns True if we are in Recharge Mode AND projected tokens are still critical.
        Used to prevent API spamming during deep freeze.
        """
        if not self.redis_client:
            return False

        is_recharging = self.redis_client.get(self.REDIS_KEY_RECHARGE_MODE) == "1"
        if not is_recharging:
            return False

        projected = self.get_projected_tokens()
        # If we are projected to be well below the threshold, stay quiet.
        if projected < self.BURST_THRESHOLD:
            return True

        return False

    def has_enough_tokens(self, estimated_cost):
        """
        Checks if there are enough tokens to proceed with an operation of the given cost,
        respecting the minimum token threshold.
        This is a non-blocking check.
        """
        # Ensure we have the latest shared state
        self._load_state_from_redis()

        if self.tokens < self.MIN_TOKEN_THRESHOLD:
            return False

        return self.tokens >= estimated_cost

    def request_permission_for_call(self, estimated_cost):
        """
        Checks if an API call can be made and waits if necessary.
        Uses optimistic atomic reservation (decrby) to handle concurrency.
        """
        cost_int = math.ceil(estimated_cost)

        while True:
            # 0. Check Recharge Mode (Redis)
            # If we are in "Recharge Mode" (low-tier strategy), we must wait until the bucket is full.
            # CRITICAL FIX: We MUST check this regardless of the current REFILL_RATE.
            # If Recharge Mode was activated (because rate was low), it must persist until satisfied.
            # This prevents "flapping" where a transient rate spike unlocks the system prematurely.
            if self.redis_client:
                is_recharging = self.redis_client.get(self.REDIS_KEY_RECHARGE_MODE)
                if is_recharging == "1":
                    # --- SAFETY: Check for Recharge Timeout (Stuck Logic) ---
                    recharge_start_str = self.redis_client.get("keepa_recharge_start_time")
                    start_time = None
                    if recharge_start_str:
                        try:
                            start_time = float(recharge_start_str)
                        except ValueError:
                            pass

                    if start_time is None:
                        # Adopt current time if missing (legacy/orphaned)
                        start_time = time.time()
                        self.redis_client.set("keepa_recharge_start_time", str(start_time))

                    elapsed = time.time() - start_time
                    RECHARGE_TIMEOUT_SECONDS = 3600 # 60 minutes

                    if elapsed > RECHARGE_TIMEOUT_SECONDS:
                        logger.warning(f"CRITICAL: Recharge Mode timed out after {elapsed/60:.1f} minutes (Limit: 60m). Forcing exit to prevent Livelock/Stuck state.")
                        self.redis_client.delete(self.REDIS_KEY_RECHARGE_MODE)
                        self.redis_client.delete("keepa_recharge_start_time")
                        # Proceed with request
                    else:
                        # Check if we have reached the burst threshold
                        # Note: We use the local token estimate (sync happening in wait loop)
                        if self.tokens >= self.BURST_THRESHOLD:
                            logger.info(f"Burst threshold reached ({self.tokens:.2f} >= {self.BURST_THRESHOLD}). Exiting Recharge Mode.")
                            self.redis_client.delete(self.REDIS_KEY_RECHARGE_MODE)
                            self.redis_client.delete("keepa_recharge_start_time")
                        else:
                            # Trust the math.
                            tokens_needed = self.BURST_THRESHOLD - self.tokens
                            if tokens_needed < 0: tokens_needed = 0

                            # Safety check: avoid division by zero or negative rate
                            rate_for_calc = self.REFILL_RATE_PER_MINUTE
                            if rate_for_calc <= 0: rate_for_calc = 1.0

                            wait_time = math.ceil((tokens_needed / rate_for_calc) * 60)

                            # If the wait is long (e.g. > 60 seconds), we should not sleep and block the worker.
                            # Instead, we raise an exception to let the caller (task) exit and retry later.
                            if wait_time > 60:
                                logger.warning(f"Recharge Mode: Tokens critically low ({self.tokens:.2f}). Required wait: {wait_time}s. Exiting task to free worker.")
                                raise TokenRechargeError(f"Recharge needed: {wait_time}s")

                            if wait_time < 5: wait_time = 5 # Minimum sleep
                            self._wait_for_tokens(wait_time, self.BURST_THRESHOLD)
                            continue

            # 1. Rate Limit Sleep (Local) - Prevent spamming API even if tokens exist
            now = time.time()
            time_since_last = now - self.last_api_call_timestamp
            if time_since_last < self.MIN_TIME_BETWEEN_CALLS_SECONDS:
                wait = self.MIN_TIME_BETWEEN_CALLS_SECONDS - time_since_last
                # logger.info(f"Rate limit: Pausing for {wait:.2f} seconds.")
                time.sleep(wait)

            # 2. Atomic Reservation (Redis)
            if self.redis_client:
                try:
                    # Optimistically decrement
                    # Use incrbyfloat with negative value because Keepa tokens can be floats (e.g. 50.5)
                    # and standard Redis DECRBY expects integer values.
                    new_val = self.redis_client.incrbyfloat(self.REDIS_KEY_TOKENS, -cost_int)
                    self.tokens = float(new_val)

                    # --- CHECK CONSTRAINTS ---
                    allowed = False

                    # Calculate starting balance (approximate)
                    old_balance = self.tokens + cost_int

                    # Refill-to-Full Logic: Enter Recharge Mode if we drop too low
                    # Only enter if rate is low. But once entered, the logic above (block 0) keeps us there.
                    if self.REFILL_RATE_PER_MINUTE < 10 and old_balance < self.MIN_TOKEN_THRESHOLD:
                        logger.warning(f"Tokens critically low ({old_balance:.2f} < {self.MIN_TOKEN_THRESHOLD}). Entering Recharge Mode until {self.BURST_THRESHOLD}.")
                        self.redis_client.set(self.REDIS_KEY_RECHARGE_MODE, "1")
                        self.redis_client.set("keepa_recharge_start_time", str(time.time()))
                        # Fail this request and force a wait loop
                        allowed = False

                    # Case A: Above threshold - Always OK (Controlled Deficit)
                    # We allow the operation if we started with a healthy balance, even if the result is negative.
                    elif old_balance >= self.MIN_TOKEN_THRESHOLD:
                        # Safety Check: Prevent extreme deficits
                        if self.tokens < self.MAX_DEFICIT:
                            logger.warning(f"Request blocked: Projected balance {self.tokens:.2f} exceeds max deficit {self.MAX_DEFICIT}.")
                            allowed = False
                        else:
                            allowed = True

                    # Case B: Priority Pass - Low cost, and strictly NOT negative
                    # Disabled for low refill rates (<10/min) to prevent starvation of high-cost tasks
                    elif cost_int <= 10 and self.tokens >= 0 and self.REFILL_RATE_PER_MINUTE >= 10:
                        logger.info(f"Priority Pass: allowing small cost {cost_int}. Balance: {self.tokens:.2f}")
                        allowed = True

                    if allowed:
                        # Success! We hold the reservation.
                        # logger.info(f"Permission granted (Redis). Balance: {self.tokens:.2f}")
                        return

                    # --- FAILURE: REVERT ---
                    # We decremented, but didn't meet criteria. Undo.
                    self.redis_client.incrbyfloat(self.REDIS_KEY_TOKENS, cost_int)

                    # Restore local view for wait calculation (approximate)
                    # We add cost back because we just incremented.
                    self.tokens = float(new_val + cost_int)
                    # logger.warning(f"Tokens low ({self.tokens:.2f}). Reverted reservation. Waiting.")

                except Exception as e:
                    logger.error(f"Redis error during reservation: {e}. Falling back to local.")
                    self.redis_client = None # Disable Redis for this session

            # 3. Local / Fallback / Wait Logic
            # If we are here, we either:
            # a) Have no Redis
            # b) Had Redis, tried to reserve, failed, and reverted.

            # If local mode (no redis), just check local state
            if not self.redis_client:
                 # Refill local logic
                 # (Simplified for brevity as Redis is primary)
                 pass

            # Check if we are critically low - Force Sync
            if self.tokens < self.MIN_TOKEN_THRESHOLD:
                 # logger.info(f"Local/Shared token count ({self.tokens:.2f}) is low. Syncing...")
                 self.sync_tokens()

            # Calculate Wait Time
            wait_time = 0
            recovery_target = 0

            # Determine required tokens to pass checks
            # Case A: Standard Check (Controlled Deficit)
            # We only need the STARTING balance to be >= Threshold.
            # So we need self.tokens (which mimics starting balance here) >= Threshold.
            required_standard = self.MIN_TOKEN_THRESHOLD

            # Deficit Safety Check
            required_for_deficit = cost_int + self.MAX_DEFICIT
            if required_for_deficit > required_standard:
                required_standard = required_for_deficit

            # Case B: Priority Pass (Cost <= 10 AND Tokens >= 0)
            # If cost is small, we just need to be non-negative.
            required_priority = 0

            target = required_standard
            if cost_int <= 10 and self.REFILL_RATE_PER_MINUTE >= 10:
                target = required_priority

            if self.tokens <= 0:
                recovery_target = 10 # Wait until positive buffer
            elif self.tokens < target:
                # If we are here, we failed priority pass (if redis)
                # Or we are local and low.
                if not self.redis_client and cost_int <= 10 and self.tokens >= cost_int:
                    # Local priority pass
                    self.tokens -= cost_int
                    return

                # Wait until we have enough to pass the check + small buffer
                if self.REFILL_RATE_PER_MINUTE < 10:
                    recovery_target = target # No buffer for slow connections to maximize throughput
                else:
                    recovery_target = target + 5

            if recovery_target > 0:
                tokens_needed = recovery_target - self.tokens
                if tokens_needed > 0:
                    wait_time = math.ceil((tokens_needed / self.REFILL_RATE_PER_MINUTE) * 60)

            if wait_time > 0:
                # If we need to wait a long time to recover a minimum balance, exit instead of sleeping.
                if wait_time > 60:
                    logger.warning(f"Insufficient tokens (Current: {self.tokens:.2f}, Target: {target}). Wait {wait_time}s > 60s. Exiting task.")
                    raise TokenRechargeError(f"Insufficient tokens: wait {wait_time}s")

                logger.warning(f"Insufficient tokens (Current: {self.tokens:.2f}, Target: {target}). Waiting for {wait_time}s.")
                self._wait_for_tokens(wait_time, recovery_target)
                continue # Retry reservation loop

            # If wait_time is 0, it means we are ostensibly good.
            # If Redis, we loop back to try reservation again.
            if self.redis_client:
                continue
            else:
                # Local success
                self.tokens -= cost_int
                return

    def _wait_for_tokens(self, initial_wait, target):
        """
        Sleeps for the calculated duration to allow refill.
        Avoids calling sync_tokens() in a loop to prevent token drain from status checks.
        """
        logger.info(f"Entered wait loop. Estimated Wait: {initial_wait}s to reach {target} tokens.")

        # Determine strict sleep duration
        # We assume 100% reliability of the refill rate.
        # We only wake up early to check for "Recharge Timeout" (every 5 mins)

        remaining = initial_wait
        while remaining > 0:
            sleep_chunk = min(remaining, 300) # Max sleep 5 mins at a time
            time.sleep(sleep_chunk)
            remaining -= sleep_chunk

            # --- Check Global Timeout (Livelock Prevention) ---
            if self.redis_client:
                recharge_start_str = self.redis_client.get("keepa_recharge_start_time")
                if recharge_start_str:
                    try:
                        start_ts = float(recharge_start_str)
                        if (time.time() - start_ts) > 3600:
                            logger.warning(f"Recharge Timeout detected inside wait loop. Forcing exit.")
                            return
                    except ValueError:
                        pass

        # Only sync at the very end of the wait
        logger.info(f"Wait complete. Syncing tokens...")
        self.sync_tokens()
        logger.info(f"Tokens after wait: {self.tokens:.2f}")

    def sync_tokens(self, force=False):
        """
        Authoritatively fetches the current token status from the Keepa API
        and updates the internal state and Redis.
        Includes throttling to prevent draining tokens via frequent status checks.
        """
        # Throttling Logic
        now = time.time()
        if not force and (now - self.last_sync_request_timestamp) < 60:
             # logger.debug("Skipping sync_tokens (throttled).")
             return

        from .keepa_api import get_token_status
        status_data = get_token_status(self.api_key)

        # Update timestamp regardless of success to prevent spamming on failure
        self.last_sync_request_timestamp = time.time()

        if status_data and 'tokensLeft' in status_data:
            refill_rate = status_data.get('refillRate')
            self._sync_tokens_from_response(status_data['tokensLeft'], refill_rate=refill_rate)
        else:
            logger.error("Failed to sync tokens. API did not return valid token data.")

    def _sync_tokens_from_response(self, tokens_left_from_api, refill_rate=None):
        """
        Authoritatively sets the token count from a provided API response value.
        Updates Redis.
        """
        self.tokens = float(tokens_left_from_api)
        self.last_refill_timestamp = time.time()

        if refill_rate is not None:
            try:
                self.REFILL_RATE_PER_MINUTE = float(refill_rate)
                self._adjust_burst_threshold()
                if self.REFILL_RATE_PER_MINUTE < 10:
                    pass
                    # logger.warning(f"CRITICAL: Keepa Refill Rate is extremely low...")
                    # (Reduced log spam here, rely on startup log)
            except (ValueError, TypeError):
                pass

        # Update Redis with authoritative value
        self._set_shared_tokens(self.tokens, self.REFILL_RATE_PER_MINUTE)

    def update_after_call(self, tokens_left_from_api):
        """
        Updates the token count and timestamp after an API call using the authoritative response.
        """
        self.last_api_call_timestamp = time.time()
        self._sync_tokens_from_response(tokens_left_from_api)
