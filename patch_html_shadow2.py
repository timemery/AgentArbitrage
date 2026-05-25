with open('templates/tracking.html', 'r') as f:
    content = f.read()

scroll_code = """
    window.addEventListener('scroll', () => {
        const mask = document.querySelector('.tracking-sticky-mask');
        const shadow = document.getElementById('tracking-shadow-line');

        // Show mask and shadow only after scrolling past the tabs area
        if (window.scrollY > 10) {
            if (mask) mask.style.display = 'block';
            if (shadow) shadow.style.display = 'block';
        } else {
            if (mask) mask.style.display = 'none';
            if (shadow) shadow.style.display = 'none';
        }
    });
"""

# Replace existing scroll listener
import re
content = re.sub(r'window\.addEventListener\(\'scroll\'.*?\}\);', scroll_code, content, flags=re.DOTALL)

with open('templates/tracking.html', 'w') as f:
    f.write(content)
