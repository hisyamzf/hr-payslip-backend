"""
Celery tasks for PDF generation and Supabase Storage upload
"""

import logging
from celery import chain, group, chord
from app.celery_app import celery_app
from app.services.pdf_service import PayslipPDFService
from app.utils.supabase_client import SupabaseStorageClient
from app.config.database import SessionLocal
from app.models.database import Payslip
from app.repositories.payslip_repository import PayslipRepository
from app.repositories.company_repository import CompanyRepository
from app.repositories.employee_repository import EmployeeRepository
from uuid import UUID
from datetime import datetime

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def generate_payslip_pdf(self, payslip_id: str):
    """
    Generate PDF for a single payslip
    
    Args:
        payslip_id: UUID of the payslip
        
    Returns:
        dict with payslip_id and status
    """
    db = SessionLocal()
    
    try:
        payslip_id_uuid = UUID(payslip_id)
        payslip_repo = PayslipRepository(db)
        company_repo = CompanyRepository(db)
        employee_repo = EmployeeRepository(db)
        
        payslip = payslip_repo.get_by_id(payslip_id_uuid)
        
        if not payslip:
            logger.error(f"Payslip not found: {payslip_id}")
            return {'status': 'error', 'payslip_id': payslip_id, 'error': 'Payslip not found'}
        
        employee = employee_repo.get_by_id(payslip.employee_id)
        company = company_repo.get_by_id(payslip.company_id)
        
        if not employee or not company:
            logger.error(f"Employee or Company not found for payslip: {payslip_id}")
            return {'status': 'error', 'payslip_id': payslip_id, 'error': 'Employee or Company not found'}
        
        full_name = f"{employee.first_name} {employee.last_name}".strip()
        
        pdf_service = PayslipPDFService()
        pdf_bytes = pdf_service.generate_payslip_pdf(
            employee_id=employee.employee_number,
            employee_name=full_name,
            employee_department=payslip.department or 'N/A',
            employee_position=payslip.position or 'N/A',
            employee_join_date=employee.join_date,
            employee_bank_account=employee.bank_account,
            company_name=company.name,
            company_address='',  # Can be added to Company model
            company_phone='',   # Can be added to Company model
            company_logo=None,
            period_start=payslip.period_start,
            period_end=payslip.period_end,
            payment_date=payslip.payment_date,
            earnings=payslip.earnings or {},
            deductions=payslip.deductions or {},
            total_earnings=float(payslip.gross_salary),
            total_deductions=float(payslip.total_deductions),
            net_salary=float(payslip.net_salary),
        )
        
        logger.info(f"✅ PDF generated for payslip {payslip_id}: {len(pdf_bytes)} bytes")
        
        return {
            'status': 'success',
            'payslip_id': payslip_id,
            'pdf_bytes': pdf_bytes,
            'employee_number': employee.employee_number,
            'period_start': payslip.period_start.isoformat()
        }
    
    except Exception as e:
        logger.error(f"❌ Error generating PDF for {payslip_id}: {str(e)}")
        
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            return {'status': 'error', 'payslip_id': payslip_id, 'error': str(e)}
    
    finally:
        db.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def upload_payslip_to_storage(self, task_result: dict):
    """
    Upload generated PDF to Supabase Storage
    
    Args:
        task_result: Result from generate_payslip_pdf task
        
    Returns:
        dict with file_url
    """
    if task_result.get('status') != 'success':
        logger.warning(f"Skipping upload - PDF generation failed: {task_result}")
        return task_result
    
    try:
        storage_client = SupabaseStorageClient()
        
        payslip_id = task_result['payslip_id']
        pdf_bytes = task_result['pdf_bytes']
        employee_number = task_result['employee_number']
        period_start = task_result['period_start']
        
        file_path = f"payslips/{period_start}/{employee_number}_{payslip_id}.pdf"
        
        result = storage_client.upload_file(
            file_path=file_path,
            file_content=pdf_bytes,
            content_type='application/pdf',
            public=True
        )
        
        file_url = storage_client.get_public_url(file_path)
        
        db = SessionLocal()
        try:
            payslip_repo = PayslipRepository(db)
            payslip = payslip_repo.get_by_id(UUID(payslip_id))
            
            if payslip:
                payslip.file_url = file_url
                payslip.status = 'generated'
                payslip.updated_at = datetime.utcnow()
                db.commit()
                logger.info(f"✅ Payslip {payslip_id} file_url updated: {file_url}")
        finally:
            db.close()
        
        return {
            'status': 'success',
            'payslip_id': payslip_id,
            'file_url': file_url
        }
    
    except Exception as e:
        logger.error(f"❌ Error uploading PDF for {task_result.get('payslip_id')}: {str(e)}")
        
        try:
            self.retry(exc=e)
        except self.MaxRetriesExceededError:
            return {'status': 'error', 'payslip_id': task_result.get('payslip_id'), 'error': str(e)}


