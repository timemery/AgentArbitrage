with open('static/global.css', 'r') as f:
    lines = f.readlines()

out = []
for i, line in enumerate(lines):
    if "/* Tracking page specific overrides */" in line:
        for j in range(-5, 50):
            if i+j >= 0 and i+j < len(lines):
                out.append(f"{i+j}: {lines[i+j]}")
        break

print("".join(out))
