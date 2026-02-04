# diag_importer.py
# A simple script to test if the main worker application can be imported without crashing.

import sys
print(f"--- Running importer diagnostic with Python: {sys.executable} ---")
print(f"--- Python Path: {sys.path} ---")

try:
    print("--- Attempting to import worker... ---")
    import worker
    print("--- SUCCESS: 'worker' module imported successfully. ---")
    print("--- This means the Python code itself is likely not the cause of the crash. ---")
except Exception as e:
    print(f"--- FAILED: An exception occurred during import. THIS IS LIKELY THE ROOT CAUSE. ---")
    import traceback
    traceback.print_exc()
