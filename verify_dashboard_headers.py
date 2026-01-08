import re

def verify_headers():
    with open('templates/dashboard.html', 'r') as f:
        content = f.read()

    # Define expected mappings
    expected_mappings = {
        '"last_price_change": "Ago"': True,
        '"1yr_Avg": "1yr Avg"': True,
        '"Seller_Quality_Score": "Seller"': True,
        '"Sales_Rank_Current": "Rank"': True,
        '"Profit_Confidence": "Estimate"': True,
        '"All_in_Cost": "All in"': True,
        '"Best_Price": "Now"': True
    }

    # Define expected group headers
    expected_groups = [
        '<th colspan="3">Book Details</th>',
        '<th colspan="4">Supply & Demand</th>',
        '<th colspan="1">Trust Ratings</th>',
        '<th colspan="5">Deal Details</th>',
        '<th colspan="6">Profit Estimates</th>'
    ]

    # Verify Mappings
    print("Verifying Column Header Mappings...")
    for mapping, required in expected_mappings.items():
        if mapping in content:
            print(f"✅ Found mapping: {mapping}")
        else:
            print(f"❌ Missing mapping: {mapping}")
            exit(1)

    # Verify Group Headers
    print("\nVerifying Group Headers...")
    for group in expected_groups:
        if group in content:
            print(f"✅ Found group header: {group}")
        else:
            print(f"❌ Missing group header: {group}")
            exit(1)

    print("\nAll verifications passed!")

if __name__ == "__main__":
    verify_headers()
