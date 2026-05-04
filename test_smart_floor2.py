import sqlite3
import keepa_deals.db_utils as db_utils

conn = sqlite3.connect(db_utils.DB_PATH)
cursor = conn.cursor()

sanitized_profit = "CAST(REPLACE(REPLACE(\"Profit\", '$', ''), ',', '') AS REAL)"
sanitized_cost = "CAST(REPLACE(REPLACE(\"All_in_Cost\", '$', ''), ',', '') AS REAL)"

cursor.execute("SELECT COUNT(*) FROM deals")
print(f"Total deals: {cursor.fetchone()[0]}")

cursor.execute(f"SELECT COUNT(*) FROM deals WHERE {sanitized_profit} >= 10")
print(f"Profit >= 10: {cursor.fetchone()[0]}")

cursor.execute(f"SELECT COUNT(*) FROM deals WHERE ({sanitized_cost} > 0 AND (({sanitized_profit} * 1.0 / {sanitized_cost}) * 100) >= 15)")
print(f"ROI >= 15: {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM deals WHERE CAST(REPLACE(\"Deal_Trust\", '%', '') AS INTEGER) >= 40")
print(f"Deal_Trust >= 40: {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM deals WHERE \"List_at\" <= 1500")
print(f"List_at <= 1500: {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM deals WHERE \"List_at\" IS NOT NULL AND \"List_at\" > 0")
print(f"List_at valid: {cursor.fetchone()[0]}")

cursor.execute("SELECT COUNT(*) FROM deals WHERE \"1yr_Avg\" IS NOT NULL AND \"1yr_Avg\" NOT IN ('-', 'N/A', '', '0', '0.00', '$0.00') AND \"1yr_Avg\" != 0")
print(f"1yr_Avg valid: {cursor.fetchone()[0]}")
