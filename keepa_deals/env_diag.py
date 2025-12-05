# keepa_deals/env_diag.py

import logging
import inspect
import os
from worker import celery_app as celery

# Use getLogger for compatibility with Celery
logger = logging.getLogger(__name__)

DIAG_OUTPUT_FILE = 'diag_output.log'

@celery.task(name='keepa_deals.env_diag.run_environment_diagnostic')
def run_environment_diagnostic():
    """
    Inspects the running Celery worker's environment and records its findings.
    This acts as a "black box recorder" to see what code the worker has loaded.
    """
    logger.info("--- Starting Environment Diagnostic Task ---")

    output_content = []
    output_content.append("--- Environment Diagnostic Report ---")

    try:
        from datetime import datetime
        output_content.append(f"Timestamp (UTC): {datetime.utcnow().isoformat()}")
    except:
        pass

    output_content.append(f"Current Working Directory: {os.getcwd()}")
    output_content.append(f"PID: {os.getpid()}")

    try:
        # Import the module we want to inspect
        from keepa_deals import backfiller

        output_content.append("\n--- SOURCE CODE OF LOADED keepa_deals.backfiller MODULE ---")

        # Get the full source code of the loaded module
        source_code = inspect.getsource(backfiller)
        output_content.append(source_code)

        logger.info("Successfully retrieved source code of the loaded backfiller module.")

    except Exception as e:
        error_message = f"Failed to inspect backfiller module: {e}"
        output_content.append(f"\n--- ERROR ---")
        output_content.append(error_message)
        logger.error(error_message, exc_info=True)

    # Write the report to the diagnostic log file
    try:
        # Write to the root directory
        report_path = os.path.join(os.path.dirname(__file__), '..', DIAG_OUTPUT_FILE)
        with open(report_path, 'w') as f:
            f.write("\n".join(output_content))
        logger.info(f"Successfully wrote diagnostic report to {report_path}")
    except Exception as e:
        logger.error(f"Failed to write diagnostic report: {e}", exc_info=True)

    logger.info("--- Environment Diagnostic Task Finished ---")
    return f"Diagnostic report written to {DIAG_OUTPUT_FILE}"
