#!/bin/bash

# Wrapper script to run the consolidated Python diagnostic
# This ensures backward compatibility for users accustomed to running this script.

# Determine the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Run the python script located in the same directory
python3 "$SCRIPT_DIR/comprehensive_diag.py"
