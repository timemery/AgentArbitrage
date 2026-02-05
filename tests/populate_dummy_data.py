import sqlite3
import datetime

def populate():
    conn = sqlite3.connect('deals.db')
    c = conn.cursor()

    # Create deals table if not exists (it should, but just in case)
    # Actually, the app creates tables on init usually? No, the log only mentioned user_restrictions.
    # I should check if deals table exists.

    # Simple schema for testing
    c.execute('''CREATE TABLE IF NOT EXISTS deals (
        ASIN TEXT PRIMARY KEY,
        Title TEXT,
        Condition TEXT,
        Sales_Rank_Current INTEGER,
        Sales_Rank_30_days_avg INTEGER,
        Sales_Rank_180_days_avg INTEGER,
        Sales_Rank_365_days_avg INTEGER,
        Sales_Rank_Drops_last_30_days INTEGER,
        Sales_Rank_Drops_last_180_days INTEGER,
        Sales_Rank_Drops_last_365_days INTEGER,
        Offers_New_Current INTEGER,
        Offers_Used_Current INTEGER,
        Offers_Used_90_days_avg REAL,
        Offers_Used_180_days_avg REAL,
        Offers_Used_365_days_avg REAL,
        Price_New_Current INTEGER,
        Price_Used_Current INTEGER,
        List_at REAL,
        Expected_Trough_Price REAL,
        "1yr_Avg" REAL,
        Price_Now REAL,
        Percent_Down REAL,
        last_price_change TEXT,
        Seller_Quality_Score REAL,
        Profit_Confidence REAL,
        All_in_Cost REAL,
        Profit REAL,
        Margin REAL,
        Detailed_Seasonality TEXT,
        Binding TEXT,
        Seller TEXT,
        Deal_found TEXT,
        Categories_Sub TEXT,
        Manufacturer TEXT,
        Publication_Date TEXT,
        Sells TEXT,
        Min_Listing_Price REAL,
        List_Price_Highest REAL,
        Trough_Season TEXT,
        Shipping_Included TEXT,
        Trend TEXT,
        Amazon_Current REAL,
        Amazon_365_days_avg REAL,
        Buy_Box_Used_Current REAL,
        Buy_Box_Used_365_days_avg REAL,
        AMZ TEXT
    )''')

    # Insert a dummy deal
    deal = (
        'B000000001', 'Test Book Title Long Enough To Be Truncated', 'Used - Very Good',
        100000, 120000, 130000, 140000,
        5, 20, 40,
        10, 15, 14, 13, 12,
        5000, 2000, 45.00, 15.00,
        30.00, 20.00, 33.3,
        datetime.datetime.now().isoformat(),
        0.95, 80.0,
        10.00, 35.00, 77.0,
        'Fall Semester', 'Hardcover', 'Best Seller Inc',
        datetime.datetime.now().isoformat(), 'Textbooks', 'Pearson', '2020-01-01',
        'Sept', 12.00, 50.00, 'May', 'Yes', '⇩',
        50.00, 48.00, 22.00, 20.00, ''
    )

    # Columns matching the tuple
    cols = '''ASIN, Title, Condition, Sales_Rank_Current, Sales_Rank_30_days_avg, Sales_Rank_180_days_avg, Sales_Rank_365_days_avg,
    Sales_Rank_Drops_last_30_days, Sales_Rank_Drops_last_180_days, Sales_Rank_Drops_last_365_days,
    Offers_New_Current, Offers_Used_Current, Offers_Used_90_days_avg, Offers_Used_180_days_avg, Offers_Used_365_days_avg,
    Price_New_Current, Price_Used_Current, List_at, Expected_Trough_Price, "1yr_Avg", Price_Now, Percent_Down,
    last_price_change, Seller_Quality_Score, Profit_Confidence, All_in_Cost, Profit, Margin, Detailed_Seasonality,
    Binding, Seller, Deal_found, Categories_Sub, Manufacturer, Publication_Date, Sells, Min_Listing_Price,
    List_Price_Highest, Trough_Season, Shipping_Included, Trend, Amazon_Current, Amazon_365_days_avg,
    Buy_Box_Used_Current, Buy_Box_Used_365_days_avg, AMZ'''

    placeholders = ','.join(['?'] * 46)

    try:
        c.execute(f'INSERT OR REPLACE INTO deals ({cols}) VALUES ({placeholders})', deal)
        conn.commit()
        print("Dummy deal inserted.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        conn.close()

if __name__ == '__main__':
    populate()
