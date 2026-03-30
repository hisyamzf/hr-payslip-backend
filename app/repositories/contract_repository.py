from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from app.models.database import Contract
from uuid import UUID
from typing import Optional, List
from datetime import datetime


class ContractRepository:
    def __init__(self, session: Session):
        self.session = session
    
    def create(self, data: dict) -> Contract:
        """Create a new contract"""
        contract = Contract(**data)
        self.session.add(contract)
        self.session.flush()
        return contract
    
    def get_by_id(self, contract_id: UUID) -> Optional[Contract]:
        """Get contract by ID"""
        return self.session.query(Contract).filter(
            Contract.id == contract_id
        ).first()
    
    def get_by_employee_id(self, employee_id: UUID) -> Optional[Contract]:
        """Get contract by employee ID"""
        return self.session.query(Contract).filter(
            Contract.employee_id == employee_id
        ).first()
    
    def get_by_company_id(
        self,
        company_id: UUID,
        limit: int = 50,
        offset: int = 0,
        employee_id: Optional[UUID] = None,
        contract_type: Optional[str] = None
    ) -> List[Contract]:
        """Get contracts by company with optional filters"""
        query = self.session.query(Contract).filter(
            Contract.company_id == company_id
        )
        
        if employee_id:
            query = query.filter(Contract.employee_id == employee_id)
        
        if contract_type:
            query = query.filter(Contract.contract_type == contract_type)
        
        return query.order_by(
            Contract.created_at.desc()
        ).offset(offset).limit(limit).all()
    
    def count_by_company(self, company_id: UUID) -> int:
        """Count contracts in a company"""
        return self.session.query(Contract).filter(
            Contract.company_id == company_id
        ).count()
    
    def update(self, contract_id: UUID, data: dict) -> Optional[Contract]:
        """Update contract"""
        contract = self.get_by_id(contract_id)
        if contract:
            for key, value in data.items():
                if hasattr(contract, key) and key != 'id':
                    setattr(contract, key, value)
            contract.updated_at = datetime.utcnow()
            self.session.flush()
        return contract
    
    def delete(self, contract_id: UUID) -> bool:
        """Delete contract"""
        contract = self.get_by_id(contract_id)
        if contract:
            self.session.delete(contract)
            return True
        return False
    
    def employee_has_contract(self, employee_id: UUID) -> bool:
        """Check if employee already has a contract"""
        return self.get_by_employee_id(employee_id) is not None
