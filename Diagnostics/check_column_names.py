import json
import re
import os

def sanitize_col_name(name):
    name = name.replace('%', 'Percent').replace('&', 'and').replace('.', '_')
    name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    name = re.sub(r'__+', '_', name)
    name = name.strip('_')
    return name

with open('keepa_deals/headers.json', 'r') as f:
    headers = json.load(f)

print("Original -> Sanitized")
print("-" * 40)
for h in headers:
    sanitized = sanitize_col_name(h)
    # Print only ones that are different or tricky
    if h != sanitized:
        print(f"'{h}' -> '{sanitized}'")
