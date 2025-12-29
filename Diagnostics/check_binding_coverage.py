#!/usr/bin/env python3
import sqlite3
import os

# --- Mappings Definition ---
# From wsgi_handler.py
backend_binding_map = {
    "Audio CD": "CD",
    "Board book": "BB",
    "Hardcover": "HC",
    "Paperback": "PB",
    "Mass Market Paperback": "MMP"
}

# From templates/dashboard.html
# Note: The JS logic lowercases and removes spaces/hyphens before checking this map.
frontend_binding_map_raw = {
    'spiralbound': 'SB',
    'boardbook': 'BB',
    'hardcover': 'HC',
    'paperback': 'PB',
    'massmarketpaperback': 'MMPB',
    'audiobook': 'Audio',
    'audiocd': 'Audio',
    'looseleaf': 'LL',
    'leatherbound': 'LB',
    'likenew': 'LN',
    'verygood': 'VG',
    'good': 'G',
    'acceptable': 'A'
}

def check_coverage(value):
    if not value or value == '-':
        return True # Ignore empty/null

    # Check Backend Map (Exact Match)
    if value in backend_binding_map:
        return True

    # Check Frontend Map (Normalized)
    cleaned_value = value.lower().replace(' ', '').replace('-', '').replace('_', '')
    if cleaned_value in frontend_binding_map_raw:
        return True

    return False

# --- Database Query ---
# Use environment variable or default to local 'deals.db'
db_path = os.getenv("DATABASE_URL", "deals.db")

if not os.path.exists(db_path):
    print(f"Error: Database not found at '{db_path}'.")
    print("Please set the DATABASE_URL environment variable or ensure 'deals.db' exists in the current directory.")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Check if 'deals' table exists
try:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='deals'")
    if not cursor.fetchone():
        print(f"Error: Table 'deals' not found in database '{db_path}'.")
        conn.close()
        exit(1)

    query = "SELECT Binding, COUNT(*) as count FROM deals GROUP BY Binding ORDER BY count DESC"
    cursor.execute(query)
    rows = cursor.fetchall()
except sqlite3.OperationalError as e:
    print(f"Database error: {e}")
    conn.close()
    exit(1)

conn.close()

# --- Analysis ---
print(f"\nScanning database: {db_path}")
print(f"{'Count':<8} | {'Binding Value':<40} | {'Status'}")
print("-" * 65)

uncovered_values = []

for binding, count in rows:
    if binding is None:
        binding_str = "None"
        is_covered = True # Ignore nulls
    else:
        binding_str = str(binding)
        is_covered = check_coverage(binding_str)

    status = "COVERED" if is_covered else "MISSING"
    if not is_covered:
        uncovered_values.append((count, binding_str))

    # Optional: Uncomment to see all values
    # print(f"{count:<8} | {binding_str:<40} | {status}")

print("\n--- Uncovered Binding Labels ---")
if not uncovered_values:
    print("All binding labels in the database are currently covered!")
else:
    print(f"{'Count':<8} | {'Binding Label'}")
    print("-" * 40)
    for count, label in uncovered_values:
        print(f"{count:<8} | {label}")

print(f"\nTotal distinct binding types found: {len(rows)}")
print(f"Total uncovered types: {len(uncovered_values)}")
