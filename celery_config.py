from celery import Celery

celery = Celery(
    'agentarbitrage',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0',
    include=['keepa_deals.Keepa_Deals']
)