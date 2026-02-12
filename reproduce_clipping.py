import logging
import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Add the current directory to sys.path
sys.path.append(os.getcwd())

from keepa_deals.ava_advisor import generate_ava_advice

# Setup minimal logging to see the output
logging.basicConfig(level=logging.INFO)

# Mock deal data based on user report
mock_deal = {
    'Title': 'Introduction to Calculus (Mock)',
    'Price_Now': 45.00,
    '1yr_Avg': 50.00,
    'Sales_Rank_Current': 1137075,
    'Sales_Rank_365_days_avg': 1229490,
    'Sales_Rank_Drops_last_365_days': 79,
    'Detailed_Seasonality': 'Textbook Seasonality Detected',
    'Profit': 15.00,
    'Margin': 33.33,
    'Percent_Down': 10,
    'Trend': 'FLAT'
}

print("--- Generating Advice (Mock) ---")
advice = generate_ava_advice(mock_deal, mentor_type='cfo')
print("\n--- Advice Output ---")
print(advice)
print("\n--- Length Check ---")
word_count = len(advice.split())
print(f"Length: {len(advice)} characters")
print(f"Word Count: {word_count} words")

if len(advice) > 0 and advice[-1] not in ['.', '!', '?', '>']: # Simple heuristic for checking if it ends with punctuation or HTML tag
    print("POSSIBLE TRUNCATION DETECTED (Ends with: " + repr(advice[-10:]) + ")")
else:
    print("Ends normally.")
