with open("templates/tracking.html", "r") as f:
    content = f.read()

# I need to restore the closing div for the div containing the buttons
target_block = """    <!-- Active Inventory Tab -->
    <div id="active-inventory" class="tab-content">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <h2>Active Inventory</h2>
            <div style="display: flex; gap: 10px;">
                    <button id="btn-sync" class="tidy-button" onclick="triggerImport()">Sync from Amazon</button>
                    <button class="tidy-button btn-info-style" onclick="window.location.href='/api/inventory/export-missing-costs'">Download Missing Costs CSV</button>
                    <button id="btn-upload" class="tidy-button" onclick="document.getElementById('cost-upload').click()">Upload Costs (CSV)</button>
                    <input type="file" id="cost-upload" style="display: none;" onchange="uploadCosts(this)">
                </div>
            <p class="tidy-text">Confirmed inventory currently at Amazon or in transit.</p>
            <div id="active-table-container">Loading...</div>
            <div id="active-pagination" class="pagination-controls" style="margin-top: 20px; text-align: center;"></div>
    </div>"""

fixed_block = """    <!-- Active Inventory Tab -->
    <div id="active-inventory" class="tab-content">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <h2>Active Inventory</h2>
            <div style="display: flex; gap: 10px;">
                <button id="btn-sync" class="tidy-button" onclick="triggerImport()">Sync from Amazon</button>
                <button class="tidy-button btn-info-style" onclick="window.location.href='/api/inventory/export-missing-costs'">Download Missing Costs CSV</button>
                <button id="btn-upload" class="tidy-button" onclick="document.getElementById('cost-upload').click()">Upload Costs (CSV)</button>
                <input type="file" id="cost-upload" style="display: none;" onchange="uploadCosts(this)">
            </div>
        </div>
        <p class="tidy-text">Confirmed inventory currently at Amazon or in transit.</p>
        <div id="active-table-container">Loading...</div>
        <div id="active-pagination" class="pagination-controls" style="margin-top: 20px; text-align: center;"></div>
    </div>"""

new_content = content.replace(target_block, fixed_block)

with open("templates/tracking.html", "w") as f:
    f.write(new_content)
