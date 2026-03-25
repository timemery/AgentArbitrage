import sys
import os
import json
import logging
import requests
import io

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from keepa_deals.stable_calculations import analyze_sales_performance, infer_sale_events
from dotenv import load_dotenv

load_dotenv()

# We want to intercept the logs to extract key information without cluttering the screen
log_stream = io.StringIO()
handler = logging.StreamHandler(log_stream)
formatter = logging.Formatter('%(message)s')
handler.setFormatter(formatter)

# Set root logger to capture all our library logs
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
# Clear any existing handlers to prevent duplicate printing to stdout
if root_logger.hasHandlers():
    root_logger.handlers.clear()
root_logger.addHandler(handler)


asins_to_check = ['0198631014', '0520009274', '3836505150', 'B01FIW4WL2']

def get_current_used_price(product):
    stats = product.get('stats', {})
    current_stats = stats.get('current', [])
    if len(current_stats) > 2 and current_stats[2] is not None:
        return current_stats[2] / 100.0
    return None

def diagnose_asins():
    api_key = os.getenv('KEEPA_API_KEY')
    if not api_key:
        print("ERROR: Could not find KEEPA_API_KEY in environment variables. Cannot diagnose.")
        return

    print("=====================================================================")
    print("                 Diagnostic: True Sales vs Fallbacks                 ")
    print("=====================================================================\n")

    for asin in asins_to_check:
        print(f"--- Checking ASIN: {asin} ---")

        # Clear the log stream for the new ASIN
        log_stream.truncate(0)
        log_stream.seek(0)

        # Manually fetch the product data from Keepa
        url = f"https://api.keepa.com/product?key={api_key}&domain=1&asin={asin}&history=1&stats=1&offers=20"
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            if not data or 'products' not in data or not data['products']:
                print(f"  Failed to fetch data for {asin}.")
                continue

            product = data['products'][0]
            current_used = get_current_used_price(product)

            # Determine how many inferred sales it has
            sale_events, total_drops = infer_sale_events(product)

            # Analyze sales performance
            analysis = analyze_sales_performance(product, sale_events)

            # Extract logs to look for specific messages
            logs = log_stream.getvalue()

            is_suspicious = False
            ratio = None
            ai_responded = None
            ai_checked = False

            for line in logs.split('\n'):
                if 'suspiciously high' in line:
                    is_suspicious = True
                    try:
                        # Extract ratio from string like "Ratio: 9.3x)"
                        ratio_str = line.split('Ratio:')[1].split('x')[0].strip()
                        ratio = float(ratio_str)
                    except:
                        pass
                if "AI responded" in line:
                    ai_checked = True
                    if "yes" in line.lower():
                        ai_responded = "YES (Approved)"
                    elif "no" in line.lower():
                        ai_responded = "NO (Rejected)"

            price_cents = analysis.get('peak_price_mode_cents', -1)
            peak_season = analysis.get('peak_season', 'Unknown')
            list_price_str = f"${price_cents / 100:.2f}" if price_cents > 0 else "REJECTED (-1)"

            # 1. True Sales
            print(f"  1. What it found:")
            print(f"     Found {len(sale_events)} true inferred sales over the last 3 years.")

            # 2. The Math
            print(f"  2. The Math:")
            if price_cents > 0:
                print(f"     During its peak season ({peak_season}), the calculated List At price was {list_price_str}.")
            else:
                print(f"     It failed to find a valid peak season price.")

            # 3. The AI Check
            print(f"  3. The AI Check:")
            if ai_checked:
                if is_suspicious and ratio and current_used:
                    print(f"     Because the price ({list_price_str}) is {ratio}x higher than the current price (${current_used:.2f}), the AI was forced to double-check.")
                else:
                    print(f"     The system ran a standard AI Reasonableness Check.")
                print(f"     The AI said {ai_responded}.")
            else:
                if len(sale_events) < 3 and price_cents > 0:
                     print(f"     The AI check was skipped because it was a Sparse Sales Rescue (too little context).")
                elif price_cents == -1:
                     print(f"     The AI check was not run because the price was already invalid or absurdly high.")
                else:
                     print(f"     The AI check was not executed.")

            # 4. The Result
            print(f"  4. The Result:")
            if len(sale_events) < 3:
                if analysis.get('price_source') == 'Inferred Sales (Sparse)':
                    print(f"     CONCLUSION: This ASIN relied on the Sparse Sales logic (1 or 2 True Inferred Sales). Final Price: {list_price_str}")
                else:
                    print(f"     CONCLUSION: This ASIN was completely rejected. No fallback was used.")
            else:
                print(f"     CONCLUSION: This ASIN had {len(sale_events)} true sales and did not rely on any fallback logic. It is a legitimate high-volume deal. Final Price: {list_price_str}")

            print("\n")

        except Exception as e:
            print(f"  Error checking {asin}: {e}\n")

if __name__ == '__main__':
    diagnose_asins()
