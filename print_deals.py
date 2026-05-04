import sqlite3
import keepa_deals.db_utils as db_utils
conn = sqlite3.connect(db_utils.DB_PATH)
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
print(cursor.fetchall())
