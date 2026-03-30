"""
Company Management API Endpoints
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID

from app.config.database import get_db
from app.repositories.company_repository import CompanyRepository
from app.repositories.auth_repository import AuthRepository
from app.utils.auth import get_current_user, CurrentUser, require_admin
from app.models.database import Company

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/companies", tags=["companies"])


# ==================== Schemas ====================

class CreateCompanyRequest(BaseModel):
    """Create new company request"""
    name: str = Field(..., example="PT Contoh Indonesia")
    code: str = Field(..., example="CONTOH")
    country: str = Field(default="Indonesia")
    currency: str = Field(default="IDR")


class CompanyResponse(BaseModel):
    """Company response"""
    id: str
    name: str
    code: str
    country: str
    currency: str
    status: str
    created_at: str


class UpdateCompanyRequest(BaseModel):
    """Update company request"""
    name: Optional[str] = None
    country: Optional[str] = None
    currency: Optional[str] = None
    status: Optional[str] = None


# ==================== Endpoints ====================

@router.get("", response_model=List[CompanyResponse])
async def list_companies(
    current_user: CurrentUser = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """
    List all companies
    Requires: Admin role
    """
    try:
        logger.info(f"Listing companies by admin {current_user.user_id}")
        
        company_repo = CompanyRepository(db)
        companies = company_repo.get_all_companies()
        
        return [
            CompanyResponse(
                id=str(c.id),
                name=c.name,
                code=c.code,
                country=c.country,
                currency=c.currency,
                status=c.status,
                created_at=str(c.created_at)
            )
            for c in companies
        ]
    
    except Exception as e:
        logger.error(f"Error listing companies: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal mengambil daftar perusahaan"
        )


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
async def create_company(
    request: CreateCompanyRequest,
    current_user: CurrentUser = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """
    Create new company
    Requires: Admin role
    """
    try:
        logger.info(f"Creating company {request.name} by admin {current_user.user_id}")
        
        company_repo = CompanyRepository(db)
        
        # Check if code already exists
        existing = company_repo.get_by_code(request.code)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Kode perusahaan sudah digunakan"
            )
        
        # Create company
        company = Company(
            name=request.name,
            code=request.code,
            country=request.country,
            currency=request.currency,
            status="active"
        )
        db.add(company)
        db.commit()
        db.refresh(company)
        
        logger.info(f"Company {company.id} created successfully")
        
        return CompanyResponse(
            id=str(company.id),
            name=company.name,
            code=company.code,
            country=company.country,
            currency=company.currency,
            status=company.status,
            created_at=str(company.created_at)
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating company: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal membuat perusahaan"
        )


@router.get("/{company_id}", response_model=CompanyResponse)
async def get_company(
    company_id: str,
    current_user: CurrentUser = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """
    Get company details
    Requires: Admin role
    """
    try:
        logger.info(f"Getting company {company_id} by admin {current_user.user_id}")
        
        company_repo = CompanyRepository(db)
        company = company_repo.get_by_id(UUID(company_id))
        
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Perusahaan tidak ditemukan"
            )
        
        return CompanyResponse(
            id=str(company.id),
            name=company.name,
            code=company.code,
            country=company.country,
            currency=company.currency,
            status=company.status,
            created_at=str(company.created_at)
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting company: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal mengambil informasi perusahaan"
        )


@router.put("/{company_id}", response_model=CompanyResponse)
async def update_company(
    company_id: str,
    request: UpdateCompanyRequest,
    current_user: CurrentUser = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """
    Update company
    Requires: Admin role
    """
    try:
        logger.info(f"Updating company {company_id} by admin {current_user.user_id}")
        
        company_repo = CompanyRepository(db)
        company = company_repo.get_by_id(UUID(company_id))
        
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Perusahaan tidak ditemukan"
            )
        
        # Update fields
        if request.name is not None:
            company.name = request.name
        if request.country is not None:
            company.country = request.country
        if request.currency is not None:
            company.currency = request.currency
        if request.status is not None:
            company.status = request.status
        
        db.commit()
        db.refresh(company)
        
        logger.info(f"Company {company_id} updated successfully")
        
        return CompanyResponse(
            id=str(company.id),
            name=company.name,
            code=company.code,
            country=company.country,
            currency=company.currency,
            status=company.status,
            created_at=str(company.created_at)
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating company: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal mengupdate perusahaan"
        )


@router.delete("/{company_id}")
async def delete_company(
    company_id: str,
    current_user: CurrentUser = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """
    Delete (deactivate) company
    Requires: Admin role
    """
    try:
        logger.info(f"Deleting company {company_id} by admin {current_user.user_id}")
        
        company_repo = CompanyRepository(db)
        company = company_repo.get_by_id(UUID(company_id))
        
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Perusahaan tidak ditemukan"
            )
        
        # Soft delete - just deactivate
        company.status = "inactive"
        db.commit()
        
        logger.info(f"Company {company_id} deactivated successfully")
        
        return {
            "success": True,
            "message": "Perusahaan berhasil dihapus"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting company: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal menghapus perusahaan"
        )


@router.get("/{company_id}/users", response_model=List[dict])
async def get_company_users(
    company_id: str,
    current_user: CurrentUser = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """
    Get all users in a company
    Requires: Admin role
    """
    try:
        logger.info(f"Getting users for company {company_id}")
        
        from app.models.database import User, UserCompanyRole
        
        # Get users with roles in this company
        user_roles = db.query(UserCompanyRole).filter(
            UserCompanyRole.company_id == UUID(company_id),
            UserCompanyRole.is_active == True
        ).all()
        
        result = []
        for ur in user_roles:
            user = db.query(User).filter(User.id == ur.user_id).first()
            if user:
                result.append({
                    "user_id": str(user.id),
                    "phone": user.phone,
                    "role": ur.role,
                    "is_active": ur.is_active
                })
        
        return result
    
    except Exception as e:
        logger.error(f"Error getting company users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal mengambil daftar user"
        )
