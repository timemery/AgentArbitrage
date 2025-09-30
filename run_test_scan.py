import logging
from keepa_deals.Keepa_Deals import run_keepa_script

# Configure basic logging to see the task dispatch confirmation
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Credentials and parameters for the test scan
# The API key is from the project briefing
KEEPA_API_KEY = "bg9037ndr2jrlore45acr8a3gustia0tusdfk5e54g1le917nspnk9jiktp7b08b"
TEST_DEAL_LIMIT = 5

logger.info(f"Dispatching test scan task to Celery worker with a limit of {TEST_DEAL_LIMIT} deals.")

# This is the corrected action: calling .delay() with only the valid arguments
task = run_keepa_script.delay(
    api_key=KEEPA_API_KEY,
    deal_limit=TEST_DEAL_LIMIT
)

logger.info(f"Task successfully dispatched with ID: {task.id}")
logger.info("The Celery worker should now be processing the scan.")
logger.info("You can monitor its progress by checking the 'celery_test.log' file.")