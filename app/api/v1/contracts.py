from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session
from uuid import UUID
from datetime import datetime
from typing import Optional
from pydantic import BaseModel
import logging

from app.config.database import get_db
from app.models.database import Employee
from app.services.contract_service import ContractService
from app.utils.auth import get_current_user, CurrentUser, check_admin_access, UserRole
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["contracts"])

CONTRACT_BUCKET = os.getenv('SUPABASE_STORAGE_BUCKET', 'contracts')


class UpdateContractRequest(BaseModel):
    contract_type: Optional[str] = None
    job_title: Optional[str] = None
    department: Optional[str] = None
    base_salary: Optional[float] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


def check_contract_access(
    current_user: CurrentUser,
    db: Session,
    contract_employee_id: UUID,
    contract_company_id: UUID,
    employee_user_id: UUID = None
):
    """Check if user can access a contract"""
    if current_user.role == UserRole.ADMIN:
        return True
    
    if contract_company_id != current_user.company_id:
        raise HTTPException(status_code=403, detail="Access denied: Contract belongs to different company")
    
    if current_user.role == UserRole.HR:
        return True
    
    if current_user.role == UserRole.EMPLOYEE:
        if employee_user_id and current_user.user_id != employee_user_id:
            raise HTTPException(status_code=403, detail="Access denied: You can only access your own contract")
        return True
    
    raise HTTPException(status_code=403, detail="Access denied")


