with open('templates/tracking.html', 'r') as f:
    content = f.read()

generator_injection = """
    function generateSortArrows(tab, columns) {
        let html = '<tr class="sort-arrows-row">';
        const state = sortState[tab];

        columns.forEach(col => {
            if (!col.id) {
                html += '<td></td>';
                return;
            }

            const upArrowSrc = (state.column === col.id && state.order === 'asc') ? '/static/ascending-on.png' : '/static/ascending-off.png';
            const downArrowSrc = (state.column === col.id && state.order === 'desc') ? '/static/descending-on.png' : '/static/descending-off.png';

            html += `
                <td>
                    <div class="sort-arrows-container">
                        <img src="${upArrowSrc}" class="sort-arrow"
                             onclick="event.stopPropagation(); handleSort('${tab}', '${col.id}', 'asc')"
                             onmouseover="this.src='/static/ascending-on.png'"
                             onmouseout="this.src='${upArrowSrc}'">
                        <img src="${downArrowSrc}" class="sort-arrow"
                             onclick="event.stopPropagation(); handleSort('${tab}', '${col.id}', 'desc')"
                             onmouseover="this.src='/static/descending-on.png'"
                             onmouseout="this.src='${downArrowSrc}'">
                    </div>
                </td>`;
        });
        html += '</tr>';
        return html;
    }
"""

if "function generateSortArrows" not in content:
    content = content.replace("function renderPotential(items) {", generator_injection + "\n    function renderPotential(items) {")

import re

# Render Potential
pot_match = re.search(r'(let html = `<div class="table-container"><table class="deal-table" style="width:100%"><thead><tr class="column-header-row">.*?)</tr></thead><tbody>`;', content, re.DOTALL)
if pot_match and "generateSortArrows" not in pot_match.group(0):
    replacement = pot_match.group(1) + "</tr>' + generateSortArrows('potential', [{id:'title'}, {id:'asin'}, {id:'buy_cost'}, {id:'created_at'}, {id:'profit'}, {id:'roi'}, {id:'margin'}, {}]) + '</thead><tbody>';"
    content = content.replace(pot_match.group(0), replacement)

# Render Active
act_match = re.search(r'(let html = `<div class="table-container"><table class="deal-table" style="width:100%"><thead><tr class="column-header-row">.*?)</tr></thead><tbody>`;', content, re.DOTALL)
if act_match and "generateSortArrows" not in act_match.group(0):
    replacement = act_match.group(1) + "</tr>' + generateSortArrows('active', [{id:'asin'}, {id:'sku'}, {id:'title'}, {id:'quantity_remaining'}, {id:'buy_cost'}, {}]) + '</thead><tbody>';"
    content = content.replace(act_match.group(0), replacement)

# Render Sales
sal_match = re.search(r'(let html = `<div class="table-container"><table class="deal-table" style="width:100%"><thead><tr class="column-header-row">.*?)</tr></thead><tbody>`;', content, re.DOTALL)
if sal_match and "generateSortArrows" not in sal_match.group(0):
    replacement = sal_match.group(1) + "</tr>' + generateSortArrows('sales', [{id:'sale_date'}, {id:'amazon_order_id'}, {id:'sku'}, {id:'sale_price'}, {id:'order_status'}]) + '</thead><tbody>';"
    content = content.replace(sal_match.group(0), replacement)

with open('templates/tracking.html', 'w') as f:
    f.write(content)
