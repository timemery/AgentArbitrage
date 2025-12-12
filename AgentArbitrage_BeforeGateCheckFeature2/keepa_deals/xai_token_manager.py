import json
import os
from datetime import date
from logging import getLogger

logger = getLogger(__name__)

class XaiTokenManager:
    """
    Manages the daily call quota for the XAI API to prevent rate-limiting and control costs.
    """
    def __init__(self, settings_path='settings.json', state_path='xai_token_state.json'):
        self.state_path = state_path
        self.daily_limit = self._load_daily_limit(settings_path)
        self.state = self._load_state()
        self._check_and_reset_daily_count()

    def _load_daily_limit(self, settings_path):
        """Loads the max_xai_calls_per_day from the main settings.json file."""
        try:
            with open(settings_path, 'r') as f:
                settings = json.load(f)
            limit = settings.get('max_xai_calls_per_day', 1000) # Default to 1000 if not set
            logger.info(f"XAI Token Manager: Daily call limit set to {limit}.")
            return limit
        except (FileNotFoundError, json.JSONDecodeError):
            logger.warning(f"Could not load '{settings_path}'. Using default daily limit of 1000.")
            return 1000

    def _load_state(self):
        """Loads the usage state from a file."""
        try:
            with open(self.state_path, 'r') as f:
                state = json.load(f)
            logger.info(f"Loaded XAI token state: {state}")
            return state
        except (FileNotFoundError, json.JSONDecodeError):
            logger.warning("XAI token state file not found or invalid. Initializing fresh state.")
            return {'last_reset_date': '1970-01-01', 'calls_today': 0}

    def _save_state(self):
        """Saves the current usage state to a file."""
        try:
            with open(self.state_path, 'w') as f:
                json.dump(self.state, f, indent=4)
        except IOError as e:
            logger.error(f"Could not save XAI token state to '{self.state_path}': {e}")

    def _check_and_reset_daily_count(self):
        """Resets the daily call count if the date has changed."""
        today_str = str(date.today())
        if self.state.get('last_reset_date') != today_str:
            logger.info(f"New day detected. Resetting XAI daily call count from {self.state['calls_today']} to 0.")
            self.state['last_reset_date'] = today_str
            self.state['calls_today'] = 0
            self._save_state()

    def request_permission(self):
        """
        Checks if an XAI API call can be made. If yes, increments the count.
        Returns True if the call is permitted, False otherwise.
        """
        self._check_and_reset_daily_count() # Ensure state is fresh before checking

        if self.state['calls_today'] < self.daily_limit:
            self.state['calls_today'] += 1
            self._save_state()
            logger.info(f"XAI call permitted. Usage today: {self.state['calls_today']}/{self.daily_limit}")
            return True
        else:
            logger.warning(
                f"XAI daily call limit reached ({self.daily_limit}). Call denied. "
                "No further XAI calls will be made today."
            )
            return False
