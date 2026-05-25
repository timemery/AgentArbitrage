with open('static/global.css', 'r') as f:
    content = f.read()

# Make sure we use !important to override the existing tracking overrides.
# Also use the offset 134px because the other tracking override uses `top: 134px;` and there's a `.tracking-sticky-mask` at `top: 134px;`.

content = content.replace(
""".tracking-page .deal-table th,
.tracking-page .deal-table .column-header-row th {
    /* Existing tracking override kept, but ensuring it stacks correctly */
    position: sticky;
    top: 50px;
    z-index: 10;
}

.tracking-page .sort-arrows-row td {
    position: sticky;
    top: 96px; /* Matches height below the headers */
    z-index: 9;
    background-color: var(--card-bg-color);
    border-bottom: 1px solid var(--border-color);
}""",
""".tracking-page .deal-table th,
.tracking-page .deal-table .column-header-row th {
    position: sticky !important;
    top: 134px !important;
    z-index: 10 !important;
}

.tracking-page .sort-arrows-row td {
    position: sticky !important;
    top: 165px !important; /* 134px + 31px header height */
    z-index: 9 !important;
    background-color: #13161a !important; /* Site background */
    border: none !important;
}

.tracking-page .sort-arrows-row td::before {
    content: '';
    position: absolute;
    inset: 0;
    background-color: #13161a;
    z-index: -2;
}
.tracking-page .sort-arrows-row td::after {
    content: '';
    position: absolute;
    inset: 0;
    background-color: #13161a;
    z-index: -1;
}"""
)

with open('static/global.css', 'w') as f:
    f.write(content)
