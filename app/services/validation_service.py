from sqlalchemy.orm import Session
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.payslip_repository import PayslipRepository
from uuid import UUID
from datetime import date

class ValidationService:
    def __init__(self, session: Session):
        self.session = session
        self.employee_repo = EmployeeRepository(session)
        self.payslip_repo = PayslipRepository(session)
    
    def validate_employee_exists(self, employee_number: str, company_id: UUID) -> tuple[bool, str]:
        """Check if employee exists in company"""
        exists = self.employee_repo.employee_exists(employee_number, company_id)
        if not exists:
            return False, f"Employee {employee_number} not found in company"
        return True, None
    
    def validate_duplicate_payslip(self, company_id: UUID, employee_number: str, period_start: date) -> tuple[bool, str]:
        """Check if payslip already exists for this period"""
        employee = self.employee_repo.get_by_employee_number_and_company(employee_number, company_id)
        if not employee:
            return True, None  # Employee doesn't exist, so no duplicate
        
        exists = self.payslip_repo.payslip_exists(company_id, employee.id, period_start)
        if exists:
            return False, f"Payslip already exists for {employee_number} in period {period_start}"
        return True, None
    
    def validate_row(self, row_data: dict, company_id: UUID, period_start: date) -> tuple[bool, str]:
        """Validate entire row"""
        employee_number = row_data.get('employee_number')
        
        # Check employee exists
        is_valid, error = self.validate_employee_exists(employee_number, company_id)
        if not is_valid:
            return False, error
        
        # Check duplicate
        is_valid, error = self.validate_duplicate_payslip(company_id, employee_number, period_start)
        if not is_valid:
            return False, error
        
        return True, None