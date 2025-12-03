import os
import sys
import pwd
import inspect
import logging
from worker import celery_app as celery
import keepa_deals.simple_task

# This is a special diagnostic task to inspect the worker's environment.

@celery.task(name="keepa_deals.env_diag.log_worker_environment")
def log_worker_environment():
    """
    Logs critical information about the Celery worker's execution environment
    to a file named diag_output.log in the application root.
    """
    log_file = os.path.join(os.getcwd(), 'diag_output.log')

    # Configure a logger to write specifically to our diagnostic file
    diag_logger = logging.getLogger('env_diag')
    diag_logger.setLevel(logging.INFO)
    # Prevent propagation to the root logger
    diag_logger.propagate = False

    # Remove old handlers to avoid duplicate logging
    for handler in diag_logger.handlers[:]:
        diag_logger.removeHandler(handler)

    handler = logging.FileHandler(log_file)
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    handler.setFormatter(formatter)
    diag_logger.addHandler(handler)

    diag_logger.info("--- Starting Worker Environment Diagnosis ---")

    try:
        # 1. Basic Info
        diag_logger.info(f"Current User: {pwd.getpwuid(os.getuid()).pw_name}")
        diag_logger.info(f"Current Working Directory: {os.getcwd()}")
        diag_logger.info(f"Python Executable: {sys.executable}")

        # 2. Python Path
        diag_logger.info("Python Path (sys.path):")
        for path in sys.path:
            diag_logger.info(f"  - {path}")

        # 3. Inspect the problematic module
        diag_logger.info("--- Inspecting 'keepa_deals.simple_task' module ---")
        try:
            module_path = inspect.getfile(keepa_deals.simple_task)
            diag_logger.info(f"Path to simple_task.py: {module_path}")

            # 4. Read the content of the file
            diag_logger.info("--- Content of simple_task.py as seen by the worker ---")
            with open(module_path, 'r') as f:
                content = f.read()
                diag_logger.info(content)
            diag_logger.info("--- End of simple_task.py content ---")

        except Exception as e:
            diag_logger.error(f"Could not inspect or read simple_task.py: {e}")

        # 5. Check celery_app object
        diag_logger.info("--- Inspecting celery_app object in simple_task ---")
        try:
            # This is the line that fails. Let's see what the linter thinks of it.
            # In the user's log, the error is UnboundLocalError for 'celery_app'
            # Let's inspect the source of the function itself.
            source_code = inspect.getsource(keepa_deals.simple_task.update_recent_deals)
            diag_logger.info("--- Source code of update_recent_deals function ---")
            diag_logger.info(source_code)
            diag_logger.info("--- End of source code ---")
            if "from worker import celery_app as celery" in source_code:
                 diag_logger.info("Found correct import alias in function source.")
            else:
                 diag_logger.warning("Did NOT find correct import alias in function source.")


        except Exception as e:
            diag_logger.error(f"Could not get source of update_recent_deals: {e}")


    except Exception as e:
        diag_logger.error(f"An unexpected error occurred during diagnosis: {e}", exc_info=True)

    diag_logger.info("--- End of Diagnosis ---")

    # Close the handler to ensure the file is written
    handler.close()
    diag_logger.removeHandler(handler)

    return f"Diagnostics written to {log_file}"
