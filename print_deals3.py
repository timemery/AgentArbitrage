import sqlite3
import keepa_deals.db_utils as db_utils
conn = sqlite3.connect(db_utils.DB_PATH)
cursor = conn.cursor()
cursor.execute("SELECT Profit, All_in_Cost, Deal_Trust, List_at, \"1yr_Avg\" FROM deals")
rows = cursor.fetchall()

query = "SELECT COUNT(*) FROM deals WHERE \"Profit\" >= 10"
print(f"Profit >= 10: {cursor.execute(query).fetchone()[0]}")

query = "SELECT COUNT(*) FROM deals WHERE \"Profit\" >= 10 AND \"All_in_Cost\" > 0 AND ((\"Profit\" * 1.0 / \"All_in_Cost\") * 100) >= 15"
print(f"ROI >= 15: {cursor.execute(query).fetchone()[0]}")

query = "SELECT COUNT(*) FROM deals WHERE CAST(\"Deal_Trust\" AS REAL) >= 40"
print(f"Deal_Trust >= 40: {cursor.execute(query).fetchone()[0]}")

query = "SELECT COUNT(*) FROM deals WHERE CAST(REPLACE(REPLACE(\"List_at\", '$', ''), ',', '') AS REAL) <= 1500"
print(f"List_at <= 1500: {cursor.execute(query).fetchone()[0]}")

query = "SELECT COUNT(*) FROM deals WHERE \"List_at\" IS NOT NULL AND CAST(REPLACE(REPLACE(\"List_at\", '$', ''), ',', '') AS REAL) > 0"
print(f"List_at valid: {cursor.execute(query).fetchone()[0]}")

query = "SELECT COUNT(*) FROM deals WHERE \"1yr_Avg\" IS NOT NULL AND \"1yr_Avg\" NOT IN ('-', 'N/A', '', '0', '0.00', '$0.00') AND \"1yr_Avg\" != 0"
print(f"1yr_Avg valid: {cursor.execute(query).fetchone()[0]}")
