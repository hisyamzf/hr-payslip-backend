from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models.database import Payslip
from app.repositories.base_repository import BaseRepository
from uuid import UUID
from datetime import date
from typing import Optional, List

class PayslipRepository(BaseRepository):
    def __init__(self, session: Session):
        super().__init__(session, Payslip)
    
    def get_by_employee_period(self, employee_id: UUID, period_start: date) -> Optional[Payslip]:
        """Get payslip for specific employee and period"""
        return self.session.query(Payslip).filter(
            and_(
                Payslip.employee_id == employee_id,
                Payslip.period_start == period_start
            )
        ).first()
    
    def payslip_exists(self, company_id: UUID, employee_id: UUID, period_start: date) -> bool:
        """Check if payslip already exists (duplicate check)"""
        return self.session.query(Payslip).filter(
            and_(
                Payslip.company_id == company_id,
                Payslip.employee_id == employee_id,
                Payslip.period_start == period_start
            )
        ).first() is not None
    
    def insert_batch(self, payslips: List[dict]) -> List[Payslip]:
        """Batch insert payslips"""
        db_payslips = []
        for p in payslips:
            db_p = self.create(p)
            db_payslips.append(db_p)
        return db_payslips