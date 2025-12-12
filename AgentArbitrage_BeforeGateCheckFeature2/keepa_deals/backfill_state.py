import json
import os
import logging

class BackfillState:
    """Manages the state of the backfill process."""
    def __init__(self, state_file):
        self.state_file = state_file
        self.state = self._load_state()

    def _load_state(self):
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logging.warning(f"Could not read or parse state file {self.state_file}, starting fresh. Error: {e}")
                return self._default_state()
        return self._default_state()

    def _default_state(self):
        return {'last_completed_page': 0}

    def _save_state(self):
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f)
        except IOError as e:
            logging.error(f"Could not write to state file {self.state_file}. State may not be saved. Error: {e}")

    def get_last_completed_page(self):
        return self.state.get('last_completed_page', 0)

    def set_last_completed_page(self, page_number):
        self.state['last_completed_page'] = page_number
        self._save_state()

    def reset(self):
        self.state = self._default_state()
        self._save_state()
        logging.info("Backfill state has been reset.")
