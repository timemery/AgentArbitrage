import subprocess
import os
import sys

# We need to run the python script and capture its output
output = subprocess.check_output([sys.executable, 'estimate_impact.py'], text=True)
print(output)
