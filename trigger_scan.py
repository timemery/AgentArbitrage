from keepa_deals.Keepa_Deals import run_keepa_script

# The user provided the API key.
api_key = "bg9037ndr2jrlore45acr8a3gustia0tusdfk5e54g1le917nspnk9jiktp7b08b"

# I will set a deal_limit to make the scan run faster for verification purposes.
deal_limit = 20

print("Triggering Keepa scan...")
# I'm calling the task defined in Keepa_Deals.py
run_keepa_script.apply_async(args=[api_key], kwargs={'deal_limit': deal_limit})
print(f"Scan triggered with deal_limit={deal_limit}. Check celery.log for progress.")