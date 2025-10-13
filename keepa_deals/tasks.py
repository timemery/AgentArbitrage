import logging
import os
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# The `update_recent_deals` task, which was previously in this file,
# has been moved to `keepa_deals/simple_task.py` as part of the
# new incremental update pipeline. This file is kept as a placeholder
# for any future, non-upserter Celery tasks.
