import sys
print("Loading celery_config.py")
sys.path.insert(0, '/app')

from celery import Celery

celery = Celery(
    'agentarbitrage',
    broker='redis://127.0.0.1:6379/0',
    backend='redis://127.0.0.1:6379/0'
)

from celery.schedules import crontab

celery.conf.update(
    imports=('keepa_deals.Keepa_Deals', 'keepa_deals.tasks', 'keepa_deals.simple_task', 'keepa_deals.backfiller'),
    worker_log_file='celery_worker.log',
    worker_log_level='INFO',
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    beat_schedule={
        'update-recent-deals-every-15-minutes': {
            'task': 'keepa_deals.simple_task.update_recent_deals',
            'schedule': crontab(minute='*/15'),
        },
    }
)
print("celery_config.py loaded successfully")