@router.post("/companies/{company_id}/contracts")
async def create_contract(
    company_id: UUID,
    employee_id: str = Form(...),
    contract_type: str = Form(...),
    job_title: str = Form(...),
    department: str = Form(...),
    base_salary: float = Form(...),
    start_date: str = Form(...),
    end_date: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a new contract for an employee
    
    POST /api/v1/companies/{company_id}/contracts
    
    Auth: admin only
    
    Form Fields:
    - employee_id: UUID of employee
    - contract_type: Type (PKWT, PKWTT, etc.)
    - job_title: Position
    - department: Department
    - base_salary: Base salary
    - start_date: Start date (YYYY-MM-DD)
    - end_date: End date (YYYY-MM-DD, optional)
    
    File: PDF contract file (required)
    """
    check_admin_access(current_user)
    
    if current_user.company_id != company_id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied: Company mismatch")
    
    employee_uuid = UUID(employee_id)
    
    employee = db.query(Employee).filter(Employee.id == employee_uuid).first()
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    if str(employee.company_id) != str(company_id):
        raise HTTPException(status_code=400, detail="Employee does not belong to this company")
    
    file_content = None
    file_name = None
    if file:
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="File must be PDF format")
        file_content = await file.read()
        file_name = file.filename
    
    try:
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date_obj = None
        if end_date:
            end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    service = ContractService(db)
    
    try:
        contract = service.create_contract(
            company_id=company_id,
            employee_id=employee_uuid,
            contract_type=contract_type,
            job_title=job_title,
            department=department,
            base_salary=base_salary,
            start_date=start_date_obj,
            end_date=end_date_obj,
            file_content=file_content,
            file_name=file_name,
            created_by=str(current_user.user_id)
        )
        
        return {
            "success": True,
            "message": "Contract created successfully",
            "contract": contract
        }
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating contract: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/companies/{company_id}/contracts/{contract_id}")
async def update_contract(
    company_id: UUID,
    contract_id: UUID,
    request: UpdateContractRequest,
    file: UploadFile = File(None),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update an existing contract
    
    PUT /api/v1/companies/{company_id}/contracts/{contract_id}
    
    Auth: admin, client_admin
    """
    check_admin_access(current_user)
    
    if current_user.company_id != company_id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied: Company mismatch")
    
    file_content = None
    file_name = None
    if file:
        if not file.filename.endswith('.pdf'):
            raise HTTPException(status_code=400, detail="File must be PDF format")
        file_content = await file.read()
        file_name = file.filename
    
    start_date = None
    end_date = None
    if request.start_date:
        try:
            start_date = datetime.strptime(request.start_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format")
    
    if request.end_date:
        try:
            end_date = datetime.strptime(request.end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format")
    
    service = ContractService(db)
    
    try:
        contract = service.update_contract(
            contract_id=contract_id,
            company_id=company_id,
            contract_type=request.contract_type,
            job_title=request.job_title,
            department=request.department,
            base_salary=request.base_salary,
            start_date=start_date,
            end_date=end_date,
            file_content=file_content,
            file_name=file_name
        )
        
        return {
            "success": True,
            "message": "Contract updated successfully",
            "contract": contract
        }
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating contract: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/companies/{company_id}/contracts")
def list_contracts(
    company_id: UUID,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    employee_id: UUID = None,
    contract_type: str = None,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List contracts in a company
    
    GET /api/v1/companies/{company_id}/contracts
    
    Auth: admin, hr, employee (own contracts only)
    """
    if current_user.role == UserRole.EMPLOYEE:
        employee = db.query(Employee).filter(
            Employee.user_id == current_user.user_id,
            Employee.company_id == company_id
        ).first()
        
        if not employee:
            raise HTTPException(status_code=403, detail="You don't belong to this company")
        
        employee_id = employee.id
    
    if current_user.company_id != company_id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied: Company mismatch")
    
    service = ContractService(db)
    
    result = service.list_company_contracts(
        company_id=company_id,
        limit=limit,
        offset=offset,
        employee_id=employee_id,
        contract_type=contract_type
    )
    
    return {
        "success": True,
        **result
    }


@router.get("/companies/{company_id}/contracts/{contract_id}")
def get_contract(
    company_id: UUID,
    contract_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get contract details
    
    GET /api/v1/companies/{company_id}/contracts/{contract_id}
    
    Auth: admin, client_admin, client (own contract only)
    """
    employee = db.query(Employee).filter(Employee.id == Employee.id).first()
    
    contract_service = ContractService(db)
    
    try:
        contract_data = contract_service.get_contract(contract_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    employee = db.query(Employee).filter(Employee.id == UUID(contract_data['employee_id'])).first()
    
    check_contract_access(
        current_user=current_user,
        db=db,
        contract_employee_id=UUID(contract_data['employee_id']),
        contract_company_id=UUID(contract_data['company_id']),
        employee_user_id=employee.user_id if employee else None
    )
    
    return {
        "success": True,
        "contract": contract_data
    }


@router.get("/companies/{company_id}/contracts/{contract_id}/download")
def download_contract(
    company_id: UUID,
    contract_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get contract PDF download URL
    
    GET /api/v1/companies/{company_id}/contracts/{contract_id}/download
    
    Auth: admin, client_admin, client (own contract only)
    
    Returns redirect to PDF file URL
    """
    contract_service = ContractService(db)
    
    try:
        contract_data = contract_service.get_contract(contract_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Contract not found")
    
    employee = db.query(Employee).filter(Employee.id == UUID(contract_data['employee_id'])).first()
    
    check_contract_access(
        current_user=current_user,
        db=db,
        contract_employee_id=UUID(contract_data['employee_id']),
        contract_company_id=UUID(contract_data['company_id']),
        employee_user_id=employee.user_id if employee else None
    )
    
    if not contract_data.get('has_file'):
        raise HTTPException(status_code=404, detail="No file attached to this contract")
    
    try:
        download_url = contract_service.get_contract_download_url(contract_id)
        return RedirectResponse(url=download_url, status_code=303)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/employees/{employee_id}/contract")
def get_employee_contract(
    employee_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get own contract (for employees)
    
    GET /api/v1/employees/{employee_id}/contract
    
    Auth: employee (own contract only)
    """
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    
    if not employee:
        raise HTTPException(status_code=404, detail="Employee not found")
    
    if current_user.role == UserRole.EMPLOYEE:
        if employee.user_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="Access denied")
        
        if str(employee.company_id) != str(current_user.company_id):
            raise HTTPException(status_code=403, detail="Access denied")
    
    if current_user.role in [UserRole.ADMIN, UserRole.HR]:
        if str(employee.company_id) != str(current_user.company_id) and current_user.role != UserRole.ADMIN:
            raise HTTPException(status_code=403, detail="Access denied")
    
    service = ContractService(db)
    
    try:
        contract = service.get_employee_contract(employee_id)
        return {
            "success": True,
            "contract": contract
        }
    except ValueError:
        raise HTTPException(status_code=404, detail="No contract found for this employee")


@router.delete("/companies/{company_id}/contracts/{contract_id}")
def delete_contract(
    company_id: UUID,
    contract_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete a contract
    
    DELETE /api/v1/companies/{company_id}/contracts/{contract_id}
    
    Auth: admin, client_admin
    """
    check_admin_access(current_user)
    
    if current_user.company_id != company_id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Access denied: Company mismatch")
    
    service = ContractService(db)
    
    try:
        success = service.delete_contract(contract_id, company_id)
        if success:
            return {
                "success": True,
                "message": "Contract deleted successfully"
            }
        else:
            raise HTTPException(status_code=404, detail="Contract not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting contract: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
