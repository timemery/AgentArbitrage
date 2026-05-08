import sqlite3
import json
import re
import uuid
import os
from datetime import datetime, timezone
import math

# Use the DB_PATH from db_utils directly to avoid inconsistencies
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from keepa_deals.db_utils import DB_PATH

def get_hours_since(date_str):
    if not date_str:
        return 0
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        now = datetime.utcnow()
        if dt.tzinfo:
            dt = dt.replace(tzinfo=None)
        delta = now - dt
        return max(0, delta.total_seconds() / 3600.0)
    except ValueError:
        try:
            dt = datetime.strptime(date_str, '%m/%d/%y %H:%M')
            now = datetime.utcnow()
            delta = now - dt
            return max(0, delta.total_seconds() / 3600.0)
        except ValueError:
            return 0

def parse_offers(offers_str):
    if not offers_str or offers_str == '-': return 0
    m = re.search(r'(\d+)', str(offers_str))
    if m:
        return int(m.group(1))
    return 0

def fetch_all_deals():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        deal_rows = cursor.execute("SELECT * FROM deals").fetchall()
        return [dict(row) for row in deal_rows]

def fetch_current_prime_picks():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            rows = cursor.execute("SELECT * FROM prime_picks ORDER BY rank ASC").fetchall()
            return [dict(row) for row in rows]
    except sqlite3.OperationalError:
        return []

def score_deals(deals_list):
    for deal in deals_list:
        profit_str = str(deal.get('Profit', '0')).replace('$', '').replace(',', '')
        cost_str = str(deal.get('All_in_Cost', '0')).replace('$', '').replace(',', '')
        try:
            profit = float(profit_str)
            cost = float(cost_str)
            roi = (profit / cost) * 100 if cost > 0 else 0
        except ValueError:
            profit = 0
            cost = 0
            roi = 0

        deal['_parsed_profit'] = profit
        deal['_parsed_cost'] = cost
        deal['_parsed_roi'] = roi

        # Use Profit_Confidence as fallback if Deal_Trust is not found
        trust_str = str(deal.get('Deal_Trust') or deal.get('Profit_Confidence') or '0').replace('%', '')
        try:
            deal['_parsed_trust'] = float(trust_str)
        except ValueError:
            deal['_parsed_trust'] = 0

        list_at_str = str(deal.get('List_at', '0')).replace('$', '').replace(',', '')
        try:
            deal['_parsed_list_at'] = float(list_at_str)
        except ValueError:
            deal['_parsed_list_at'] = 0

        hours_since = get_hours_since(deal.get('last_seen_utc') or deal.get('Deal_found'))

        sales_rank = deal.get('Sales_Rank___Current')
        if sales_rank is None or sales_rank == '':
            sales_rank = 1000000
        else:
            try:
                sales_rank = float(str(sales_rank).replace(',', ''))
            except ValueError:
                sales_rank = 1000000

        deal['_parsed_sales_rank'] = sales_rank

        offers = parse_offers(deal.get('New_Offer_Count___Current') or deal.get('Used_Offer_Count___Current'))
        deal['_parsed_offers'] = offers

        base_half_life = 24 + (sales_rank / 2000000.0) * 144
        final_half_life = base_half_life * (1 - min(0.5, offers * 0.02))

        score = (profit * roi) * (0.5 ** (hours_since / max(0.001, final_half_life)))
        deal['_score'] = score

    return deals_list

def run_filter(deals_list, min_profit, min_roi, max_roi, min_trust, max_list_at):
    filtered = []
    for d in deals_list:
        # Require 1yr_Avg condition as in prime_picks_task
        yr_avg = d.get('1yr_Avg')
        if not yr_avg or yr_avg in ('-', 'N/A', '', '0', '0.00', '$0.00'):
            continue
        try:
            yr_avg_val = float(str(yr_avg).replace('$', '').replace(',', ''))
            if yr_avg_val == 0:
                continue
        except ValueError:
            continue

        if (d['_parsed_profit'] >= min_profit and
            d['_parsed_cost'] > 0 and
            min_roi <= d['_parsed_roi'] <= max_roi and
            d['_parsed_trust'] >= min_trust and
            d.get('List_at') is not None and
            0 < d['_parsed_list_at'] <= max_list_at):
            filtered.append(d)
    return filtered

