import sys
import os

# Add repo root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from keepa_deals import smart_ingestor
    print("Successfully imported keepa_deals.smart_ingestor")
except Exception as e:
    print(f"Failed to import keepa_deals.smart_ingestor: {e}")
    sys.exit(1)
