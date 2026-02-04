import sys
import os

print("--- Python Import Test ---")
print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")
print(f"Current working directory: {os.getcwd()}")

print("\nsys.path is:")
for p in sys.path:
    print(f"  - {p}")

try:
    print("\nAttempting to import 'celery_config'...")
    import celery_config
    print("[SUCCESS] Successfully imported 'celery_config'.")
    print(f"Found app variable 'celery': {hasattr(celery_config, 'celery')}")
except ImportError as e:
    print(f"\n[FAILURE] Failed to import 'celery_config'.")
    print(f"Error: {e}")
except Exception as e:
    print(f"\n[FAILURE] An unexpected error occurred.")
    print(f"Error: {e}")

print("\n--- Test Finished ---")
