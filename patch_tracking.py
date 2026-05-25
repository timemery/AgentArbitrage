import re

with open('templates/tracking.html', 'r') as f:
    content = f.read()

# Add sort state to script
if "let sortState =" not in content:
    state_injection = """
    // Sort state and data
    let currentData = { potential: [], active: [], sales: [] };
    let sortState = {
        potential: { column: null, order: 'asc' },
        active: { column: null, order: 'asc' },
        sales: { column: null, order: 'asc' }
    };

    function sortData(tab, data) {
        if (!sortState[tab].column || !data || data.length === 0) return data;
        const col = sortState[tab].column;
        const order = sortState[tab].order;

        return [...data].sort((a, b) => {
            let valA = a[col] !== undefined ? a[col] : '';
            let valB = b[col] !== undefined ? b[col] : '';

            // Handle em-dashes as null/bottom
            if (valA === '—' || valA === null) valA = '';
            if (valB === '—' || valB === null) valB = '';
            if (valA === '' && valB !== '') return 1;
            if (valB === '' && valA !== '') return -1;
            if (valA === '' && valB === '') return 0;

            // Handle numbers formatted as currencies/percentages
            let numA = String(valA).replace(/[\$,%]/g, '');
            let numB = String(valB).replace(/[\$,%]/g, '');

            if (!isNaN(parseFloat(numA)) && !isNaN(parseFloat(numB))) {
                return order === 'asc' ? parseFloat(numA) - parseFloat(numB) : parseFloat(numB) - parseFloat(numA);
            }

            // Handle dates
            let dateA = Date.parse(valA);
            let dateB = Date.parse(valB);
            if (!isNaN(dateA) && !isNaN(dateB)) {
                return order === 'asc' ? dateA - dateB : dateB - dateA;
            }

            // String sort
            return order === 'asc' ? String(valA).localeCompare(String(valB)) : String(valB).localeCompare(String(valA));
        });
    }

    function handleSort(tab, column, order = null) {
        if (order) {
            sortState[tab].column = column;
            sortState[tab].order = order;
        } else {
            // Toggle logic if no explicit order given
            if (sortState[tab].column === column) {
                if (sortState[tab].order === 'asc') {
                    sortState[tab].order = 'desc';
                } else if (sortState[tab].order === 'desc') {
                    sortState[tab].column = null;
                    sortState[tab].order = 'asc';
                }
            } else {
                sortState[tab].column = column;
                sortState[tab].order = 'asc';
            }
        }

        if (tab === 'potential') renderPotential(sortData('potential', currentData.potential));
        if (tab === 'active') renderActive(sortData('active', currentData.active));
        if (tab === 'sales') renderSales(sortData('sales', currentData.sales));
    }
"""
    content = content.replace("<script>", "<script>" + state_injection)

# Add sort arrows generator
if "function generateSortArrows" not in content:
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
    content = content.replace("function renderPotential(data) {", generator_injection + "\n    function renderPotential(data) {")

with open('templates/tracking.html', 'w') as f:
    f.write(content)
