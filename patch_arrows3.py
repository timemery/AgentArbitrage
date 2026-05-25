with open('templates/tracking.html', 'r') as f:
    content = f.read()

# Render Potential
content = content.replace(
    'let html = \'<div class="table-container"><table class="deal-table" style="width:100%"><thead><tr class="column-header-row"><th>Title</th><th>ASIN</th><th><div class="tooltip-header">Buy Cost ℹ️<span class="tooltip-text">Click to edit. Italic = estimated from Dashboard. Solid = you confirmed the actual Amazon price.</span></div></th><th>Date</th><th>Profit</th><th>ROI</th><th>Margin</th><th>Actions</th></tr></thead><tbody>\';',
    'let html = \'<div class="table-container"><table class="deal-table" style="width:100%"><thead><tr class="column-header-row"><th>Title</th><th>ASIN</th><th><div class="tooltip-header">Buy Cost ℹ️<span class="tooltip-text">Click to edit. Italic = estimated from Dashboard. Solid = you confirmed the actual Amazon price.</span></div></th><th>Date</th><th>Profit</th><th>ROI</th><th>Margin</th><th>Actions</th></tr>\' + generateSortArrows(\'potential\', [{id:\'title\'}, {id:\'asin\'}, {id:\'buy_cost\'}, {id:\'created_at\'}, {id:\'profit\'}, {id:\'roi\'}, {id:\'margin\'}, {}]) + \'</thead><tbody>\';'
)

# Render Active
content = content.replace(
    'let html = \'<div class="table-container"><table class="deal-table" style="width:100%"><thead><tr class="column-header-row"><th>ASIN</th><th>SKU</th><th>Title</th><th><div class="tooltip-header">Qty ℹ️<span class="tooltip-text">Includes Active (Fulfillable) & Inbound (Working/Shipped) Inventory</span></div></th><th>Cost</th><th>Actions</th></tr></thead><tbody>\';',
    'let html = \'<div class="table-container"><table class="deal-table" style="width:100%"><thead><tr class="column-header-row"><th>ASIN</th><th>SKU</th><th>Title</th><th><div class="tooltip-header">Qty ℹ️<span class="tooltip-text">Includes Active (Fulfillable) & Inbound (Working/Shipped) Inventory</span></div></th><th>Cost</th><th>Actions</th></tr>\' + generateSortArrows(\'active\', [{id:\'asin\'}, {id:\'sku\'}, {id:\'title\'}, {id:\'quantity_remaining\'}, {id:\'buy_cost\'}, {}]) + \'</thead><tbody>\';'
)

# Clean up any bad state from regex replace
content = content.replace(
    "let html = '<div class=\"table-container\"><table class=\"deal-table\" style=\"width:100%\"><thead><tr class=\"column-header-row\"><th>Date</th><th>Order ID</th><th>SKU</th><th><div class=\"tooltip-header\">Sale Price (Gross) ℹ️<span class=\"tooltip-text\">Excludes Amazon Fees (Customer Paid Price)</span></div></th><th>Status</th></tr>' + generateSortArrows('potential', [{id:'title'}, {id:'asin'}, {id:'buy_cost'}, {id:'created_at'}, {id:'profit'}, {id:'roi'}, {id:'margin'}, {}]) + '</thead><tbody>';",
    "let html = '<div class=\"table-container\"><table class=\"deal-table\" style=\"width:100%\"><thead><tr class=\"column-header-row\"><th>Date</th><th>Order ID</th><th>SKU</th><th><div class=\"tooltip-header\">Sale Price (Gross) ℹ️<span class=\"tooltip-text\">Excludes Amazon Fees (Customer Paid Price)</span></div></th><th>Status</th></tr>' + generateSortArrows('sales', [{id:'sale_date'}, {id:'amazon_order_id'}, {id:'sku'}, {id:'sale_price'}, {id:'order_status'}]) + '</thead><tbody>';"
)

with open('templates/tracking.html', 'w') as f:
    f.write(content)
