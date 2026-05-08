import re
import sys
import os

def main():
    log_file = sys.argv[1] if len(sys.argv) > 1 else "celery_worker.log"
    # Find absolute path if it is relative
    log_file = os.path.abspath(log_file)

    # Read the file
    try:
        with open(log_file, "r") as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: Could not find {log_file}")
        sys.exit(1)

    # Find the last occurrence of "Pass 2: Querying xAI API" to find the last run
    run_marker = "Pass 2: Querying xAI API"
    last_run_start_idx = content.rfind(run_marker)

    if last_run_start_idx == -1:
        print("Error: Could not find any Pass 2 runs in the log file.")
        sys.exit(1)

    # Extract the run info
    run_text = content[last_run_start_idx:]

    prompt_size = None
    latency = None
    raw_response = None
    reasoning_lines = []

    prompt_match = re.search(r"prompt size: (\d+) chars", run_text)
    if prompt_match:
        prompt_size = prompt_match.group(1)

    latency_match = re.search(r"took (\d+\.\d+) seconds", run_text)
    if latency_match:
        latency = latency_match.group(1)

    raw_response_match = re.search(r"Pass 2 Raw Response: ([\s\S]*?)(?=\n\[?\d{4}-\d{2}-\d{2}|\Z)", run_text)
    if raw_response_match:
        raw_response = raw_response_match.group(1).strip()

    for line in run_text.split("\n"):
        if "[Pass 2 Reasoning]" in line:
            reasoning_lines.append(line.split("[Pass 2 Reasoning] ")[1].strip())

    # Print output
    print("=" * 60)
    print("PASS 2 REASONING EXTRACTION (LATEST RUN)")
    print("=" * 60)
    print(f"Prompt Size: {prompt_size if prompt_size else 'Unknown'} characters")
    print(f"API Latency: {latency if latency else 'Unknown'} seconds")
    print("\n" + "-" * 60)
    print("RAW XAI RESPONSE:")
    print("-" * 60)
    print(raw_response if raw_response else "Not found")
    print("\n" + "-" * 60)
    print("PER-ASIN REASONING:")
    print("-" * 60)

    if not reasoning_lines:
        print("No per-ASIN reasoning logs found.")
    else:
        # Separate selected and rejected
        selected = []
        rejected = []

        for r in reasoning_lines:
            if "Selected=True" in r:
                selected.append(r)
            else:
                rejected.append(r)

        print(f"SELECTED CANDIDATES ({len(selected)}):")
        for r in selected:
            print(f"  {r}")

        print(f"\nREJECTED CANDIDATES ({len(rejected)}):")
        for r in rejected:
            print(f"  {r}")

    print("\n" + "=" * 60)

if __name__ == "__main__":
    main()
