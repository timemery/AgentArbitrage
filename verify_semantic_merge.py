import os
import sys
import logging

# Setup basic logging to stdout
logging.basicConfig(level=logging.INFO)

# Append cwd to path so we can import wsgi_handler
sys.path.append(os.getcwd())

import wsgi_handler

def main():
    print("Starting homogenization verification...")
    try:
        # We call the function directly. It will use the real 'intelligence.json'
        # and the real 'query_xai_api' (which uses the env var XAI_TOKEN).
        # BE CAREFUL: This consumes tokens and modifies the file if successful.
        # However, since the user reported "0 removed", running it again here allows us to see the logs.
        removed = wsgi_handler._homogenize_intelligence()
        print(f"Homogenization complete. Removed: {removed}")
    except Exception as e:
        print(f"Error during homogenization: {e}")

if __name__ == "__main__":
    main()
