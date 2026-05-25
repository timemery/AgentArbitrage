import re

with open('templates/tracking.html', 'r') as f:
    content = f.read()

# Render Potential
pot_match = re.search(r'(let html = \'<div class="table-container"><table class="deal-table" style="width:100%"><thead><tr class="column-header-row">.*?)</tr></thead><tbody>\';', content, re.DOTALL)
if pot_match and "generateSortArrows" not in pot_match.group(0):
    replacement = pot_match.group(1) + "</tr>' + generateSortArrows('potential', [{id:'title'}, {id:'asin'}, {id:'buy_cost'}, {id:'created_at'}, {id:'profit'}, {id:'roi'}, {id:'margin'}, {}]) + '</thead><tbody>';"
    content = content.replace(pot_match.group(0), replacement)

# Render Active
act_match = re.search(r'(let html = \'<div class="table-container"><table class="deal-table" style="width:100%"><thead><tr class="column-header-row">.*?)</tr></thead><tbody>\';', content, re.DOTALL)
if act_match and "generateSortArrows" not in act_match.group(0):
    replacement = act_match.group(1) + "</tr>' + generateSortArrows('active', [{id:'asin'}, {id:'sku'}, {id:'title'}, {id:'quantity_remaining'}, {id:'buy_cost'}, {}]) + '</thead><tbody>';"
    content = content.replace(act_match.group(0), replacement)

# Render Sales
sal_match = re.search(r'(let html = \'<div class="table-container"><table class="deal-table" style="width:100%"><thead><tr class="column-header-row">.*?)</tr></thead><tbody>\';', content, re.DOTALL)
if sal_match and "generateSortArrows" not in sal_match.group(0):
    replacement = sal_match.group(1) + "</tr>' + generateSortArrows('sales', [{id:'sale_date'}, {id:'amazon_order_id'}, {id:'sku'}, {id:'sale_price'}, {id:'order_status'}]) + '</thead><tbody>';"
    content = content.replace(sal_match.group(0), replacement)

with open('templates/tracking.html', 'w') as f:
    f.write(content)
