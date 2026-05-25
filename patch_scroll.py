with open('templates/tracking.html', 'r') as f:
    content = f.read()

scroll_code = """
        // Show mask only after scrolling past the tabs area
        window.addEventListener('scroll', () => {
            const tabsHeight = 100;
            if (window.scrollY > tabsHeight) {
                document.getElementById('tracking-shadow-line').style.display = 'block';
            } else {
                document.getElementById('tracking-shadow-line').style.display = 'none';
            }
        });
"""

if "window.addEventListener('scroll'" not in content:
    content = content.replace("fetchPotential(); // Refresh tables", "fetchPotential(); // Refresh tables\n" + scroll_code)

with open('templates/tracking.html', 'w') as f:
    f.write(content)
