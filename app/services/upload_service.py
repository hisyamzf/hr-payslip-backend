from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from app.models.database import Payslip, Employee, Company
from app.repositories.company_repository import CompanyRepository
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.payslip_repository import PayslipRepository
from app.repositories.upload_session_repository import UploadSessionRepository
from app.services.validation_service import ValidationService
from app.services.pdf_service import PayslipPDFService
from app.utils.excel_parser import ExcelParser
from app.utils.hashing import calculate_file_hash
from uuid import UUID, uuid4
from datetime import datetime
import logging
from decimal import Decimal
import os

logger = logging.getLogger(__name__)

class UploadService:
    def __init__(self, session: Session):
        self.session = session
        self.company_repo = CompanyRepository(session)
        self.employee_repo = EmployeeRepository(session)
        self.payslip_repo = PayslipRepository(session)
        self.upload_session_repo = UploadSessionRepository(session)
        self.validation_service = ValidationService(session)
        self.excel_parser = ExcelParser(max_rows=None, skip_empty_rows=True)
        self.pdf_service = PayslipPDFService()
    
    def create_upload_session(
        self,
        company_id: UUID,
        file_path: str,
        file_hash: str,
        period_start,
        period_end,
        payment_date,
        created_by: str
    ):
        """
        Step 1: Create upload session
        """
        # Verify company exists
        if not self.company_repo.company_exists(company_id):
            raise ValueError(f"Company {company_id} not found")
        
        upload_session = None
        try:
            # Create session record
            session_data = {
                'upload_session_id': uuid4(),
                'company_id': company_id,
                'file_path': file_path,
                'file_hash': file_hash,
                'period_start': period_start,
                'period_end': period_end,
                'payment_date': payment_date,
                'status': 'pending',
                'created_by': created_by,
            }
            
            upload_session = self.upload_session_repo.create_session(session_data)
            self.session.flush()
            self.session.commit()
            
            logger.info(f"Created upload session {upload_session.upload_session_id}")
            return upload_session
        
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Error creating upload session: {e}")
            raise
    
    def submit_column_mapping(self, upload_session_id: UUID, column_mapping: dict):
        """
        Step 2: Save column mapping from admin
        """
        try:
            session = self._get_session(upload_session_id)
            session.column_mapping = column_mapping
            session.status = 'mapped'
            self.session.commit()
            
            logger.info(f"Saved column mapping for {upload_session_id}")
            return session
        
        except SQLAlchemyError as e:
            self.session.rollback()
            logger.error(f"Error submitting mapping: {e}")
            raise
    
    def process_upload(self, upload_session_id: UUID, start_row: int = None):
        """
        Step 3-9: Main processing function
        """
        try:
            session = self._get_session(upload_session_id)
            session_db_id = session.id
            
            # Update status to processing
            self.upload_session_repo.update_status(upload_session_id, 'inserting')
            self.session.commit()
            
            # Get column mapping dari session
            column_mapping = session.column_mapping
            if not column_mapping:
                raise ValueError("Column mapping tidak ditemukan untuk session ini")
            
            # CHANGE: Parse Excel dengan real parser + column_mapping
            start_row = column_mapping.get('start_row', 2)
            rows = self.excel_parser.parse_file(session.file_path, column_mapping, start_row=start_row)
            logger.info(f"✅ Parsed {len(rows)} rows from Excel")
            
            # Initialize tracking
            payslips_to_insert = []
            upload_rows = []
            successful_count = 0
            failed_count = 0
            errors = []
            
            # Process each row
            for row_data in rows:
                row_number = row_data.get('row_number')
                employee_number = row_data.get('employee_number')
                
                # Validation
                is_valid, error_msg = self.validation_service.validate_row(
                    row_data,
                    session.company_id,
                    session.period_start
                )
                
                if not is_valid:
                    # Track failed row
                    upload_rows.append({
                        'upload_session_id': session_db_id,
                        'row_number': row_number,
                        'employee_number': employee_number,
                        'status': 'failed',
                        'error_message': error_msg,
                        'raw_data': row_data,
                    })
                    errors.append({
                        'row_number': row_number,
                        'employee_number': employee_number,
                        'error': error_msg
                    })
                    failed_count += 1
                    continue
                
                # Transform & prepare payslip
                payslip_data = self._transform_row_to_payslip(
                    row_data,
                    session.company_id,
                    employee_number,
                    session.period_start,
                    session.period_end,
                    session.payment_date
                )
                
                payslips_to_insert.append(payslip_data)
                
                # Will update row status after successful insert
                upload_rows.append({
                    'upload_session_id': session_db_id,
                    'row_number': row_number,
                    'employee_number': employee_number,
                    'status': 'pending',  # Will be updated after insert
                    'raw_data': row_data,
                })
                
                successful_count += 1
            
            # Batch insert payslips
            if payslips_to_insert:
                inserted_payslips = self.payslip_repo.insert_batch(payslips_to_insert)
                self.session.flush()  # Get generated IDs
                logger.info(f"Inserted {len(inserted_payslips)} payslips")
                
                # Generate PDF synchronously for successful payslips
                try:
                    self._generate_pdfs_sync(inserted_payslips)
                except Exception as e:
                    logger.warning(f"⚠️  PDF generation error (non-blocking): {str(e)}")

                # Mapping employee_number dari row_data ke payslip.id
                emp_to_payslip_id = {
                    row_data['employee_number']: p.id 
                    for row_data, p in zip(rows, inserted_payslips)
                }

                for upload_row in upload_rows:
                    if upload_row['status'] == 'pending':
                        emp_num = upload_row['employee_number']
                        if emp_num in emp_to_payslip_id:
                            upload_row['status'] = 'success'
                            upload_row['payslip_id'] = emp_to_payslip_id[emp_num]
            
            # Update session result
            result = {
                'total_rows': len(rows),
                'successful_inserts': len(payslips_to_insert),
                'failed': failed_count,
                'errors': errors
            }
            
            self.upload_session_repo.set_result(upload_session_id, result)
            
            # Commit all
            self.session.commit()
            
            logger.info(f"✅ Upload {upload_session_id} completed: {result}")
            return result
        
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error processing upload {upload_session_id}: {e}")
            
            # Mark session as failed
            try:
                self.upload_session_repo.update_status(upload_session_id, 'failed')
                self.session.commit()
            except:
                pass
            
            raise
    
    # Private helper methods
    
    def _get_session(self, upload_session_id: UUID):
        """Get upload session or raise error"""
        session = self.upload_session_repo.get_session(upload_session_id)
        if not session:
            raise ValueError(f"Upload session {upload_session_id} not found")
        return session
    
    def _transform_row_to_payslip(
        self,
        row_data: dict,
        company_id: UUID,
        employee_number: str,
        period_start,
        period_end,
        payment_date
    ) -> dict:
        """
        Transform Excel row into payslip record
        """
        # Get employee for snapshot data
        employee = self.employee_repo.get_by_employee_number_and_company(employee_number, company_id)
        
        # Extract earnings & deductions from row
        earnings = row_data.get('earnings', {})
        deductions = row_data.get('deductions', {})
        
        # Calculate totals
        gross_salary = sum(Decimal(str(v)) for v in earnings.values())
        total_deductions = sum(Decimal(str(v)) for v in deductions.values())
        net_salary = gross_salary - total_deductions
        
        return {
            'company_id': company_id,
            'employee_id': employee.id,
            'period_start': period_start,
            'period_end': period_end,
            'payment_date': payment_date,
            'full_name': row_data.get('full_name', f"{employee.first_name} {employee.last_name}"),
            'department': row_data.get('department', 'N/A'),
            'position': row_data.get('position', 'N/A'),
            'earnings': earnings,
            'deductions': deductions,
            'gross_salary': float(gross_salary),
            'total_deductions': float(total_deductions),
            'net_salary': float(net_salary),
            'status': 'draft',
        }
    
    def _queue_pdf_generation(self, inserted_payslips: list):
        """
        Queue PDF generation for successfully inserted payslips
        Uses Celery for async processing
        """
        try:
            pdf_count = len(inserted_payslips)
            logger.info(f"📑 Queued {pdf_count} payslips for PDF generation")
            
            is_async = os.getenv('CELERY_BROKER_URL')
            
            if is_async:
                from app.tasks.pdf_tasks import batch_process_payslips
                
                payslip_ids = [str(p.id) for p in inserted_payslips]
                task = batch_process_payslips.delay(payslip_ids)
                
                logger.info(f"📋 Celery task queued: {task.id}")
                return task.id
            else:
                logger.info("ℹ️  Celery not configured, skipping async PDF generation")
                return None
            
        except Exception as e:
            logger.warning(f"⚠️  Error in PDF queue: {str(e)}")
            return None
    
    def _generate_pdfs_sync(self, inserted_payslips: list):
        """
        Generate PDF synchronously for all inserted payslips
        """
        try:
            from app.services.pdf_service import PayslipPDFService
            from app.repositories.employee_repository import EmployeeRepository
            
            pdf_service = PayslipPDFService()
            employee_repo = EmployeeRepository(self.session)
            
            for payslip in inserted_payslips:
                try:
                    logger.info(f"Generating PDF for payslip {payslip.id}")
                    
                    # Get employee data
                    employee = employee_repo.get_by_id(payslip.employee_id)
                    if not employee:
                        logger.warning(f"Employee not found for payslip {payslip.id}")
                        continue
                    
                    # Get company data
                    company = payslip.company_id
                    
                    # Get earnings and deductions from payslip JSON
                    earnings = payslip.earnings_json or {}
                    deductions = payslip.deductions_json or {}
                    
                    # Generate PDF
                    pdf_bytes = pdf_service.generate_payslip_pdf(
                        employee_id=employee.employee_number,
                        employee_name=employee.first_name or '',
                        employee_department=employee.department or '',
                        employee_position=employee.position or '',
                        employee_join_date=employee.join_date,
                        employee_bank_account=employee.bank_account,
                        company_name=company.name if company else "Company",
                        period_start=payslip.period_start,
                        period_end=payslip.period_end,
                        payment_date=payslip.payment_date,
                        earnings=earnings,
                        deductions=deductions,
                        total_earnings=payslip.gross_salary or 0,
                        total_deductions=payslip.total_deduction or 0,
                        net_salary=payslip.net_salary or 0,
                    )
                    
                    # Save PDF to storage (Supabase)
                    if pdf_bytes:
                        pdf_url = self._save_pdf_to_storage(payslip.id, pdf_bytes)
                        if pdf_url:
                            payslip.pdf_url = pdf_url
                            payslip.status = 'completed'
                            self.session.commit()
                            logger.info(f"✅ PDF generated for payslip {payslip.id}")
                except Exception as e:
                    logger.warning(f"⚠️  Error generating PDF for payslip {payslip.id}: {str(e)}")
                    continue
            
            logger.info(f"✅ Generated PDFs for {len(inserted_payslips)} payslips")
        except Exception as e:
            logger.warning(f"⚠️  Error in sync PDF generation: {str(e)}")
    
    def _save_pdf_to_storage(self, payslip_id, pdf_bytes: bytes) -> str:
        """Save PDF to Supabase storage"""
        try:
            from app.utils.supabase_client import get_supabase_client
            supabase = get_supabase_client()
            
            file_name = f"payslips/{payslip_id}.pdf"
            supabase.storage.from_("payslips").upload(
                file_name,
                pdf_bytes,
                {"content-type": "application/pdf", "x-upsert": "true"}
            )
            
            public_url = supabase.storage.from_("payslips").get_public_url(file_name)
            return public_url
        except Exception as e:
            logger.warning(f"⚠️  Error saving PDF to storage: {str(e)}")
            return None
    
    def process_reprocess(
        self,
        child_session_id: UUID,
        column_mapping: dict,
        data_rows: list
    ):
        """
        Process failed rows for reprocess
        """
        try:
            session = self._get_session(child_session_id)
            session_db_id = session.id
            
            self.upload_session_repo.update_status(child_session_id, 'inserting')
            self.session.commit()
            
            payslips_to_insert = []
            upload_rows = []
            successful_count = 0
            failed_count = 0
            errors = []
            
            for row_data in data_rows:
                row_number = row_data.get('row_number', 0)
                employee_number = row_data.get('employee_number', '')
                
                is_valid, error_msg = self.validation_service.validate_row(
                    row_data,
                    session.company_id,
                    session.period_start
                )
                
                if not is_valid:
                    upload_rows.append({
                        'upload_session_id': session_db_id,
                        'row_number': row_number,
                        'employee_number': employee_number,
                        'status': 'failed',
                        'error_message': error_msg,
                        'raw_data': row_data,
                    })
                    errors.append({
                        'row_number': row_number,
                        'employee_number': employee_number,
                        'error': error_msg
                    })
                    failed_count += 1
                    continue
                
                payslip_data = self._transform_row_to_payslip(
                    row_data,
                    session.company_id,
                    employee_number,
                    session.period_start,
                    session.period_end,
                    session.payment_date
                )
                
                payslips_to_insert.append(payslip_data)
                
                upload_rows.append({
                    'upload_session_id': session_db_id,
                    'row_number': row_number,
                    'employee_number': employee_number,
                    'status': 'pending',
                    'raw_data': row_data,
                })
                
                successful_count += 1
            
            if payslips_to_insert:
                inserted_payslips = self.payslip_repo.insert_batch(payslips_to_insert)
                self.session.flush()
                
                try:
                    self._generate_pdfs_sync(inserted_payslips)
                except Exception as e:
                    logger.warning(f"⚠️  PDF generation error (non-blocking): {str(e)}")
                
                emp_to_payslip_id = {
                    row_data.get('employee_number'): p.id 
                    for row_data, p in zip(data_rows, inserted_payslips)
                }
                
                for upload_row in upload_rows:
                    if upload_row['status'] == 'pending':
                        emp_num = upload_row['employee_number']
                        if emp_num in emp_to_payslip_id:
                            upload_row['status'] = 'success'
                            upload_row['payslip_id'] = emp_to_payslip_id[emp_num]
            
            result = {
                'total_rows': len(data_rows),
                'successful_inserts': len(payslips_to_insert),
                'failed': failed_count,
                'errors': errors
            }
            
            self.upload_session_repo.set_result(child_session_id, result)
            
            status = 'completed' if failed_count == 0 else 'completed_with_errors'
            self.upload_session_repo.update_status(child_session_id, status)
            
            self.session.commit()
            
            logger.info(f"✅ Reprocess {child_session_id} completed: {result}")
            return result
        
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error reprocessing {child_session_id}: {e}")
            raise