def find_near_misses(deals_list, min_profit, min_roi, max_roi, min_trust, max_list_at):
    near_misses = []
    for d in deals_list:
        # Base requirements (always must pass)
        yr_avg = d.get('1yr_Avg')
        if not yr_avg or yr_avg in ('-', 'N/A', '', '0', '0.00', '$0.00'):
            continue
        try:
            yr_avg_val = float(str(yr_avg).replace('$', '').replace(',', ''))
            if yr_avg_val == 0:
                continue
        except ValueError:
            continue

        if d['_parsed_cost'] <= 0 or d.get('List_at') is None or d['_parsed_list_at'] <= 0:
            continue

        failures = []
        if d['_parsed_profit'] < min_profit:
            failures.append(f"Profit ({d['_parsed_profit']:.2f} < {min_profit})")
        if not (min_roi <= d['_parsed_roi'] <= max_roi):
            failures.append(f"ROI ({d['_parsed_roi']:.2f}% outside {min_roi}-{max_roi}%)")
        if d['_parsed_trust'] < min_trust:
            failures.append(f"Trust ({d['_parsed_trust']:.2f} < {min_trust})")
        if d['_parsed_list_at'] > max_list_at:
            failures.append(f"List_At ({d['_parsed_list_at']:.2f} > {max_list_at})")

        if len(failures) == 1:
            near_misses.append({
                'deal': d,
                'failure': failures[0]
            })

    # Sort near misses by score descending
    near_misses.sort(key=lambda x: x['deal']['_score'], reverse=True)
    return near_misses[:10]

