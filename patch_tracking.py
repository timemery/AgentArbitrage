import re

with open("templates/tracking.html", "r") as f:
    content = f.read()

# Replace header
content = content.replace(
    '<th>SKU</th><th>Title</th><th><div class="tooltip-header">Qty ℹ️',
    '<th>ASIN</th><th>SKU</th><th>Title</th><th><div class="tooltip-header">Qty ℹ️'
)

# Replace row
content = content.replace(
    '<tr class="deal-row">\n                <td>${item.sku || \'-\'}</td>',
    '<tr class="deal-row">\n                <td>${item.asin || \'—\'}</td>\n                <td>${item.sku || \'-\'}</td>'
)

# Replace colspan
content = content.replace(
    '<tr class="spacer-row"><td colspan="5">&nbsp;</td></tr>`;\n        });\n\n        html += \'</tbody></table></div>\';\n        container.innerHTML = html;\n    }\n\n    function openConfirmModal(item) {',
    '<tr class="spacer-row"><td colspan="6">&nbsp;</td></tr>`;\n        });\n\n        html += \'</tbody></table></div>\';\n        container.innerHTML = html;\n    }\n\n    function openConfirmModal(item) {'
)

with open("templates/tracking.html", "w") as f:
    f.write(content)
