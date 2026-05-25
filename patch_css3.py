with open('static/global.css', 'r') as f:
    content = f.read()

content = content.replace(
"""#tracking-shadow-line {
    position: fixed;
    top: 110px; /* Aligns just below tabs/arrows row */
    left: 0;
    right: 0;
    height: 10px;
    box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.4);
    z-index: 8;
    pointer-events: none;
    display: none;
}""",
"""#tracking-shadow-line {
    position: fixed;
    top: 190px; /* 165px (arrows top) + 25px (arrows height) */
    left: 50%;
    transform: translateX(-50%);
    width: 100%;
    max-width: 1200px;
    height: 30px;
    background: linear-gradient(to bottom, rgba(0, 0, 0, 0.75) 0%, rgba(0, 0, 0, 0) 100%);
    z-index: 8 !important;
    pointer-events: none;
    display: none;
}"""
)

with open('static/global.css', 'w') as f:
    f.write(content)
