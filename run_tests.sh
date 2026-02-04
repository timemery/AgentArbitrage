#!/bin/bash
echo "Running Core Tests..."

# Find all test_*.py files in tests/ (maxdepth 1 ensures we skip Legacy/)
TEST_FILES=$(find tests -maxdepth 1 -name "test_*.py")

# Run each test module
for f in $TEST_FILES; do
    # Convert filepath to module format (tests/test_foo.py -> tests.test_foo)
    # 1. Strip .py extension
    mod="${f%.py}"
    # 2. Replace slashes with dots
    mod="${mod//\//.}"

    echo "----------------------------------------------------------------------"
    echo "Running $mod"
    python3 -m unittest "$mod"
    if [ $? -ne 0 ]; then
        echo "FAILED: $mod"
        exit 1
    fi
done

echo "----------------------------------------------------------------------"
echo "All Core Tests Passed."
