import sqlite3
import keepa_deals.db_utils as db_utils

conn = sqlite3.connect(db_utils.DB_PATH)
cursor = conn.cursor()

sanitized_profit = "CAST(REPLACE(REPLACE(\"Profit\", '$', ''), ',', '') AS REAL)"
sanitized_cost = "CAST(REPLACE(REPLACE(\"All_in_Cost\", '$', ''), ',', '') AS REAL)"

# Query 1: Total deals
cursor.execute("SELECT COUNT(*) FROM deals")
total = cursor.fetchone()[0]
print(f"Total deals: {total}")

# Query 2: Profit >= 15
cursor.execute(f"SELECT COUNT(*) FROM deals WHERE {sanitized_profit} >= 15")
print(f"Deals with Profit >= 15: {cursor.fetchone()[0]}")

# Query 3: Profit >= 15 AND ROI >= 30
cursor.execute(f"SELECT COUNT(*) FROM deals WHERE {sanitized_profit} >= 15 AND ({sanitized_cost} > 0 AND (({sanitized_profit} * 1.0 / {sanitized_cost}) * 100) >= 30)")
print(f"Deals with Profit >= 15 AND ROI >= 30: {cursor.fetchone()[0]}")

# Query 4: Full Smart Floor
where_sql = f"WHERE {sanitized_profit} >= 15 AND ({sanitized_cost} > 0 AND (({sanitized_profit} * 1.0 / {sanitized_cost}) * 100) >= 30) AND CAST(\"Deal_Trust\" AS INTEGER) >= 70 AND \"List_at\" <= 1500 AND \"List_at\" IS NOT NULL AND \"List_at\" > 0 AND \"1yr_Avg\" IS NOT NULL AND \"1yr_Avg\" NOT IN ('-', 'N/A', '', '0', '0.00', '$0.00') AND \"1yr_Avg\" != 0"
cursor.execute(f"SELECT COUNT(*) FROM deals {where_sql}")
print(f"Deals passing full Smart Floor: {cursor.fetchone()[0]}")
