import re
from datetime import datetime

def analyze_log(log_file_path):
    """
    Parses the celery.log file to analyze the performance of the backfill_deals task.
    """
    # Regex patterns to identify key start and end points of phases
    task_start_pattern = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}): INFO/ForkPoolWorker-\d+\] --- Task: backfill_deals started ---")
    deal_collection_end_pattern = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}): INFO/ForkPoolWorker-\d+\] Total deals collected: (\d+)\. Starting product data fetch\.")
    product_fetch_end_pattern = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}): INFO/ForkPoolWorker-\d+\] Fetched product data for batch \d+/\d+")
    seller_fetch_start_pattern = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}): INFO/ForkPoolWorker-\d+\] Fetching data for batch of \d+ sellers")
    processing_start_pattern = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}): INFO/ForkPoolWorker-\d+\] Appending processed row for ASIN:")
    task_end_pattern = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}): INFO/ForkPoolWorker-\d+\] --- Task: backfill_deals finished ---")
    worker_lost_pattern = re.compile(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}): ERROR/MainProcess\] Task handler raised error: WorkerLostError")

    # Data storage
    timestamps = {
        "task_start": None,
        "deal_collection_end": None,
        "product_fetch_end": None,
        "seller_fetch_start": None, # First occurrence
        "seller_fetch_end": None, # Last occurrence
        "processing_start": None,
        "task_end": None,
        "task_crash": None,
    }
    total_deals = 0

    print(f"--- Analyzing log file: {log_file_path} ---")

    with open(log_file_path, 'r') as f:
        for line in f:
            # Match start of the task
            if not timestamps["task_start"]:
                match = task_start_pattern.search(line)
                if match:
                    timestamps["task_start"] = datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S,%f')
                    continue

            # Once task has started, look for other milestones
            if timestamps["task_start"]:
                deal_match = deal_collection_end_pattern.search(line)
                if deal_match:
                    timestamps["deal_collection_end"] = datetime.strptime(deal_match.group(1), '%Y-%m-%d %H:%M:%S,%f')
                    total_deals = int(deal_match.group(2))
                    continue

                prod_match = product_fetch_end_pattern.search(line)
                if prod_match:
                    timestamps["product_fetch_end"] = datetime.strptime(prod_match.group(1), '%Y-%m-%d %H:%M:%S,%f')

                seller_match = seller_fetch_start_pattern.search(line)
                if seller_match and not timestamps["seller_fetch_start"]:
                    timestamps["seller_fetch_start"] = datetime.strptime(seller_match.group(1), '%Y-%m-%d %H:%M:%S,%f')

                # The end of seller fetch is the last log entry before processing starts
                # So we find the last seller-related log entry
                if "Fetching data for batch of" in line:
                     timestamps["seller_fetch_end"] = datetime.strptime(line.split(',')[0], '%Y-%m-%d %H:%M:%S')


                proc_match = processing_start_pattern.search(line)
                if proc_match and not timestamps["processing_start"]:
                    timestamps["processing_start"] = datetime.strptime(proc_match.group(1), '%Y-%m-%d %H:%M:%S,%f')

                end_match = task_end_pattern.search(line)
                if end_match:
                    timestamps["task_end"] = datetime.strptime(end_match.group(1), '%Y-%m-%d %H:%M:%S,%f')

                crash_match = worker_lost_pattern.search(line)
                if crash_match:
                    timestamps["task_crash"] = datetime.strptime(crash_match.group(1), '%Y-%m-%d %H:%M:%S,%f')

    # --- Calculations and Reporting ---
    if not timestamps["task_start"]:
        print("Could not find the start of a backfill_deals task in the log.")
        return

    if total_deals == 0:
        print("Could not determine the total number of deals processed.")
        return

    print("\n--- Backfill Performance Analysis ---")
    print(f"Total ASINs Processed: {total_deals}")

    final_event_time = timestamps["task_end"] or timestamps["task_crash"] or timestamps["processing_start"] or timestamps["seller_fetch_end"]

    if final_event_time:
        total_runtime = final_event_time - timestamps["task_start"]
        print(f"Total Runtime (until last event): {str(total_runtime).split('.')[0]}")
    else:
        print("Could not determine total runtime.")


    print("\n--- Phase Durations ---")

    # Deal Collection
    if timestamps["deal_collection_end"]:
        deal_collection_duration = timestamps["deal_collection_end"] - timestamps["task_start"]
        print(f"1. Deal Collection:      {str(deal_collection_duration).split('.')[0]}")

    # Product Fetch
    if timestamps["product_fetch_end"] and timestamps["deal_collection_end"]:
        product_fetch_duration = timestamps["product_fetch_end"] - timestamps["deal_collection_end"]
        print(f"2. Product Data Fetch:   {str(product_fetch_duration).split('.')[0]}")

    # Seller Fetch
    if timestamps["seller_fetch_end"] and timestamps["seller_fetch_start"]:
        seller_fetch_duration = timestamps["seller_fetch_end"] - timestamps["seller_fetch_start"]
        print(f"3. Seller Data Fetch:    {str(seller_fetch_duration).split('.')[0]}")

    # xAI Processing
    if timestamps["processing_start"] and (timestamps["task_crash"] or timestamps["task_end"]):
        end_time = timestamps["task_crash"] or timestamps["task_end"]
        processing_duration = end_time - timestamps["processing_start"]
        print(f"4. xAI & Final Processing: {str(processing_duration).split('.')[0]} (until crash/end)")


    print("\n--- Average Time Per ASIN ---")

    if final_event_time:
        total_seconds = total_runtime.total_seconds()
        print(f"Overall Average: {total_seconds / total_deals:.2f} seconds/ASIN")

    if timestamps["product_fetch_end"] and timestamps["deal_collection_end"]:
        product_fetch_seconds = product_fetch_duration.total_seconds()
        print(f"- Product Fetch:   {product_fetch_seconds / total_deals:.2f} seconds/ASIN")

    if timestamps["seller_fetch_end"] and timestamps["seller_fetch_start"]:
        seller_fetch_seconds = seller_fetch_duration.total_seconds()
        print(f"- Seller Fetch:    {seller_fetch_seconds / total_deals:.2f} seconds/ASIN")

    if timestamps["processing_start"] and (timestamps["task_crash"] or timestamps["task_end"]):
        processing_seconds = processing_duration.total_seconds()
        # This is a partial number, so we need to know how many ASINs were processed
        # For now, we'll just show the total time for this phase
        print(f"- xAI Processing (partial): Ran for {str(processing_duration).split('.')[0]} before end event.")


    if timestamps["task_crash"]:
        print("\n--- Analysis Conclusion ---")
        print("The task ended abruptly due to a WorkerLostError (SIGKILL).")
        print("The durations and averages above reflect the time until the crash.")
    elif timestamps["task_end"]:
        print("\n--- Analysis Conclusion ---")
        print("The task completed successfully.")
    else:
        print("\n--- Analysis Conclusion ---")
        print("The task did not complete. The log may be incomplete.")


if __name__ == "__main__":
    analyze_log('celery.log')
