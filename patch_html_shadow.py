with open('templates/tracking.html', 'r') as f:
    content = f.read()

content = content.replace('<div class="tracking-sticky-mask"></div>', '<div class="tracking-sticky-mask"></div>\n    <div id="tracking-shadow-line"></div>')

if "window.addEventListener('scroll'" not in content:
    scroll_code = """
        // Show shadow only after scrolling past the tabs area
        window.addEventListener('scroll', () => {
            const tabsHeight = 100; // Matches dashboard offset conceptually
            const shadowLine = document.getElementById('tracking-shadow-line');
            if (shadowLine) {
                if (window.scrollY > tabsHeight) {
                    shadowLine.style.display = 'block';
                } else {
                    shadowLine.style.display = 'none';
                }
            }
        });
"""
    content = content.replace("fetchPotential(); // Refresh tables", "fetchPotential(); // Refresh tables\n" + scroll_code)

with open('templates/tracking.html', 'w') as f:
    f.write(content)
