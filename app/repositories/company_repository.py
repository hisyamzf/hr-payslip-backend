from sqlalchemy.orm import Session
from sqlalchemy import and_
from app.models.database import Company
from app.repositories.base_repository import BaseRepository
from uuid import UUID
from typing import List

class CompanyRepository(BaseRepository):
    def __init__(self, session: Session):
        super().__init__(session, Company)
    
    def get_by_id(self, company_id: UUID) -> Company:
        """Get company by ID"""
        return self.session.query(Company).filter(Company.id == company_id).first()
    
    def company_exists(self, company_id: UUID) -> bool:
        """Check if company exists"""
        return self.session.query(Company).filter(Company.id == company_id).first() is not None
    
    def get_all(self) -> List[Company]:
        """Get all companies"""
        return self.session.query(Company).filter(Company.status == 'active').all()
    
    def get_all_companies(self) -> List[Company]:
        """Get all companies including inactive"""
        return self.session.query(Company).all()
    
    def get_by_code(self, code: str) -> Company:
        """Get company by code"""
        return self.session.query(Company).filter(Company.code == code).first()