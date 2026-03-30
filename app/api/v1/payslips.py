from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime
from io import BytesIO

from app.config.database import get_db
from app.models.database import Payslip, Employee, Company, UserCompanyRole
from app.services.pdf_service import PayslipPDFService
from app.repositories.payslip_repository import PayslipRepository
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.company_repository import CompanyRepository
from app.utils.auth import get_current_user, CurrentUser, check_access_payslip, check_list_access, UserRole
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/payslips", tags=["payslips"])

# Initialize PDF service (can be moved to dependency if needed)
pdf_service = PayslipPDFService()


@router.get("/{payslip_id}/pdf")
def get_payslip_pdf(
    payslip_id: UUID,
    download: bool = Query(False, description="True for download, False for view inline"),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get payslip as PDF
    
    GET /api/v1/payslips/{payslip_id}/pdf?download=false
    - download=false: View inline in browser
    - download=true: Download as attachment
    
    Access control:
    - admin: Can access any payslip
    - client_admin: Can access payslips in their company
    - client: Can only access their own payslip
    """
    try:
        # Fetch payslip from DB
        payslip_repo = PayslipRepository(db)
        payslip = payslip_repo.get_by_id(payslip_id)
        
        if not payslip:
            raise HTTPException(status_code=404, detail="Payslip not found")
        
        # Check access control
        employee = db.query(Employee).filter(Employee.id == payslip.employee_id).first()
        check_access_payslip(
            current_user=current_user,
            db=db,
            payslip_company_id=payslip.company_id,
            payslip_employee_id=payslip.employee_id,
            employee_user_id=employee.user_id if employee else None
        )
        
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        # Fetch company details
        company_repo = CompanyRepository(db)
        company = company_repo.get_by_id(payslip.company_id)
        
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        # Construct employee full name from first_name and last_name
        full_name = f"{employee.first_name} {employee.last_name}".strip()
        
        # Get department and position from payslip (already stored there)
        department = payslip.department or 'N/A'
        position = payslip.position or 'N/A'
        
        # Extract earnings & deductions from JSON
        earnings = payslip.earnings or {}
        deductions = payslip.deductions or {}
        
        # Generate PDF
        pdf_bytes = pdf_service.generate_payslip_pdf(
            employee_id=employee.employee_number,
            employee_name=full_name,
            employee_department=department,
            employee_position=position,
            employee_join_date=employee.join_date,
            employee_bank_account=employee.bank_account,
            
            company_name=company.name,
            company_address='',  # Not in Company model
            company_phone='',  # Not in Company model
            company_logo=None,
            
            period_start=payslip.period_start,
            period_end=payslip.period_end,
            payment_date=payslip.payment_date,
            
            earnings=earnings,
            deductions=deductions,
            total_earnings=float(payslip.gross_salary),
            total_deductions=float(payslip.total_deductions),
            net_salary=float(payslip.net_salary),
        )
        
        # Prepare filename
        filename = f"Payslip_{employee.employee_number}_{payslip.period_start.strftime('%Y%m%d')}.pdf"
        
         # Return PDF
        if download:
            # Download as file attachment
            return StreamingResponse(
                BytesIO(pdf_bytes),
                media_type='application/pdf',
                headers={'Content-Disposition': f'attachment; filename="{filename}"'}
            )
        else:
            # View inline in browser
            return StreamingResponse(
                BytesIO(pdf_bytes),
                media_type='application/pdf',
                headers={'Content-Disposition': f'inline; filename="{filename}"'}
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error generating payslip PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")


@router.get("/employee/{employee_id}/period/{period_start}")
def get_payslip_by_employee_period(
    employee_id: UUID,
    period_start: str,  # Format: "2025-03-01"
    download: bool = Query(False),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get payslip by employee_id and period_start
    
    GET /api/v1/payslips/employee/{employee_id}/period/2025-03-01?download=false
    
    Access control:
    - admin: Can access any payslip
    - client_admin: Can access payslips in their company
    - client: Can only access their own payslip
    """
    try:
        from datetime import datetime as dt
        
        # Parse period_start
        try:
            period_date = dt.strptime(period_start, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid period format. Use YYYY-MM-DD")
        
        # Fetch payslip
        payslip_repo = PayslipRepository(db)
        payslip = db.query(Payslip).filter(
            Payslip.employee_id == employee_id,
            Payslip.period_start == period_date
        ).first()
        
        if not payslip:
            raise HTTPException(status_code=404, detail="Payslip not found for this period")
        
        # Fetch employee & company
        employee = db.query(Employee).filter(Employee.id == employee_id).first()
        company = db.query(Company).filter(Company.id == payslip.company_id).first()
        
        if not employee or not company:
            raise HTTPException(status_code=404, detail="Employee or company not found")
        
        # Check access control
        check_access_payslip(
            current_user=current_user,
            db=db,
            payslip_company_id=payslip.company_id,
            payslip_employee_id=payslip.employee_id,
            employee_user_id=employee.user_id
        )
        
        # Construct employee full name from first_name and last_name
        full_name = f"{employee.first_name} {employee.last_name}".strip()
        
        # Get department and position from payslip (already stored there)
        department = payslip.department or 'N/A'
        position = payslip.position or 'N/A'
        
        # Extract data
        earnings = payslip.earnings or {}
        deductions = payslip.deductions or {}
        
        # Generate PDF
        pdf_bytes = pdf_service.generate_payslip_pdf(
            employee_id=employee.employee_number,
            employee_name=full_name,
            employee_department=department,
            employee_position=position,
            employee_join_date=employee.join_date,
            employee_bank_account=employee.bank_account,
            
            company_name=company.name,
            company_address='',
            company_phone='',
            company_logo=None,
            
            period_start=payslip.period_start,
            period_end=payslip.period_end,
            payment_date=payslip.payment_date,
            
            earnings=earnings,
            deductions=deductions,
            total_earnings=float(payslip.gross_salary),
            total_deductions=float(payslip.total_deductions),
            net_salary=float(payslip.net_salary),
        )
        
        filename = f"Payslip_{employee.employee_number}_{period_start}.pdf"
        
        if download:
            return FileResponse(
                BytesIO(pdf_bytes),
                media_type='application/pdf',
                filename=filename
            )
        else:
            return StreamingResponse(
                BytesIO(pdf_bytes),
                media_type='application/pdf',
                headers={'Content-Disposition': f'inline; filename="{filename}"'}
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/employee/{employee_id}")
def list_employee_payslips(
    employee_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all payslips for an employee
    
    GET /api/v1/payslips/employee/{employee_id}?limit=20&offset=0
    
    Access control:
    - admin: Can list any employee's payslips
    - client_admin: Can list payslips for employees in their company
    - client: Can only list their own payslips
    """
    try:
        # Check access control
        employee = db.query(Employee).filter(Employee.id == employee_id).first()
        
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        check_list_access(
            current_user=current_user,
            db=db,
            target_company_id=employee.company_id,
            target_employee_id=employee_id
        )
        
        # Build query based on role
        query = db.query(Payslip).filter(Payslip.employee_id == employee_id)
        
        # EMPLOYEE role: only get payslips if they are the employee
        if current_user.role == UserRole.EMPLOYEE:
            # Ensure they own this employee record
            if employee.user_id != current_user.user_id:
                raise HTTPException(status_code=403, detail="Access denied")
        
        # HR role: filter to their company
        elif current_user.role == UserRole.HR:
            # Ensure employee is in their company
            if employee.company_id != current_user.company_id:
                raise HTTPException(status_code=403, detail="Employee not in your company")
        
        # ADMIN role: no additional filtering needed
        
        # Execute query with pagination
        payslips = query.order_by(
            Payslip.period_start.desc()
        ).offset(offset).limit(limit).all()
        
        total_count = query.count()
        
        return {
            'total': total_count,
            'limit': limit,
            'offset': offset,
            'payslips': [
                {
                    'id': str(p.id),
                    'employee_id': str(p.employee_id),
                    'period_start': p.period_start.isoformat(),
                    'period_end': p.period_end.isoformat(),
                    'gross_salary': float(p.gross_salary),
                    'total_deductions': float(p.total_deductions),
                    'net_salary': float(p.net_salary),
                    'status': p.status,
                }
                for p in payslips
            ]
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/companies/{company_id}/payslips")
def list_company_payslips(
    company_id: UUID,
    period_start: str = Query(None, description="Filter by period start (YYYY-MM-DD)"),
    period_end: str = Query(None, description="Filter by period end (YYYY-MM-DD)"),
    employee_id: UUID = Query(None, description="Filter by employee ID"),
    status: str = Query(None, description="Filter by status (draft, generated)"),
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List all payslips for a company
    
    GET /api/v1/payslips/companies/{company_id}/payslips
    
    Access control:
    - admin: Can list any payslip in the company
    - hr: Can list payslips in their company
    - employee: Can view their own payslips (auto-detected by user_id)
    """
    try:
        # Check access control
        employee_id_for_query = employee_id
        
        if current_user.role == UserRole.EMPLOYEE:
            # Auto-detect employee_id from current user
            employee = db.query(Employee).filter(
                Employee.user_id == current_user.user_id
            ).first()
            if not employee:
                # No employee record found, return empty list
                return {
                    'data': [],
                    'pagination': {
                        'page': page,
                        'per_page': per_page,
                        'total_pages': 1,
                        'total': 0
                    }
                }
            employee_id_for_query = employee.id
        
        elif current_user.role == UserRole.HR:
            if current_user.company_id != company_id and current_user.role != UserRole.ADMIN:
                raise HTTPException(
                    status_code=403,
                    detail="Access denied: Company mismatch"
                )
        
        # ADMIN role: no additional filtering needed
        
        # Build query
        query = db.query(Payslip).filter(Payslip.company_id == company_id)
        
        # Apply filters
        if period_start:
            try:
                period_start_date = datetime.strptime(period_start, "%Y-%m-%d").date()
                query = query.filter(Payslip.period_start >= period_start_date)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid period_start format. Use YYYY-MM-DD")
        
        if period_end:
            try:
                period_end_date = datetime.strptime(period_end, "%Y-%m-%d").date()
                query = query.filter(Payslip.period_end <= period_end_date)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid period_end format. Use YYYY-MM-DD")
        
        if employee_id_for_query:
            query = query.filter(Payslip.employee_id == employee_id_for_query)
        
        if status:
            query = query.filter(Payslip.status == status)
        
        # Get employee info for each payslip
        employee_ids = [p.employee_id for p in query.all()]
        employees = db.query(Employee).filter(Employee.id.in_(employee_ids)).all() if employee_ids else []
        employee_map = {str(e.id): e for e in employees}
        
        # Count total before pagination
        total_count = query.count()
        
        # Apply pagination
        offset = (page - 1) * per_page
        payslips = query.order_by(Payslip.period_start.desc()).offset(offset).limit(per_page).all()
        
        # Build response
        data = []
        for p in payslips:
            emp = employee_map.get(str(p.employee_id))
            emp_name = f"{emp.first_name} {emp.last_name}".strip() if emp else p.full_name
            
            data.append({
                'id': str(p.id),
                'company_id': str(p.company_id),
                'employee_id': str(p.employee_id),
                'employee_name': emp_name,
                'position': p.position,
                'department': p.department,
                'period_start': p.period_start.isoformat(),
                'period_end': p.period_end.isoformat(),
                'payment_date': p.payment_date.isoformat(),
                'gross_salary': float(p.gross_salary),
                'total_deductions': float(p.total_deductions),
                'net_salary': float(p.net_salary),
                'status': p.status,
                'has_pdf': p.file_url is not None,
                'created_at': p.created_at.isoformat() if p.created_at else None
            })
        
        return {
            'success': True,
            'data': data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total_items': total_count,
                'total_pages': (total_count + per_page - 1) // per_page
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing payslips: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/companies/{company_id}/payslips/{payslip_id}/download")
def download_payslip_pdf(
    company_id: UUID,
    payslip_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Download payslip PDF
    
    GET /api/v1/payslips/companies/{company_id}/payslips/{payslip_id}/download
    
    Access control:
    - admin: Can download any payslip
    - client_admin: Can download payslips in their company
    - client: Can only download their own payslip
    """
    try:
        # Fetch payslip
        payslip = db.query(Payslip).filter(
            Payslip.id == payslip_id,
            Payslip.company_id == company_id
        ).first()
        
        if not payslip:
            raise HTTPException(status_code=404, detail="Payslip not found")
        
        # Fetch employee
        employee = db.query(Employee).filter(Employee.id == payslip.employee_id).first()
        
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        # Check access control
        check_access_payslip(
            current_user=current_user,
            db=db,
            payslip_company_id=payslip.company_id,
            payslip_employee_id=payslip.employee_id,
            employee_user_id=employee.user_id
        )
        
        # Check if file_url exists and redirect to it
        if payslip.file_url:
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url=payslip.file_url, status_code=303)
        
        # Generate PDF on-demand if no file_url
        # Fetch company details
        company = db.query(Company).filter(Company.id == payslip.company_id).first()
        
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        
        full_name = f"{employee.first_name} {employee.last_name}".strip()
        department = payslip.department or 'N/A'
        position = payslip.position or 'N/A'
        
        earnings = payslip.earnings or {}
        deductions = payslip.deductions or {}
        
        pdf_bytes = pdf_service.generate_payslip_pdf(
            employee_id=employee.employee_number,
            employee_name=full_name,
            employee_department=department,
            employee_position=position,
            employee_join_date=employee.join_date,
            employee_bank_account=employee.bank_account or '',
            company_name=company.name,
            company_address='',
            company_phone='',
            company_logo=None,
            period_start=payslip.period_start,
            period_end=payslip.period_end,
            payment_date=payslip.payment_date,
            earnings=earnings,
            deductions=deductions,
            total_earnings=float(payslip.gross_salary),
            total_deductions=float(payslip.total_deductions),
            net_salary=float(payslip.net_salary),
        )
        
        filename = f"Payslip_{employee.employee_number}_{payslip.period_start.strftime('%Y%m%d')}.pdf"
        
        return StreamingResponse(
            BytesIO(pdf_bytes),
            media_type='application/pdf',
            headers={'Content-Disposition': f'attachment; filename="{filename}"'}
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading payslip PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/companies/{company_id}/payslips/pdf-status")
def get_pdf_generation_status(
    company_id: UUID,
    period_start: str = Query(None, description="Filter by period start (YYYY-MM-DD)"),
    period_end: str = Query(None, description="Filter by period end (YYYY-MM-DD)"),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get PDF generation status for a company
    
    GET /api/v1/payslips/companies/{company_id}/payslips/pdf-status
    
    Access control:
    - admin: Can view any company status
    - client_admin: Can view their company status
    - client: Not allowed
    """
    try:
        if current_user.role == UserRole.EMPLOYEE:
            raise HTTPException(status_code=403, detail="Access denied")
        
        if current_user.role == UserRole.HR:
            if current_user.company_id != company_id:
                raise HTTPException(status_code=403, detail="Access denied: Company mismatch")
        
        # Build query
        query = db.query(Payslip).filter(Payslip.company_id == company_id)
        
        if period_start:
            try:
                period_start_date = datetime.strptime(period_start, "%Y-%m-%d").date()
                query = query.filter(Payslip.period_start >= period_start_date)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid period_start format")
        
        if period_end:
            try:
                period_end_date = datetime.strptime(period_end, "%Y-%m-%d").date()
                query = query.filter(Payslip.period_end <= period_end_date)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid period_end format")
        
        total_payslips = query.count()
        generated_count = query.filter(Payslip.file_url.isnot(None)).count()
        pending_count = total_payslips - generated_count
        
        return {
            'success': True,
            'pdf_status': {
                'total_payslips': total_payslips,
                'generated': generated_count,
                'pending': pending_count,
                'percentage': round((generated_count / total_payslips * 100) if total_payslips > 0 else 0, 2)
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting PDF status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/companies/{company_id}/payslips/{payslip_id}")
def get_payslip_detail(
    company_id: UUID,
    payslip_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get payslip detail by ID
    
    GET /api/v1/payslips/companies/{company_id}/payslips/{payslip_id}
    
    Access control:
    - admin: Can view any payslip
    - client_admin: Can view payslips in their company
    - client: Can only view their own payslip
    """
    try:
        # Fetch payslip
        payslip = db.query(Payslip).filter(
            Payslip.id == payslip_id,
            Payslip.company_id == company_id
        ).first()
        
        if not payslip:
            raise HTTPException(status_code=404, detail="Payslip not found")
        
        # Fetch employee
        employee = db.query(Employee).filter(Employee.id == payslip.employee_id).first()
        
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")
        
        # Check access control
        check_access_payslip(
            current_user=current_user,
            db=db,
            payslip_company_id=payslip.company_id,
            payslip_employee_id=payslip.employee_id,
            employee_user_id=employee.user_id
        )
        
        # Build response
        full_name = f"{employee.first_name} {employee.last_name}".strip()
        
        return {
            'success': True,
            'payslip': {
                'id': str(payslip.id),
                'company_id': str(payslip.company_id),
                'employee_id': str(payslip.employee_id),
                'employee_name': full_name,
                'employee_number': employee.employee_number,
                'position': payslip.position,
                'department': payslip.department,
                'period_start': payslip.period_start.isoformat(),
                'period_end': payslip.period_end.isoformat(),
                'payment_date': payslip.payment_date.isoformat(),
                'earnings': payslip.earnings or {},
                'gross_salary': float(payslip.gross_salary),
                'deductions': payslip.deductions or {},
                'total_deductions': float(payslip.total_deductions),
                'net_salary': float(payslip.net_salary),
                'status': payslip.status,
                'has_pdf': payslip.file_url is not None,
                'file_url': payslip.file_url,
                'notes': payslip.notes,
                'created_at': payslip.created_at.isoformat() if payslip.created_at else None
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting payslip detail: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))