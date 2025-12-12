# celery_app.py
from celery import Celery

celery_app = Celery('agentarbitrage')

# Load the configuration from celery_config.py
celery_app.config_from_object('celery_config')
