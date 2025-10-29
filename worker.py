# This file is the entry point for the Celery worker.
# It imports the celery app instance from celery_config.py
#
# DO NOT import task modules directly here (e.g., `from keepa_deals import simple_task`).
# Task discovery is handled by the `imports` tuple in `celery_config.py`.
# Direct imports in this file can cause the worker to crash on startup if any
# imported module has an error, preventing the worker from ever starting.

from celery_config import celery

# The celery variable must be exposed in this module's namespace for the
# `celery -A worker.celery worker` command to find it. No other code is needed.
