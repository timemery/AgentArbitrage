import sqlite3
import re
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from keepa_deals.db_utils import DB_PATH
import os
import sys
from keepa_deals.db_utils import get_db_connection

def extract_code_constants():
    # Extract constants from keepa_deals/prime_picks_task.py
    constants = {}

    # Defaults in case not found
    constants['profit_min'] = None
    constants['roi_min'] = None
    constants['roi_max'] = None
    constants['deal_trust_min'] = None
    constants['list_at_max'] = None

    try:
        # Find the path dynamically
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        file_path = os.path.join(base_dir, 'keepa_deals', 'prime_picks_task.py')

        with open(file_path, 'r') as f:
            content = f.read()

            # Use regex to find thresholds, accommodating possible spaces and formatting

            # Profit
            match = re.search(r'\{sanitized_profit\}\s*>=\s*(\d+)', content)
            if match:
                constants['profit_min'] = float(match.group(1))

            # ROI min
            match = re.search(r'\{roi_expr\}\s*>=\s*(\d+)', content)
            if match:
                constants['roi_min'] = float(match.group(1))

            # ROI max
            match = re.search(r'\{roi_expr\}\s*<=\s*(\d+)', content)
            if match:
                constants['roi_max'] = float(match.group(1))

            # Deal Trust
            match = re.search(r'Deal_Trust.*?>=.*?(\d+)', content)
            if match:
                constants['deal_trust_min'] = float(match.group(1))

            # List At
            match = re.search(r'\{sanitized_list_at\}\s*<=\s*(\d+)', content)
            if match:
                constants['list_at_max'] = float(match.group(1))
    except Exception as e:
        print(f"Error reading prime_picks_task.py: {e}")
    return constants

