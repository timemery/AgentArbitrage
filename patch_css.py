import re

with open('static/global.css', 'r') as f:
    content = f.read()

# Fix the tracking headers - the tracking table might not be nested exactly how the CSS selector expects
content = content.replace(
"""/* Tracking Layout Consistency with Dashboard */
.tracking-page .deal-table th {""",
"""/* Tracking Layout Consistency with Dashboard */
.tracking-page .deal-table th,
.tracking-page .deal-table .column-header-row th {"""
)

with open('static/global.css', 'w') as f:
    f.write(content)
