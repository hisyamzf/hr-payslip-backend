"""
Celery worker startup script
Run this to start background workers for PDF generation

Usage:
    python -m celery_worker
"""

from app.celery_app import celery_app
from app.tasks.pdf_tasks import (
    generate_payslip_pdf,
    upload_payslip_to_storage,
    process_payslip,
    batch_process_payslips,
    process_upload_session,
)

if __name__ == '__main__':
    print("Starting Celery worker...")
    celery_app.worker_main([
        'worker',
        '--loglevel=info',
        '--queues=default,pdf_generation,pdf_upload',
        '--concurrency=4',
    ])
