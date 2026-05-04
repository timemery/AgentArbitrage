import sqlite3
import keepa_deals.db_utils as db_utils
conn = sqlite3.connect(db_utils.DB_PATH)
cursor = conn.cursor()
cursor.execute("SELECT Profit, All_in_Cost, Deal_Trust, List_at, \"1yr_Avg\" FROM deals")
rows = cursor.fetchall()
if len(rows) == 0:
    print("WARNING: Sandbox database 'deals' table is completely empty.")
else:
    print(rows[:5])
