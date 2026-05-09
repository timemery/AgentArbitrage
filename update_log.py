import sys

def modify_file():
    with open('wsgi_handler.py', 'r') as f:
        lines = f.readlines()

    for i, line in enumerate(lines):
        if "except (KeyError, IndexError):" in line:
            # We want to add full exception logging here.
            lines.insert(i+1, "             app.logger.exception(f\"Error parsing AI response: {result}\")\n")
            break

    with open('wsgi_handler.py', 'w') as f:
        f.writelines(lines)

modify_file()
