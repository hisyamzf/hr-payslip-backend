"""
Celery configuration for HR Payslip System
Background task processing for PDF generation and upload processing
"""

from celery import Celery
import os

broker_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

celery_app = Celery(
    'hr_payslip',
    broker=broker_url,
    backend=result_backend,
    include=['app.tasks.pdf_tasks']
)

celery_app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Jakarta',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,
    task_soft_time_limit=270,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_routes={
        'app.tasks.pdf_tasks.generate_payslip_pdf': {'queue': 'pdf_generation'},
        'app.tasks.pdf_tasks.upload_payslip_to_storage': {'queue': 'pdf_upload'},
    },
    task_default_queue='default',
)
