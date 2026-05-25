1. **ASIN and SKU links**
   - Create CSS class `.tracking-link { color: #a3aec0; text-decoration: none; }` and `.tracking-link:hover { text-decoration: underline; }` in `static/global.css`.
   - Update `renderPotential`, `renderActive`, `renderSales` in `tracking.html` to output:
     `<a href="https://www.amazon.com/dp/${asin}" target="_blank" rel="noopener noreferrer" class="tracking-link">${asin}</a>`
     `<a href="https://sellercentral.amazon.com/inventory?searchType=sku&searchValue=${sku}" target="_blank" rel="noopener noreferrer" class="tracking-link">${sku}</a>`

2. **Sorting functionality**
   - We need to attach sort click listeners for each column header arrow.
   - For `tracking.html`, the tables are updated entirely on each render. So we should define a global sorting state:
     ```javascript
     let sortState = {
         potential: { by: null, order: 'asc' },
         active: { by: null, order: 'asc' },
         sales: { by: null, order: 'asc' }
     };
     let currentData = { potential: [], active: [], sales: [] };
     ```
   - When fetching data, we store it in `currentData.tabName`, apply sorting, then render.
   - The arrow HTML generation should match Dashboard exactly:
     ```html
     <tr class="sort-arrows-row">
       <!-- loop columns -->
       <td>
         <div class="sort-arrows-container">
           <img src="/static/ascending-${active}.png" class="sort-arrow" onclick="handleSort('tab', 'col', 'asc')">
           ...
         </div>
       </td>
     </tr>
     ```

3. **CSS / Visual matching**
   - `dashboard.html` uses `.sort-arrows-row td::before` and `::after` with sticky top to hide scrolling rows underneath.
   - We will need to adapt the sticky top for `.tracking-page`. Let's check `global.css`:
     `tracking-page .deal-table .column-header-row th { top: 134px; }`
     So the sort row should be:
     `tracking-page .deal-table .sort-arrows-row td { top: 165px; z-index: 170; }` (since header is 31px height).
   - And the shadow line:
     `#tracking-shadow-line { top: 190px; }` (165 + 25px height of sort row).

4. **Shadow effect JavaScript**
   - Scroll listener in `tracking.html` will toggle `#tracking-shadow-line` display.
