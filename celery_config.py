import sys
print("Loading celery_config.py")
sys.path.insert(0, '/app')

from celery import Celery

celery = Celery(
    'agentarbitrage',
    broker='redis://127.0.0.1:6379/0',
    backend='redis://127.0.0.1:6379/0'
)

celery.conf.update(
    worker_log_file='celery_worker.log',
    worker_log_level='DEBUG',
)
print("celery_config.py loaded successfully")