import json

payload = '{\n"asins": ["0123456789"]\n}'
try:
    parsed = json.loads(payload)
    if isinstance(parsed, list):
        print([str(x) for x in parsed])
    elif isinstance(parsed, dict) and "asins" in parsed:
        print([str(x) for x in parsed["asins"]])
except Exception as e:
    print(e)
