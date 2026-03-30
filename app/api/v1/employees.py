"""
Employee Management API Endpoints
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import date

from app.config.database import get_db
from app.models.database import Employee, User, UserCompanyRole
from app.utils.auth import get_current_user, CurrentUser, require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["employees"])


class CreateEmployeeRequest(BaseModel):
    user_id: str = Field(..., description="User ID associated with this employee")
    first_name: str = Field(..., example="John")
    last_name: str = Field(..., example="Doe")
    employee_number: str = Field(..., example="EMP001")
    date_of_birth: str = Field(..., description="Date of birth (YYYY-MM-DD)")
    join_date: str = Field(..., description="Join date (YYYY-MM-DD)")
    email: Optional[str] = Field(None, example="john.doe@example.com")
    bank_account: Optional[str] = Field(None, example="1234567890")


class UpdateEmployeeRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    bank_account: Optional[str] = None
    employment_status: Optional[str] = None


class EmployeeResponse(BaseModel):
    id: str
    user_id: str
    employee_number: str
    first_name: str
    last_name: str
    date_of_birth: str
    join_date: str
    email: Optional[str]
    bank_account: Optional[str]
    employment_status: str
    created_at: str


class EmployeeAdminResponse(BaseModel):
    id: str
    user_id: str
    employee_number: str
    first_name: str
    last_name: str
    date_of_birth: str
    join_date: str
    email: Optional[str]
    bank_account: Optional[str]
    employment_status: str
    created_at: str
    company_id: str
    company_name: str
    company_code: str


def parse_date(date_str: str) -> date:
    """Parse date string to date object"""
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid date format: {date_str}. Use YYYY-MM-DD"
        )


@router.get("/companies/{company_id}/employees", response_model=List[EmployeeResponse])
async def list_employees(
    company_id: UUID,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None, description="Filter by employment status"),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List employees in a company
    Requires: HR or Admin role
    """
    if current_user.role.value not in ['admin', 'hr']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: HR or Admin role required"
        )
    
    if company_id != current_user.company_id and current_user.role.value != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Company mismatch"
        )
    
    query = db.query(Employee).filter(Employee.company_id == company_id)
    
    if status:
        query = query.filter(Employee.employment_status == status)
    
    employees = query.order_by(Employee.created_at.desc()).offset(offset).limit(limit).all()
    
    return [
        EmployeeResponse(
            id=str(emp.id),
            user_id=str(emp.user_id),
            employee_number=emp.employee_number,
            first_name=emp.first_name,
            last_name=emp.last_name,
            date_of_birth=emp.date_of_birth.isoformat(),
            join_date=emp.join_date.isoformat(),
            email=emp.email,
            bank_account=emp.bank_account,
            employment_status=emp.employment_status,
            created_at=str(emp.created_at)
        )
        for emp in employees
    ]


@router.get("/admin/employees", response_model=List[EmployeeAdminResponse])
async def list_all_employees(
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status: Optional[str] = Query(None, description="Filter by employment status"),
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List ALL employees across all companies
    Requires: Admin (super admin) role only
    """
    if current_user.role.value != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Admin role required"
        )
    
    query = db.query(Employee).join(Employee.company)
    
    if status:
        query = query.filter(Employee.employment_status == status)
    
    employees = query.order_by(Employee.created_at.desc()).offset(offset).limit(limit).all()
    
    return [
        EmployeeAdminResponse(
            id=str(emp.id),
            user_id=str(emp.user_id),
            employee_number=emp.employee_number,
            first_name=emp.first_name,
            last_name=emp.last_name,
            date_of_birth=emp.date_of_birth.isoformat(),
            join_date=emp.join_date.isoformat(),
            email=emp.email,
            bank_account=emp.bank_account,
            employment_status=emp.employment_status,
            created_at=str(emp.created_at),
            company_id=str(emp.company_id),
            company_name=emp.company.name,
            company_code=emp.company.code
        )
        for emp in employees
    ]


@router.post("/companies/{company_id}/employees", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
async def create_employee(
    company_id: UUID,
    request: CreateEmployeeRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create new employee in a company
    Requires: HR or Admin role
    """
    if current_user.role.value not in ['admin', 'hr']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: HR or Admin role required"
        )
    
    if company_id != current_user.company_id and current_user.role.value != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Company mismatch"
        )
    
    user_id = UUID(request.user_id)
    
    existing_user = db.query(User).filter(User.id == user_id).first()
    if not existing_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    existing_employee = db.query(Employee).filter(
        Employee.user_id == user_id
    ).first()
    if existing_employee:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has an employee record"
        )
    
    existing_number = db.query(Employee).filter(
        Employee.company_id == company_id,
        Employee.employee_number == request.employee_number
    ).first()
    if existing_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Employee number already exists in this company"
        )
    
    try:
        employee = Employee(
            company_id=company_id,
            user_id=user_id,
            first_name=request.first_name,
            last_name=request.last_name,
            employee_number=request.employee_number,
            date_of_birth=parse_date(request.date_of_birth),
            join_date=parse_date(request.join_date),
            email=request.email,
            bank_account=request.bank_account,
            employment_status='active'
        )
        
        db.add(employee)
        db.commit()
        db.refresh(employee)
        
        logger.info(f"Created employee {employee.id} for user {user_id}")
        
        return EmployeeResponse(
            id=str(employee.id),
            user_id=str(employee.user_id),
            employee_number=employee.employee_number,
            first_name=employee.first_name,
            last_name=employee.last_name,
            date_of_birth=employee.date_of_birth.isoformat(),
            join_date=employee.join_date.isoformat(),
            email=employee.email,
            bank_account=employee.bank_account,
            employment_status=employee.employment_status,
            created_at=str(employee.created_at)
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating employee: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create employee"
        )


