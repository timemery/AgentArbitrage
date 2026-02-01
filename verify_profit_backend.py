import sqlite3
import os

# Create a dummy database
db_path = 'test_deals_profit.db'
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

# Insert deals: one with positive profit, one with negative profit, one with NULL profit
cursor.execute("INSERT INTO deals (ASIN, Profit) VALUES ('P1', 10.0)")
cursor.execute("INSERT INTO deals (ASIN, Profit) VALUES ('P2', -5.0)")
cursor.execute("INSERT INTO deals (ASIN, Profit) VALUES ('P3', NULL)")
conn.commit()

# Simulate backend logic for Profit
def get_deals_profit(filters):
    where_clauses = []
    filter_params = []

    # This logic matches what is currently in wsgi_handler.py
    if filters.get("profit_gte") is not None and filters["profit_gte"] > 0:
        where_clauses.append("\"Profit\" >= ?")
        filter_params.append(filters["profit_gte"])

    where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    query = f"SELECT ASIN, Profit FROM deals{where_sql}"
    print(f"Query: {query} Params: {filter_params}")
    return cursor.execute(query, filter_params).fetchall()

# Test Case: profit_gte = 0
print("--- Test Case: profit_gte = 0 ---")
results = get_deals_profit({"profit_gte": 0})
print("Results:", results)
# Expectation: All deals should appear if 0 works as "Any"

conn.close()
os.remove(db_path)