def main():
    print("="*50)
    print("PRIME PICKS FUNNEL DIAGNOSTIC REPORT")
    print("="*50)

    # ---------------------------------------------------------
    # Connect to Database
    # ---------------------------------------------------------
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        sys.exit(1)

    try:
        conn = get_db_connection(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
    except Exception as e:
        print(f"Error connecting to database: {e}")
        sys.exit(1)

    # ---------------------------------------------------------
    # Stage 0: Total deals in DB
    # ---------------------------------------------------------
    print("\n--- Stage 0: Data Context ---")

    # Total deals
    try:
        cursor.execute("SELECT COUNT(*) FROM deals")
        total_deals = cursor.fetchone()[0]
    except sqlite3.OperationalError as e:
        print(f"Error querying deals table: {e}")
        total_deals = 0

    # Post-display filters - based on wsgi_handler.py API logic
    # Must filter out zero cost to avoid division by zero when calculating ROI
    try:
        base_query = """
        SELECT * FROM deals
        WHERE CAST(REPLACE(REPLACE("All_in_Cost", '$', ''), ',', '') AS REAL) > 0
        """
        all_deals = cursor.execute(base_query).fetchall()
        displayed_deals = len(all_deals)
    except sqlite3.OperationalError as e:
        print(f"Error executing base query: {e}")
        all_deals = []
        displayed_deals = 0

    print(f"Total deals in `deals` table: {total_deals}")
    print(f"Of those, displayed on dashboard (post-display filters): {displayed_deals}")

    # ---------------------------------------------------------
    # Stage 3: Code Constants
    # ---------------------------------------------------------
    print("\n--- Stage 3: Code Analysis ---")
    constants = extract_code_constants()

    p_min = constants.get('profit_min')
    r_min = constants.get('roi_min')
    r_max = constants.get('roi_max')
    t_min = constants.get('deal_trust_min')
    l_max = constants.get('list_at_max')

    print("Active thresholds in code:")
    print(f"  Profit minimum:    {p_min if p_min is not None else 'N/A'}")
    print(f"  ROI range:         {r_min if r_min is not None else 'N/A'}% - {r_max if r_max is not None else 'N/A'}%")
    print(f"  Deal_Trust min:    {t_min if t_min is not None else 'N/A'}")
    print(f"  List_At max:       {l_max if l_max is not None else 'N/A'}")

    spec_mismatch = False
    if p_min != 15 or r_min != 30 or r_max != 300 or t_min != 70 or l_max != 1500:
        spec_mismatch = True

    if spec_mismatch:
        print("\n⚠️  WARNING: Production thresholds differ from spec!")
        print("    Spec:  Profit >= 15, ROI 30-300%, Deal_Trust >= 70, List_At <= 1500")
        print(f"    Code:  Profit >= {p_min}, ROI {r_min}-{r_max}%, Deal_Trust >= {t_min}, List_At <= {l_max}")

    # Fallback to spec values if constants couldn't be extracted
    p_min = p_min if p_min is not None else 15
    r_min = r_min if r_min is not None else 30
    r_max = r_max if r_max is not None else 300
    t_min = t_min if t_min is not None else 70
    l_max = l_max if l_max is not None else 1500

    # ---------------------------------------------------------
    # Stage 1: Pass 1 Smart Floor breakdown
    # ---------------------------------------------------------
    print("\n--- Stage 1: Smart Floor Baseline Filters ---")

    profit_pass = 0
    profit_fail = 0
    roi_pass = 0
    roi_low_fail = 0
    roi_high_fail = 0
    trust_pass = 0
    trust_fail = 0
    list_at_pass = 0
    list_at_fail = 0

    all_pass = 0
    candidates = []
    rejected_deals = []

    # Store metrics for Stage 5
    metrics = {
        'profit': [],
        'roi': [],
        'trust': [],
        'list_at': []
    }

    for row in all_deals:
        d = dict(row)

        # Parse metrics safely
        try:
            profit_str = str(d.get('Profit', '0')).replace('$', '').replace(',', '')
            profit = float(profit_str) if profit_str else 0
        except ValueError:
            profit = 0

        try:
            cost_str = str(d.get('All_in_Cost', '0')).replace('$', '').replace(',', '')
            cost = float(cost_str) if cost_str else 0
            roi = (profit / cost) * 100 if cost > 0 else 0
        except ValueError:
            roi = 0

        try:
            trust_str = str(d.get('Deal_Trust', '0')).replace('%', '')
            trust = float(trust_str) if trust_str else 0
        except ValueError:
            trust = 0

        try:
            list_at_str = str(d.get('List_at', '0')).replace('$', '').replace(',', '')
            list_at = float(list_at_str) if list_at_str and list_at_str not in ('-', 'N/A', '') else 0
        except ValueError:
            list_at = 0

        # Record for Stage 5
        metrics['profit'].append(profit)
        metrics['roi'].append(roi)
        metrics['trust'].append(trust)
        if list_at > 0:
            metrics['list_at'].append(list_at)

        # Check filters individually
        pass_p = profit >= p_min
        if pass_p: profit_pass += 1
        else: profit_fail += 1

        pass_r = r_min <= roi <= r_max
        if pass_r: roi_pass += 1
        elif roi < r_min: roi_low_fail += 1
        elif roi > r_max: roi_high_fail += 1

        pass_t = trust >= t_min
        if pass_t: trust_pass += 1
        else: trust_fail += 1

        has_valid_list_at = d.get('List_at') is not None and list_at > 0
        pass_l = has_valid_list_at and list_at <= l_max
        if pass_l: list_at_pass += 1
        else: list_at_fail += 1

        # Must also meet these extra conditions from code
        avg_valid = d.get('1yr_Avg') is not None and str(d.get('1yr_Avg')) not in ('-', 'N/A', '', '0', '0.00', '$0.00')
        try:
            avg_val = float(str(d.get('1yr_Avg', '0')).replace('$', '').replace(',', ''))
            pass_avg = avg_val != 0 and avg_valid
        except ValueError:
            pass_avg = False

        if pass_p and pass_r and pass_t and pass_l and pass_avg:
            all_pass += 1
            candidates.append(d)
        else:
            rejected_deals.append({
                'asin': d.get('ASIN', 'Unknown'),
                'profit': profit,
                'pass_p': pass_p,
                'roi': roi,
                'pass_r': pass_r,
                'roi_err': 'low' if roi < r_min else ('high' if roi > r_max else ''),
                'trust': trust,
                'pass_t': pass_t,
                'list_at': list_at,
                'pass_l': pass_l
            })

    print(f"Profit >= {p_min}:           {profit_pass} pass / {profit_fail} fail")
    print(f"ROI between {r_min}% and {r_max}%: {roi_pass} pass / {roi_low_fail + roi_high_fail} fail   (and: {roi_low_fail} fail for ROI < {r_min}%, {roi_high_fail} fail for ROI > {r_max}%)")
    print(f"Deal_Trust >= {t_min}:       {trust_pass} pass / {trust_fail} fail")
    print(f"List_At <= {l_max}:        {list_at_pass} pass / {list_at_fail} fail")
    print(f"\nDeals passing ALL Pass 1 baselines: {all_pass}")

    # ---------------------------------------------------------
    # Stage 2: Pass 1 scoring & top-20 selection
    # ---------------------------------------------------------
    print("\n--- Stage 2: Scoring & Top Selection ---")

    # Simple scoring logic mirroring prime_picks_task.py
    for deal in candidates:
        profit_str = str(deal.get('Profit', '0')).replace('$', '').replace(',', '')
        cost_str = str(deal.get('All_in_Cost', '0')).replace('$', '').replace(',', '')
        try:
            profit = float(profit_str)
            cost = float(cost_str)
            roi = (profit / cost) * 100 if cost > 0 else 0
        except ValueError:
            profit = 0
            roi = 0

        # Calculate hours since
        hours_since = 0
        date_str = deal.get('last_seen_utc') or deal.get('Deal_found')
        if date_str:
            from datetime import datetime
            try:
                dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
                now = datetime.utcnow()
                if dt.tzinfo:
                    dt = dt.replace(tzinfo=None)
                delta = now - dt
                hours_since = max(0, delta.total_seconds() / 3600.0)
            except ValueError:
                pass

        sales_rank = deal.get('Sales_Rank_Current')
        if sales_rank is None or sales_rank == '':
            sales_rank = 1000000
        else:
            try:
                sales_rank = float(str(sales_rank).replace(',', ''))
            except ValueError:
                sales_rank = 1000000

        offers_str = deal.get('Offers')
        offers = 0
        if offers_str and offers_str != '-':
            m = re.search(r'(\d+)', str(offers_str))
            if m:
                offers = int(m.group(1))

        base_half_life = 24 + (sales_rank / 2000000.0) * 144
        final_half_life = base_half_life * (1 - min(0.5, offers * 0.02))

        score = (profit * roi) * (0.5 ** (hours_since / max(0.001, final_half_life)))
        deal['_score'] = score

    # Sort
    candidates.sort(key=lambda x: x.get('_score', 0), reverse=True)
    top_20 = candidates[:20]

    print(f"Candidates after baselines: {len(candidates)}")
    print(f"Top 20 selected by Time Decay score: {len(top_20)}")

    if top_20:
        print(f"Top candidate score: {top_20[0]['_score']:.2f}")
        last_idx = len(top_20) - 1
        print(f"{len(top_20)}th candidate score: {top_20[last_idx]['_score']:.2f}")
    else:
        print("Top candidate score: n/a")
        print("20th candidate score: n/a")

    # ---------------------------------------------------------
    # Stage 4: Sample rejected deals
    # ---------------------------------------------------------
    print("\n--- Stage 4: Sample Rejected Deals ---")
    import random

    samples = rejected_deals[:5] if len(rejected_deals) <= 5 else random.sample(rejected_deals, 5)

    for r in samples:
        p_str = "pass" if r['pass_p'] else "FAIL profit"

        if r['pass_r']: r_str = "pass"
        elif r['roi_err'] == 'low': r_str = "FAIL roi_low"
        else: r_str = "FAIL roi_high"

        t_str = "pass" if r['pass_t'] else "FAIL trust"
        l_str = "pass" if r['pass_l'] else "FAIL list_at"

        print(f"ASIN {r['asin']}: Profit=${r['profit']:.2f} ({p_str}), ROI={r['roi']:.1f}% ({r_str}), Deal_Trust={r['trust']:.1f} ({t_str}), List_At=${r['list_at']:.2f} ({l_str})")

    # ---------------------------------------------------------
    # Stage 5: Distribution summary
    # ---------------------------------------------------------
    print("\n--- Stage 5: Distribution summary ---")

    def get_stats(data):
        if not data:
            return None, None, None
        data_sorted = sorted(data)
        n = len(data_sorted)
        minimum = data_sorted[0]
        maximum = data_sorted[-1]
        median = data_sorted[n//2] if n % 2 != 0 else (data_sorted[n//2 - 1] + data_sorted[n//2]) / 2.0
        return minimum, median, maximum

    p_min_val, p_med, p_max_val = get_stats(metrics['profit'])
    r_min_val, r_med, r_max_val = get_stats(metrics['roi'])
    t_min_val, t_med, t_max_val = get_stats(metrics['trust'])
    l_min_val, l_med, l_max_val = get_stats(metrics['list_at'])

    def fmt_val(v, prefix='', suffix=''):
        return f"{prefix}{v:.2f}{suffix}" if v is not None else "N/A"

    def fmt_val_1f(v, prefix='', suffix=''):
        return f"{prefix}{v:.1f}{suffix}" if v is not None else "N/A"

    print(f"Profit:     min={fmt_val(p_min_val, '$')}, median={fmt_val(p_med, '$')}, max={fmt_val(p_max_val, '$')}")
    print(f"ROI:        min={fmt_val_1f(r_min_val, suffix='%')}, median={fmt_val_1f(r_med, suffix='%')}, max={fmt_val_1f(r_max_val, suffix='%')}")
    print(f"Deal_Trust: min={fmt_val_1f(t_min_val)}, median={fmt_val_1f(t_med)}, max={fmt_val_1f(t_max_val)}")
    print(f"List_At:    min={fmt_val(l_min_val, '$')}, median={fmt_val(l_med, '$')}, max={fmt_val(l_max_val, '$')}")
    print("="*50)

if __name__ == "__main__":
    main()


if 'conn' in locals() and conn:
    try:
        conn.close()
    except Exception:
        pass