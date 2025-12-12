import json
import os
from logging import getLogger

logger = getLogger(__name__)

class XaiCache:
    """
    A simple persistent JSON-based cache for XAI API responses to avoid redundant calls.
    """
    def __init__(self, cache_path='xai_cache.json'):
        self.cache_path = cache_path
        self.cache = self._load_cache()

    def _load_cache(self):
        """Loads the cache from a JSON file."""
        if not os.path.exists(self.cache_path):
            logger.info("XAI cache file not found. Starting with an empty cache.")
            return {}
        try:
            with open(self.cache_path, 'r') as f:
                cache = json.load(f)
            logger.info(f"Successfully loaded {len(cache)} items from XAI cache.")
            return cache
        except (IOError, json.JSONDecodeError):
            logger.warning(f"Could not read or parse '{self.cache_path}'. Starting with an empty cache.")
            return {}

    def _save_cache(self):
        """Saves the in-memory cache to the JSON file."""
        try:
            with open(self.cache_path, 'w') as f:
                json.dump(self.cache, f, indent=4)
        except IOError as e:
            logger.error(f"Could not save XAI cache to '{self.cache_path}': {e}")

    def get(self, key):
        """
        Retrieves a value from the cache.
        Returns the cached value or None if the key is not found.
        """
        result = self.cache.get(key)
        if result:
            logger.debug(f"XAI Cache HIT for key: '{key}'")
        else:
            logger.debug(f"XAI Cache MISS for key: '{key}'")
        return result

    def set(self, key, value):
        """
        Adds a key-value pair to the cache and saves it to disk.
        """
        logger.debug(f"XAI Cache SET for key: '{key}'")
        self.cache[key] = value
        self._save_cache()
