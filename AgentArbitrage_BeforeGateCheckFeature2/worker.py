# This file is the entry point for the Celery worker.
# It now imports the celery_app instance from the new celery_app.py file.
# This breaks the circular dependency that was causing startup hangs.
#
# DO NOT import task modules directly here.
# Task discovery is handled by the `imports` tuple in `celery_config.py`,
# which is loaded by the celery_app.

from celery_app import celery_app

# The celery_app variable must be exposed in this module's namespace for the
# `celery -A worker.celery_app worker` command to find it. The `-A` flag now
# needs to point to this new object.
