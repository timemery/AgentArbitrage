import sys

def modify_file():
    with open('wsgi_handler.py', 'r') as f:
        lines = f.readlines()

    out_lines = []
    for line in lines:
        if "app.logger.exception(f\"Error parsing AI response:" in line:
            # Skip all but we will add one back
            continue
        out_lines.append(line)

    for i, line in enumerate(out_lines):
        if "except (KeyError, IndexError):" in line:
            out_lines.insert(i+1, "             app.logger.exception(f\"Error parsing AI response: {result}\")\n")
            break

    with open('wsgi_handler.py', 'w') as f:
        f.writelines(out_lines)

modify_file()
