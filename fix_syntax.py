with open("keepa_deals/Keepa_Deals.py", "r") as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.strip() == "from keepa_deals.db_utils import get_db_connection":
        continue
    new_lines.append(line)

new_lines.insert(20, "from keepa_deals.db_utils import get_db_connection\n")

with open("keepa_deals/Keepa_Deals.py", "w") as f:
    f.writelines(new_lines)
