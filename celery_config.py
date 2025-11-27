# celery_config.py
from celery.schedules import crontab

# This file is now only for configuration. The Celery app object is defined in celery_app.py.

broker_url = 'redis://127.0.0.1:6379/0'
result_backend = 'redis://127.0.0.1:6379/0'

imports = ('keepa_deals.Keepa_Deals', 'keepa_deals.tasks', 'keepa_deals.simple_task', 'keepa_deals.backfiller', 'keepa_deals.recalculator', 'keepa_deals.amazon_sp_api')
beat_schedule_filename = 'celerybeat-schedule'
worker_log_file = 'celery_worker.log'
worker_log_level = 'INFO'
task_serializer = 'json'
result_serializer = 'json'
accept_content = ['json']

beat_schedule = {
    'update-recent-deals-every-15-minutes': {
        'task': 'keepa_deals.simple_task.update_recent_deals',
        'schedule': crontab(minute='*/15'),
    },
}
