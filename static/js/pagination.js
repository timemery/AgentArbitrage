function renderSharedPagination(pagination, containerId, fetchCallback) {
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = '';

    // Handle different API pagination formats gracefully
    const totalPages = pagination.total_pages || pagination.pages;
    const currentPage = pagination.current_page || pagination.page;

    if (!totalPages || totalPages <= 1) return;

    const createButton = (text, page, isActive = false, isDisabled = false) => {
        const btn = document.createElement('button');
        btn.textContent = text;
        btn.className = `page-btn ${isActive ? 'active' : ''}`;
        if (isDisabled) btn.disabled = true;
        else btn.onclick = () => {
            fetchCallback(page);
            // Try to find the closest table to scroll to, otherwise scroll to top
            const table = container.closest('.tab-content')?.querySelector('table') || document.getElementById('deals-table');
            if(table) {
                table.scrollIntoView({ behavior: 'smooth' });
            }
        };
        return btn;
    };

    // Prev Button
    container.appendChild(createButton('Prev', currentPage - 1, false, currentPage === 1));

    // Logic for page numbers (window of 5)
    let startPage = Math.max(1, currentPage - 2);
    let endPage = Math.min(totalPages, startPage + 4);

    if (endPage - startPage < 4) {
        startPage = Math.max(1, endPage - 4);
    }

    if (startPage > 1) {
        container.appendChild(createButton('1', 1, currentPage === 1));
        if (startPage > 2) {
            const ellipsis = document.createElement('span');
            ellipsis.className = 'page-ellipsis';
            ellipsis.textContent = '...';
            container.appendChild(ellipsis);
        }
    }

    for (let i = startPage; i <= endPage; i++) {
        container.appendChild(createButton(i, i, currentPage === i));
    }

    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            const ellipsis = document.createElement('span');
            ellipsis.className = 'page-ellipsis';
            ellipsis.textContent = '...';
            container.appendChild(ellipsis);
        }
        container.appendChild(createButton(totalPages, totalPages, currentPage === totalPages));
    }

    // Next Button
    container.appendChild(createButton('Next', currentPage + 1, false, currentPage === totalPages));
}
