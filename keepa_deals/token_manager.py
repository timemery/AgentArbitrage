import time
import math
import logging
import os
import redis
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

class TokenManager:
    """
    Manages Keepa API tokens, rate limiting, and refills using Redis for shared state.
    Uses Atomic Reservation (Check-Then-Act mitigation) to prevent race conditions.
    """
    REDIS_KEY_TOKENS = "keepa_tokens_left"
    REDIS_KEY_RATE = "keepa_refill_rate"

    def __init__(self, api_key):
        self.api_key = api_key

        # Constants
        self.REFILL_RATE_PER_MINUTE = 5.0 # Default, will be updated from Redis/API
        self.MIN_TIME_BETWEEN_CALLS_SECONDS = 60
        self.MIN_TOKEN_THRESHOLD = 50

        # State variables
        self.tokens = 100 # Local cache/fallback
        self.max_tokens = 300
        self.last_api_call_timestamp = time.time() - self.MIN_TIME_BETWEEN_CALLS_SECONDS
        self.last_refill_timestamp = time.time()

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
        except Exception as e:
            logger.error(f"Redis load state error: {e}")

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

                    # Case A: Above threshold - Always OK (Controlled Deficit)
                    # We allow the operation if we started with a healthy balance, even if the result is negative.
                    if old_balance >= self.MIN_TOKEN_THRESHOLD:
                        allowed = True

                    # Case B: Priority Pass - Low cost, and strictly NOT negative
                    elif cost_int <= 10 and self.tokens >= 0:
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

            # Case B: Priority Pass (Cost <= 10 AND Tokens >= 0)
            # If cost is small, we just need to be non-negative.
            required_priority = 0

            target = required_standard
            if cost_int <= 10:
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
                recovery_target = target + 5

            if recovery_target > 0:
                tokens_needed = recovery_target - self.tokens
                if tokens_needed > 0:
                    wait_time = math.ceil((tokens_needed / self.REFILL_RATE_PER_MINUTE) * 60)

            if wait_time > 0:
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
        Sleeps in chunks, checking for refill/sync updates.
        """
        logger.info(f"Entered wait loop. Initial Wait: {initial_wait}s. Target: {target}")
        remaining = initial_wait
        while remaining > 0:
            sleep_chunk = max(1, min(remaining, 30))
            time.sleep(sleep_chunk)

            # Sync to check progress (updates self.tokens)
            self.sync_tokens()
            if self.tokens >= target:
                logger.info(f"Tokens recovered ({self.tokens:.2f} >= {target}). Resuming.")
                return

            # Recalc
            tokens_needed = target - self.tokens
            if tokens_needed <= 0: return

            # Refill rate might have changed
            if self.REFILL_RATE_PER_MINUTE <= 0:
                logger.error("Refill rate 0. Sleeping 15m.")
                time.sleep(900)
                self.sync_tokens()
                continue

            new_wait = math.ceil((tokens_needed / self.REFILL_RATE_PER_MINUTE) * 60)
            remaining = new_wait

    def sync_tokens(self):
        """
        Authoritatively fetches the current token status from the Keepa API
        and updates the internal state and Redis.
        """
        from .keepa_api import get_token_status
        status_data = get_token_status(self.api_key)
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
