with open('app.log', 'r') as f:
    lines = f.readlines()
    for line in lines[-200:]:
        if "Agent's Choice" in line:
            print(line.strip())
