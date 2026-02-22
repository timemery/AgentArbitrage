
import csv
import io

# Exact content from user diagnostic output (replacing visual tabs with \t where obvious)
# Note: The diagnostic output had "mfn-fulfillable-quantitafn-listing-exists".
# This suggests a missing tab between "mfn-fulfillable-quantity" and "afn-listing-exists".
# Or maybe the column name is just truncated/mangled in the preview?
# Let's try to parse the header string provided.

raw_header = "sku\tfnsku\tasin\tproduct-name\tcondition\tyour-price\tmfn-listing-exists\tmfn-fulfillable-quantitafn-listing-exists\tafn-warehouse-quantity\tafn-fulfillable-quantity\tafn-unsellable-quantity\tafn-reserved-quantity\tafn-total-quantity\tper-unit-volume\tafn-inbound-working-quantity\tafn-inbound-shipped-quantity\tafn-inbound-receiving-quantity\tafn-researching-quantity\tafn-reserved-future-supply\tafn-future-supply-buyable\tstore"

raw_row_1 = "TXT-012324-0005\tX00441RV0J\t1133310699\tPlays for the Theatre, Enhanced\tUsedGood\t16.99\tNo\t\tYes\t0\t0\t0\t0\t0\t0.03\t0\t0\t0\t0\t0\t0\t"
raw_row_2 = "TXT-012324-0007\tX004424Q6Z\t0131899058\tImperialism in the Modern World\tUsedGood\t18.99\tNo\t\tYes\t1\t1\t0\t0\t1\t0.02\t0\t0\t0\t0\t0\t0\t"

# Construct TSV content
tsv_content = f"{raw_header}\n{raw_row_1}\n{raw_row_2}"

print("--- Parsing Simulation ---")
try:
    reader = csv.DictReader(io.StringIO(tsv_content), delimiter='\t')
    print(f"Detected Fields: {reader.fieldnames}")

    print("\nRows:")
    for row in reader:
        print(f"SKU: {row.get('sku')}")

        # Check for the critical column
        qty_key = 'afn-fulfillable-quantity'
        if qty_key in row:
            print(f"  {qty_key}: {row[qty_key]}")
        else:
            print(f"  MISSING KEY: {qty_key}")
            # Try to find what it might be called
            for k in row.keys():
                if 'afn' in k and 'fulfillable' in k:
                    print(f"  Found similar key: '{k}' -> {row[k]}")

except Exception as e:
    print(f"Parsing Error: {e}")