def main():
    print("=== Prime Picks Tuning Diagnostic ===")

    all_deals = fetch_all_deals()
    all_deals = score_deals(all_deals)

    # Run Current Pass 1
    current_pass1 = run_filter(all_deals, min_profit=10, min_roi=15, max_roi=300, min_trust=40, max_list_at=1500)
    current_pass1.sort(key=lambda x: x['_score'], reverse=True)
    top_20 = current_pass1[:20]
    top_20_asins = [d['ASIN'] for d in top_20]

    print(f"\nTotal Deals in DB: {len(all_deals)}")
    print(f"Deals passing current Pass 1 filter: {len(current_pass1)}")

    print("\n--- 1. Current Picks Deep-Dive ---")
    current_picks = fetch_current_prime_picks()
    if not current_picks:
        print("No cached Prime Picks found in DB.")
    else:
        for pick in current_picks:
            asin = pick['asin']
            deal = next((d for d in all_deals if d['ASIN'] == asin), None)
            if deal:
                # Find Pass 1 rank
                pass1_rank = "N/A (not in top 20)"
                if asin in top_20_asins:
                    pass1_rank = top_20_asins.index(asin) + 1

                print(f"\nASIN: {asin} (Cache Rank: {pick['rank']})")
                print(f"  Title: {deal.get('Title', '')[:50]}...")
                print(f"  Pass 1 Rank: {pass1_rank}")
                print(f"  Score: {deal['_score']:.2f}")
                print(f"  Profit: ${deal['_parsed_profit']:.2f}")
                print(f"  ROI: {deal['_parsed_roi']:.2f}%")
                print(f"  Deal_Trust: {deal['_parsed_trust']}%")
                print(f"  List_At: ${deal['_parsed_list_at']:.2f}")
                print(f"  Sales Rank: {deal['_parsed_sales_rank']}")
                print(f"  Offer Count: {deal['_parsed_offers']}")
                print(f"  Seasonality: {deal.get('Detailed_Seasonality', 'N/A')}")
            else:
                print(f"ASIN: {asin} - Deal details not found in current deals table.")

    print("\n--- 2. Near-Miss Analysis ---")
    near_misses = find_near_misses(all_deals, min_profit=10, min_roi=15, max_roi=300, min_trust=40, max_list_at=1500)
    if not near_misses:
        print("No near misses found.")
    else:
        for nm in near_misses:
            d = nm['deal']
            print(f"ASIN: {d['ASIN']} | Score: {d['_score']:.2f} | Failed on: {nm['failure']}")
            print(f"  (Profit: ${d['_parsed_profit']:.2f}, ROI: {d['_parsed_roi']:.2f}%, Trust: {d['_parsed_trust']}%, List: ${d['_parsed_list_at']:.2f})")

    print("\n--- 3. Pass 2 Selection Ratio ---")
    # Parse celery worker log to try to find the xAI selection info if possible
    # This is a bit hacky but read-only and requested
    try:
        if os.path.exists('celery_worker.log'):
            with open('celery_worker.log', 'r') as f:
                lines = f.readlines()
                # reverse read to find latest run
                lines.reverse()
                found_run = False
                for line in lines:
                    if "Pass 2 complete. Selected" in line:
                        print(f"Latest xAI log: {line.strip()}")
                        found_run = True
                        break
                    elif "xAI API returned an error" in line or "Failed to parse xAI output" in line:
                        print(f"xAI Error log: {line.strip()}")
                        found_run = True
                        break
                if not found_run:
                    print("Could not find xAI selection logs in recent celery_worker.log.")
        else:
            print("celery_worker.log not found.")
    except Exception as e:
         print(f"Error reading logs: {e}")

    cached_picks_count = len(current_picks)
    print(f"Currently cached picks: {cached_picks_count}")
    print(f"Selection ratio: {cached_picks_count}/20 ({cached_picks_count/20.0*100:.1f}%)" if top_20 else "N/A")

    print("\n--- 4. Threshold Sensitivity Simulation ---")
    scenarios = [
        ("Current",      10, 15, 300, 40, 1500),
        ("Tightened A",  15, 20, 300, 50, 500),
        ("Tightened B",  20, 25, 300, 60, 300),
        ("Loosened",      5, 10, 300, 30, 1500)
    ]

    for name, min_p, min_r, max_r, min_t, max_l in scenarios:
        res = run_filter(all_deals, min_p, min_r, max_r, min_t, max_l)
        res.sort(key=lambda x: x['_score'], reverse=True)
        print(f"\nScenario: {name}")
        print(f"  Criteria: Profit>={min_p}, ROI {min_r}-{max_r}%, Trust>={min_t}, List<={max_l}")
        print(f"  Total Qualifying: {len(res)}")
        print("  Top 5:")
        for i, d in enumerate(res[:5]):
            print(f"    {i+1}. ASIN: {d['ASIN']} | Score: {d['_score']:.2f} | Profit: ${d['_parsed_profit']:.2f} | ROI: {d['_parsed_roi']:.2f}% | Trust: {d['_parsed_trust']}%")

    print("\n--- 5. Top-of-Pool Analysis ---")
    if len(current_pass1) > 20:
        pool_remainder = current_pass1[20:]
        print(f"Remaining candidates in Pass 1 pool: {len(pool_remainder)}")
        scores = [d['_score'] for d in pool_remainder]
        if scores:
            print(f"  Max Score (Rank 21): {scores[0]:.2f}")
            print(f"  Min Score: {scores[-1]:.2f}")
            print(f"  Median Score: {scores[len(scores)//2]:.2f}")
            print(f"  Mean Score: {sum(scores)/len(scores):.2f}")

            # Show a few top items that didn't make it to Pass 2
            print("\n  Top 3 that missed the top 20 cutoff:")
            for i, d in enumerate(pool_remainder[:3]):
                 print(f"    Rank {21+i}. ASIN: {d['ASIN']} | Score: {d['_score']:.2f} | Profit: ${d['_parsed_profit']:.2f} | ROI: {d['_parsed_roi']:.2f}%")
        else:
            print("  Scores array empty.")
    else:
        print("Pass 1 pool had 20 or fewer candidates. No remainder to analyze.")

if __name__ == '__main__':
    main()

# Added print completion to make script clean output
print("\nDone.")
