import json

def analyze_product_data(file_path):
    """
    Parses the raw product data file to validate the hypothesis that
    'Used - Current' price in stats matches the lowest-priced 'Used' offer.
    """
    with open(file_path, 'r') as f:
        content = f.read()

    # Split the content into individual JSON objects for each product
    # This is a bit brittle, but works for the current file format.
    json_strs = [line.strip() for line in content.split('|') if line.strip().startswith('{"asin"')]

    if not json_strs:
        print("No product data found in the file.")
        return

    for i, json_str in enumerate(json_strs):
        try:
            # The last character might be a dangling '}', so we fix it if needed
            if not json_str.endswith('}'):
                json_str += '}'
            product = json.loads(json_str)
            asin = product.get('asin')
            print(f"--- Analyzing ASIN: {asin} ---")

            # 1. Get the 'Used - Current' price from the stats (csv)
            # The second array (index 1) is USED price history.
            # The history is in pairs [timestamp, price], so we take every second element.
            used_prices = product.get('csv', [])[1][1::2] if len(product.get('csv', [])) > 1 else []
            if not used_prices or used_prices[-1] == -1:
                print("  'Used - Current' price not available in stats.")
                continue
            stats_used_price = used_prices[-1]
            print(f"  Stats 'Used - Current' Price: {stats_used_price / 100:.2f}")

            # 2. Find the minimum price from the 'offers' array for 'Used' conditions
            min_offer_price = float('inf')
            lowest_offer = None
            used_offers_found = False

            # Condition codes for 'Used': 2, 3, 4, 5
            # From seller_info.py: {2: 'Used - Like New', 3: 'Used - Very Good', 4: 'Used - Good', 5: 'Used - Acceptable'}
            used_condition_codes = {2, 3, 4, 5}

            for offer in product.get('offers', []):
                # The 'condition' can be an integer or a dictionary
                condition_val = offer.get('condition')
                if isinstance(condition_val, dict):
                    condition_code = condition_val.get('value')
                else:
                    condition_code = condition_val

                if condition_code in used_condition_codes:
                    used_offers_found = True
                    price = offer.get('price', 0)
                    shipping_cost = offer.get('shippingCost', 0)
                    total_price = price + shipping_cost

                    if total_price < min_offer_price:
                        min_offer_price = total_price
                        lowest_offer = offer

            if not used_offers_found:
                print("  No 'Used' condition offers found in the 'offers' array.")
                continue

            print(f"  Lowest Priced 'Used' Offer: {min_offer_price / 100:.2f}")
            if lowest_offer:
                 print(f"     - Seller ID: {lowest_offer.get('sellerId')}")
                 print(f"     - Condition: {lowest_offer.get('condition')}")


            # 3. Compare and conclude
            if stats_used_price == min_offer_price:
                print("  ✅ HYPOTHESIS CONFIRMED: The prices match.")
            else:
                print("  ❌ HYPOTHESIS FALSE: The prices DO NOT match.")
            print("-" * 30)

        except json.JSONDecodeError as e:
            print(f"Error decoding JSON for product {i+1}: {e}")
        except Exception as e:
            print(f"An unexpected error occurred for product {i+1}: {e}")


if __name__ == "__main__":
    analyze_product_data('Documents_Dev_Logs/RAW_PRODUCT_DATA.md')
