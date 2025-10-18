# This file is the entry point for the Celery worker.
# It imports the celery app instance from celery_config.py

from celery_config import celery

# The following line is necessary for Celery to discover tasks.
# Although the variable 'celery' is not explicitly used here,
# the import statement makes the Celery app instance available
# to the Celery worker command.
# The command `celery -A worker.celery worker` will look for the
# `celery` object in this `worker.py` module.