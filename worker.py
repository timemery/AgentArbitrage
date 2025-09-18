from celery_config import celery
import keepa_deals.Keepa_Deals

# By importing the task module, the @celery.task decorator runs,
# registering the task with the celery instance.
# This is the entry point for the celery worker.
# Run worker with: celery -A worker.celery worker --loglevel=info