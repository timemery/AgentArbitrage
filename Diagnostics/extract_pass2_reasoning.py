import sys
import os

def find_last_run_start(file_path, marker="Pass 2: Querying xAI API"):
    """
    Reads the file backward in chunks to find the last occurrence of the marker.
    Returns the byte offset of the line containing the marker, or -1 if not found.
    """
    chunk_size = 8192
    with open(file_path, 'rb') as f:
        f.seek(0, 2)
        file_size = f.tell()

        offset = file_size
        overlap = b""

        while offset > 0:
            read_size = min(chunk_size, offset)
            offset -= read_size
            f.seek(offset)
            chunk = f.read(read_size) + overlap

            # Find the marker in this chunk
            idx = chunk.rfind(marker.encode('utf-8'))
            if idx != -1:
                # We found the marker. We need to find the start of its line.
                # Find the last newline before the marker in this chunk
                newline_idx = chunk.rfind(b'\n', 0, idx)
                if newline_idx == -1:
                    # The line starts exactly at or before this chunk's boundary.
                    # Since we didn't find a newline, the line start is at least `offset`.
                    # To be safe, just return the offset + idx as an approximation.
                    return offset + idx
                else:
                    return offset + newline_idx + 1

            overlap = chunk[:len(marker)] # Keep overlap in case marker crosses chunk boundary

    return -1

def main():
    log_file = sys.argv[1] if len(sys.argv) > 1 else "celery_worker.log"
    log_file = os.path.abspath(log_file)

    if not os.path.exists(log_file):
        print(f"Error: Could not find {log_file}")
        sys.exit(1)

    start_offset = find_last_run_start(log_file)

    if start_offset == -1:
        print("Error: Could not find any Pass 2 runs in the log file.")
        sys.exit(1)

    prompt_size = None
    latency = None
    raw_response_lines = []
    reasoning_lines = []

    in_raw_response = False
    max_raw_response_lines = 1000 # Safety bound to prevent OOM

    # Process file line by line to avoid memory exhaustion
    with open(log_file, "r") as f:
        f.seek(start_offset)
        for line in f:
            if "Pass 2: Querying xAI API (prompt size: " in line:
                try:
                    prompt_size = line.split("prompt size: ")[1].split(" chars")[0]
                except IndexError:
                    pass
            elif "Pass 2: xAI API call took" in line:
                try:
                    latency = line.split("took ")[1].split(" seconds")[0]
                except IndexError:
                    pass
            elif "Pass 2 Raw Response:" in line:
                in_raw_response = True
                try:
                    raw_response_lines.append(line.split("Pass 2 Raw Response:")[1].lstrip())
                except IndexError:
                    pass
            elif in_raw_response:
                # If we encounter a new log timestamp, we are out of the raw response block
                # Celery log lines typically start with a bracket: [2023-10-27 10:00:00,000: INFO/MainProcess]
                stripped = line.strip()
                is_new_log_entry = False

                # Check for standard celery log format
                if stripped.startswith('[') and len(stripped) > 5 and stripped[1:5].isdigit() and stripped[5] == '-':
                    is_new_log_entry = True
                # Fallback for standard python log format
                elif len(stripped) > 10 and stripped[0:4].isdigit() and stripped[4] == '-' and stripped[7] == '-':
                    is_new_log_entry = True

                if is_new_log_entry:
                     in_raw_response = False
                elif "[Pass 2 Reasoning]" in line:
                     in_raw_response = False
                elif len(raw_response_lines) > max_raw_response_lines:
                     in_raw_response = False
                     raw_response_lines.append("... [TRUNCATED - EXCEEDED MAX LINES] ...")
                else:
                    raw_response_lines.append(line)

            if "[Pass 2 Reasoning]" in line:
                parts = line.split("[Pass 2 Reasoning] ")
                if len(parts) > 1:
                    reasoning_lines.append(parts[1].strip())

    raw_response = "".join(raw_response_lines).strip()

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