@celery_app.task(bind=True)
def process_payslip(self, payslip_id: str):
    """
    Complete pipeline: Generate PDF + Upload to storage
    
    Args:
        payslip_id: UUID of the payslip
        
    Returns:
        dict with file_url
    """
    try:
        pdf_result = generate_payslip_pdf.delay(payslip_id)
        
        upload_result = upload_payslip_to_storage.delay(pdf_result.get())
        
        return upload_result.get(timeout=120)
    
    except Exception as e:
        logger.error(f"❌ Error in process_payslip pipeline for {payslip_id}: {str(e)}")
        return {'status': 'error', 'payslip_id': payslip_id, 'error': str(e)}


@celery_app.task(bind=True)
def batch_process_payslips(self, payslip_ids: list):
    """
    Batch process multiple payslips concurrently
    
    Args:
        payslip_ids: List of payslip UUIDs
        
    Returns:
        dict with summary
    """
    logger.info(f"📦 Starting batch process for {len(payslip_ids)} payslips")
    
    try:
        tasks = []
        for payslip_id in payslip_ids:
            task = chain(
                generate_payslip_pdf.s(payslip_id),
                upload_payslip_to_storage.s()
            )
            tasks.append(task)
        
        results = group(tasks)()
        
        processed_results = results.get(timeout=600)
        
        successful = sum(1 for r in processed_results if r.get('status') == 'success')
        failed = len(processed_results) - successful
        
        logger.info(f"✅ Batch complete: {successful} success, {failed} failed")
        
        return {
            'total': len(payslip_ids),
            'successful': successful,
            'failed': failed,
            'results': processed_results
        }
    
    except Exception as e:
        logger.error(f"❌ Error in batch process: {str(e)}")
        return {'status': 'error', 'error': str(e)}


@celery_app.task(bind=True)
def process_upload_session(self, upload_session_id: str, payslip_ids: list):
    """
    Process all payslips from an upload session
    
    Args:
        upload_session_id: UUID of the upload session
        payslip_ids: List of payslip UUIDs to process
        
    Returns:
        dict with processing summary
    """
    from app.config.database import SessionLocal
    from app.models.database import PayslipUploadSession
    from datetime import datetime
    
    db = SessionLocal()
    
    try:
        session = db.query(PayslipUploadSession).filter(
            PayslipUploadSession.upload_session_id == UUID(upload_session_id)
        ).first()
        
        if not session:
            return {'status': 'error', 'error': 'Upload session not found'}
        
        session.status = 'processing'
        session.updated_at = datetime.utcnow()
        db.commit()
        
        batch_result = batch_process_payslips(payslip_ids)
        
        session.status = 'completed_with_errors' if batch_result.get('failed', 0) > 0 else 'completed'
        session.updated_at = datetime.utcnow()
        session.result = batch_result
        db.commit()
        
        return batch_result
    
    except Exception as e:
        logger.error(f"❌ Error processing upload session {upload_session_id}: {str(e)}")
        
        try:
            session = db.query(PayslipUploadSession).filter(
                PayslipUploadSession.upload_session_id == UUID(upload_session_id)
            ).first()
            if session:
                session.status = 'failed'
                session.updated_at = datetime.utcnow()
                db.commit()
        except:
            pass
        
        return {'status': 'error', 'error': str(e)}
    
    finally:
        db.close()