@router.get("/companies/{company_id}/employees/{employee_id}", response_model=EmployeeResponse)
async def get_employee(
    company_id: UUID,
    employee_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get employee details
    Requires: HR or Admin role
    """
    if current_user.role.value not in ['admin', 'hr']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: HR or Admin role required"
        )
    
    if company_id != current_user.company_id and current_user.role.value != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Company mismatch"
        )
    
    employee = db.query(Employee).filter(
        Employee.id == employee_id,
        Employee.company_id == company_id
    ).first()
    
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found"
        )
    
    return EmployeeResponse(
        id=str(employee.id),
        user_id=str(employee.user_id),
        employee_number=employee.employee_number,
        first_name=employee.first_name,
        last_name=employee.last_name,
        date_of_birth=employee.date_of_birth.isoformat(),
        join_date=employee.join_date.isoformat(),
        email=employee.email,
        bank_account=employee.bank_account,
        employment_status=employee.employment_status,
        created_at=str(employee.created_at)
    )


@router.put("/companies/{company_id}/employees/{employee_id}", response_model=EmployeeResponse)
async def update_employee(
    company_id: UUID,
    employee_id: UUID,
    request: UpdateEmployeeRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Update employee details
    Requires: HR or Admin role
    """
    if current_user.role.value not in ['admin', 'hr']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: HR or Admin role required"
        )
    
    if company_id != current_user.company_id and current_user.role.value != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Company mismatch"
        )
    
    employee = db.query(Employee).filter(
        Employee.id == employee_id,
        Employee.company_id == company_id
    ).first()
    
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found"
        )
    
    if request.first_name is not None:
        employee.first_name = request.first_name
    if request.last_name is not None:
        employee.last_name = request.last_name
    if request.email is not None:
        employee.email = request.email
    if request.bank_account is not None:
        employee.bank_account = request.bank_account
    if request.employment_status is not None:
        employee.employment_status = request.employment_status
    
    db.commit()
    db.refresh(employee)
    
    logger.info(f"Updated employee {employee_id}")
    
    return EmployeeResponse(
        id=str(employee.id),
        user_id=str(employee.user_id),
        employee_number=employee.employee_number,
        first_name=employee.first_name,
        last_name=employee.last_name,
        date_of_birth=employee.date_of_birth.isoformat(),
        join_date=employee.join_date.isoformat(),
        email=employee.email,
        bank_account=employee.bank_account,
        employment_status=employee.employment_status,
        created_at=str(employee.created_at)
    )


@router.delete("/companies/{company_id}/employees/{employee_id}")
async def delete_employee(
    company_id: UUID,
    employee_id: UUID,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Delete employee (soft delete by setting status to inactive)
    Requires: HR or Admin role
    """
    if current_user.role.value not in ['admin', 'hr']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: HR or Admin role required"
        )
    
    if company_id != current_user.company_id and current_user.role.value != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Company mismatch"
        )
    
    employee = db.query(Employee).filter(
        Employee.id == employee_id,
        Employee.company_id == company_id
    ).first()
    
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found"
        )
    
    employee.employment_status = 'inactive'
    db.commit()
    
    logger.info(f"Deactivated employee {employee_id}")
    
    return {
        "success": True,
        "message": "Employee deactivated successfully"
    }
