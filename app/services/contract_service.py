from sqlalchemy.orm import Session
from app.models.database import Contract, Employee
from app.repositories.contract_repository import ContractRepository
from app.repositories.employee_repository import EmployeeRepository
from app.repositories.company_repository import CompanyRepository
from app.utils.supabase_client import SupabaseStorageClient
from uuid import UUID
from datetime import datetime
import logging
from decimal import Decimal
import os

logger = logging.getLogger(__name__)


class ContractService:
    CONTRACT_BUCKET = "contracts"
    
    def __init__(self, session: Session):
        self.session = session
        self.contract_repo = ContractRepository(session)
        self.employee_repo = EmployeeRepository(session)
        self.company_repo = CompanyRepository(session)
        self.storage_client = SupabaseStorageClient() if os.getenv('SUPABASE_URL') else None
    
    def create_contract(
        self,
        company_id: UUID,
        employee_id: UUID,
        contract_type: str,
        job_title: str,
        department: str,
        base_salary: float,
        start_date,
        end_date=None,
        file_content: bytes = None,
        file_name: str = None,
        created_by: str = None
    ) -> dict:
        """
        Create a new contract with optional PDF upload
        
        Args:
            company_id: Company UUID
            employee_id: Employee UUID
            contract_type: Type of contract (PKWT, PKWTT, etc.)
            job_title: Job title/position
            department: Department
            base_salary: Base salary amount
            start_date: Contract start date
            end_date: Contract end date (optional)
            file_content: PDF file content as bytes (optional)
            file_name: Original file name (optional)
            created_by: User ID who created this
            
        Returns:
            Contract data dict
        """
        employee = self.employee_repo.get_by_id(employee_id)
        if not employee:
            raise ValueError(f"Employee {employee_id} not found")
        
        if employee.company_id != company_id:
            raise ValueError("Employee does not belong to this company")
        
        if self.contract_repo.employee_has_contract(employee_id):
            raise ValueError("Employee already has a contract. Use update to replace.")
        
        file_url = None
        if file_content and self.storage_client:
            file_url = self._upload_contract_file(
                company_id=company_id,
                employee_id=employee_id,
                file_content=file_content,
                file_name=file_name or f"{employee.employee_number}_contract.pdf"
            )
        
        contract_data = {
            'company_id': company_id,
            'employee_id': employee_id,
            'contract_type': contract_type,
            'job_title': job_title,
            'department': department,
            'base_salary': Decimal(str(base_salary)),
            'start_date': start_date,
            'end_date': end_date,
            'file_url': file_url,
        }
        
        contract = self.contract_repo.create(contract_data)
        self.session.commit()
        
        logger.info(f"Created contract {contract.id} for employee {employee_id}")
        
        return self._format_contract_response(contract, employee)
    
    def update_contract(
        self,
        contract_id: UUID,
        company_id: UUID,
        contract_type: str = None,
        job_title: str = None,
        department: str = None,
        base_salary: float = None,
        start_date=None,
        end_date=None,
        file_content: bytes = None,
        file_name: str = None
    ) -> dict:
        """
        Update an existing contract
        
        Args:
            contract_id: Contract UUID
            company_id: Company UUID (for validation)
            Other fields optional - only updates provided values
            
        Returns:
            Updated contract data dict
        """
        contract = self.contract_repo.get_by_id(contract_id)
        if not contract:
            raise ValueError(f"Contract {contract_id} not found")
        
        if contract.company_id != company_id:
            raise ValueError("Contract does not belong to this company")
        
        update_data = {}
        
        if contract_type:
            update_data['contract_type'] = contract_type
        if job_title:
            update_data['job_title'] = job_title
        if department:
            update_data['department'] = department
        if base_salary is not None:
            update_data['base_salary'] = Decimal(str(base_salary))
        if start_date:
            update_data['start_date'] = start_date
        if end_date is not None:
            update_data['end_date'] = end_date
        
        if file_content and self.storage_client:
            file_url = self._upload_contract_file(
                company_id=company_id,
                employee_id=contract.employee_id,
                file_content=file_content,
                file_name=file_name or f"{contract_id}_contract.pdf"
            )
            update_data['file_url'] = file_url
        
        if update_data:
            contract = self.contract_repo.update(contract_id, update_data)
            self.session.commit()
        
        employee = self.employee_repo.get_by_id(contract.employee_id)
        
        logger.info(f"Updated contract {contract_id}")
        
        return self._format_contract_response(contract, employee)
    
    def get_contract(self, contract_id: UUID) -> dict:
        """Get contract by ID"""
        contract = self.contract_repo.get_by_id(contract_id)
        if not contract:
            raise ValueError(f"Contract {contract_id} not found")
        
        employee = self.employee_repo.get_by_id(contract.employee_id)
        return self._format_contract_response(contract, employee)
    
    def get_employee_contract(self, employee_id: UUID) -> dict:
        """Get contract for an employee"""
        contract = self.contract_repo.get_by_employee_id(employee_id)
        if not contract:
            raise ValueError(f"No contract found for employee {employee_id}")
        
        employee = self.employee_repo.get_by_id(employee_id)
        return self._format_contract_response(contract, employee)
    
    def list_company_contracts(
        self,
        company_id: UUID,
        limit: int = 50,
        offset: int = 0,
        employee_id: UUID = None,
        contract_type: str = None
    ) -> dict:
        """List contracts in a company"""
        contracts = self.contract_repo.get_by_company_id(
            company_id=company_id,
            limit=limit,
            offset=offset,
            employee_id=employee_id,
            contract_type=contract_type
        )
        
        total = self.contract_repo.count_by_company(company_id)
        
        result = []
        for contract in contracts:
            employee = self.employee_repo.get_by_id(contract.employee_id)
            result.append(self._format_contract_response(contract, employee))
        
        return {
            'contracts': result,
            'total': total,
            'limit': limit,
            'offset': offset
        }
    
    def delete_contract(self, contract_id: UUID, company_id: UUID) -> bool:
        """Delete a contract"""
        contract = self.contract_repo.get_by_id(contract_id)
        if not contract:
            raise ValueError(f"Contract {contract_id} not found")
        
        if contract.company_id != company_id:
            raise ValueError("Contract does not belong to this company")
        
        if contract.file_url and self.storage_client:
            try:
                self._delete_contract_file(contract.file_url)
            except Exception as e:
                logger.warning(f"Could not delete file from storage: {e}")
        
        return self.contract_repo.delete(contract_id)
    
    def get_contract_download_url(self, contract_id: UUID) -> str:
        """Get signed/download URL for contract PDF"""
        contract = self.contract_repo.get_by_id(contract_id)
        if not contract:
            raise ValueError(f"Contract {contract_id} not found")
        
        if not contract.file_url:
            raise ValueError("No file attached to this contract")
        
        if self.storage_client:
            return self.storage_client.get_public_url(contract.file_url)
        
        return contract.file_url
    
    def _upload_contract_file(
        self,
        company_id: UUID,
        employee_id: UUID,
        file_content: bytes,
        file_name: str
    ) -> str:
        """Upload contract PDF to Supabase Storage"""
        if not self.storage_client:
            raise ValueError("Storage not configured")
        
        timestamp = datetime.utcnow().strftime('%Y%m%d')
        storage_path = f"contracts/{company_id}/{employee_id}/{timestamp}_{file_name}"
        
        result = self.storage_client.upload_file(
            file_path=storage_path,
            file_content=file_content,
            content_type='application/pdf',
            public=True
        )
        
        logger.info(f"Uploaded contract file to {storage_path}")
        
        return storage_path
    
    def _delete_contract_file(self, storage_path: str):
        """Delete contract file from Supabase Storage"""
        if not self.storage_client:
            return
        
        try:
            self.storage_client.delete_file(storage_path)
            logger.info(f"Deleted contract file: {storage_path}")
        except Exception as e:
            logger.warning(f"Failed to delete file {storage_path}: {e}")
    
    def _format_contract_response(self, contract: Contract, employee: Employee = None) -> dict:
        """Format contract for API response"""
        if employee is None:
            employee = self.employee_repo.get_by_id(contract.employee_id)
        
        return {
            'id': str(contract.id),
            'company_id': str(contract.company_id),
            'employee_id': str(contract.employee_id),
            'employee_name': f"{employee.first_name} {employee.last_name}" if employee else None,
            'employee_number': employee.employee_number if employee else None,
            'contract_type': contract.contract_type,
            'job_title': contract.job_title,
            'department': contract.department,
            'base_salary': float(contract.base_salary),
            'start_date': contract.start_date.isoformat() if contract.start_date else None,
            'end_date': contract.end_date.isoformat() if contract.end_date else None,
            'file_url': contract.file_url,
            'has_file': contract.file_url is not None,
            'created_at': contract.created_at.isoformat() if contract.created_at else None,
            'updated_at': contract.updated_at.isoformat() if contract.updated_at else None,
        }
