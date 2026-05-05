import re

def parse_offers(offers_str):
    if not offers_str or offers_str == '-': return 0
    # format might be "15 ↘" or "15 ↗" or "15 ⇨" or just "15"
    m = re.search(r'(\d+)', str(offers_str))
    if m:
        return int(m.group(1))
    return 0

print(parse_offers("15 ↘"))
print(parse_offers(" 15 "))
print(parse_offers(None))
print(parse_offers("-"))
