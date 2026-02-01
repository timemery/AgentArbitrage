import sqlite3
import os

# Create a dummy database
db_path = 'test_deals.db'
if os.path.exists(db_path):
    os.remove(db_path)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE deals (
        id INTEGER PRIMARY KEY,
        ASIN TEXT,
        Margin REAL,
        Profit REAL,
        Profit_Confidence INTEGER,
        Seller_Quality_Score REAL,
        Percent_Down REAL,
        Sales_Rank_Current INTEGER,
        Title TEXT,
        Categories_Sub TEXT,
        Detailed_Seasonality TEXT,
        Manufacturer TEXT,
        Author TEXT,
        Seller TEXT,
        AMZ TEXT
    )
''')

# Insert deals: one with positive margin, one with negative margin, one with NULL margin
cursor.execute("INSERT INTO deals (ASIN, Margin) VALUES ('A1', 10.0)")
cursor.execute("INSERT INTO deals (ASIN, Margin) VALUES ('A2', -5.0)")
cursor.execute("INSERT INTO deals (ASIN, Margin) VALUES ('A3', NULL)")
conn.commit()

# Simulate backend logic
def get_deals(filters):
    where_clauses = []
    filter_params = []

    if filters.get("margin_gte") is not None and filters["margin_gte"] > 0:
        where_clauses.append("\"Margin\" >= ?")
        filter_params.append(filters["margin_gte"])

    where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    query = f"SELECT ASIN, Margin FROM deals{where_sql}"
    print(f"Query: {query} Params: {filter_params}")
    return cursor.execute(query, filter_params).fetchall()

# Test Case 1: margin_gte = 0 (Current Default)
print("--- Test Case 1: margin_gte = 0 ---")
results = get_deals({"margin_gte": 0})
print("Results:", results)
# Expectation: Only A1 (10.0) should show. A2 (-5.0) and A3 (NULL) should be hidden.
# If we want "Any", we expect A1, A2, and A3 (or at least A1 and A2) to show.

conn.close()
os.remove(db_path)
