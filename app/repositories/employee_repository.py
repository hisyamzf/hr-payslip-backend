from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models.database import Employee
from app.repositories.base_repository import BaseRepository
from uuid import UUID
from typing import Optional

class EmployeeRepository(BaseRepository):
    def __init__(self, session: Session):
        super().__init__(session, Employee)
    
    def get_by_employee_number_and_company(self, employee_number: str, company_id: UUID) -> Optional[Employee]:
        """Get employee by employee_number and company"""
        return self.session.query(Employee).filter(
            and_(
                Employee.employee_number == employee_number,
                Employee.company_id == company_id
            )
        ).first()
    
    def employee_exists(self, employee_number: str, company_id: UUID) -> bool:
        """Check if employee exists"""
        return self.get_by_employee_number_and_company(employee_number, company_id) is not None