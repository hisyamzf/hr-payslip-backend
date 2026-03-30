"""
User Management API Endpoints
Admin operations untuk manage users dan roles
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID

from app.config.database import get_db
from app.repositories.auth_repository import AuthRepository
from app.repositories.company_repository import CompanyRepository
from app.utils.auth import get_current_user, CurrentUser, check_admin_access, require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/users", tags=["users"])


# ==================== Schemas ====================

class CreateUserRequest(BaseModel):
    """Create new user request"""
    phone: str = Field(..., example="+62812345678")
    company_id: str = Field(..., example="uuid-of-company")
    role: str = Field(..., example="employee")


class UserResponse(BaseModel):
    """User response"""
    user_id: str
    phone: str
    created_at: str


class UserWithRoleResponse(UserResponse):
    """User with role response"""
    company_id: Optional[str] = None
    role: Optional[str] = None
    employee_name: Optional[str] = None


class AssignRoleRequest(BaseModel):
    """Assign role request"""
    company_id: str = Field(..., example="uuid-of-company")
    role: str = Field(..., example="admin")


class RoleResponse(BaseModel):
    """Role assignment response"""
    success: bool
    message: str


# ==================== Endpoints ====================

@router.post("", response_model=UserWithRoleResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    request: CreateUserRequest,
    current_user: CurrentUser = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """
    Create new user dan assign to company with role
    Requires: Admin role
    """
    try:
        logger.info(f"👤 Creating user {request.phone} by admin {current_user.user_id}")
        
        auth_repo = AuthRepository(db)
        company_repo = CompanyRepository(db)
        
        # Normalize phone
        from app.services.otp_service import OTPService
        phone = OTPService._normalize_phone(request.phone)
        
        # Check if user already exists
        existing_user = auth_repo.get_user_by_phone(phone)
        if existing_user:
            # Assign to company if not already
            company_id = UUID(request.company_id)
            existing_role = auth_repo.get_user_company_role(existing_user.id, company_id)
            if existing_role:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="User sudah terdaftar di perusahaan ini"
                )
            
            # Assign to company
            auth_repo.assign_user_to_company(existing_user.id, company_id, request.role)
            
            return UserWithRoleResponse(
                user_id=str(existing_user.id),
                phone=existing_user.phone,
                created_at=str(existing_user.created_at),
                company_id=request.company_id,
                role=request.role
            )
        
        # Verify company exists
        company = company_repo.get_company_by_id(UUID(request.company_id))
        if not company:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Perusahaan tidak ditemukan"
            )
        
        # Validate role
        valid_roles = ["admin", "hr", "employee"]
        if request.role not in valid_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Role tidak valid. Pilih: {', '.join(valid_roles)}"
            )
        
        # Create user
        user = auth_repo.create_user(phone)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Gagal membuat user"
            )
        
        # Assign to company
        auth_repo.assign_user_to_company(user.id, UUID(request.company_id), request.role)
        
        logger.info(f"✅ User {user.id} created and assigned to company {request.company_id}")
        
        return UserWithRoleResponse(
            user_id=str(user.id),
            phone=user.phone,
            created_at=str(user.created_at),
            company_id=request.company_id,
            role=request.role
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error creating user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal membuat user"
        )


@router.get("", response_model=List[UserWithRoleResponse])
async def list_users(
    company_id: Optional[str] = None,
    current_user: CurrentUser = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """
    List all users (optionally filtered by company)
    Requires: Admin role
    """
    try:
        logger.info(f"Listing users by admin {current_user.user_id}")
        
        auth_repo = AuthRepository(db)
        
        # Get all users with their company roles
        from app.models.database import User, UserCompanyRole, Employee
        
        if company_id:
            # Filter by company
            users = db.query(User).join(
                UserCompanyRole, User.id == UserCompanyRole.user_id
            ).filter(
                UserCompanyRole.company_id == UUID(company_id),
                UserCompanyRole.is_active == True
            ).all()
            
            result = []
            for user in users:
                role = auth_repo.get_user_company_role(user.id, UUID(company_id))
                # Get employee info if exists
                employee = db.query(Employee).filter(Employee.user_id == user.id).first()
                employee_name = f"{employee.first_name} {employee.last_name}" if employee else None
                
                result.append(UserWithRoleResponse(
                    user_id=str(user.id),
                    phone=user.phone,
                        created_at=str(user.created_at),
                    company_id=company_id,
                    role=role.role if role else None,
                    employee_name=employee_name
                ))
            return result
        else:
            # Get all users (system admin only)
            users = db.query(User).all()
            
            result = []
            for user in users:
                roles = auth_repo.get_user_company_roles(user.id)
                first_role = roles[0] if roles else None
                
                # Get employee info if exists
                employee = db.query(Employee).filter(Employee.user_id == user.id).first()
                employee_name = f"{employee.first_name} {employee.last_name}" if employee else None
                
                result.append(UserWithRoleResponse(
                    user_id=str(user.id),
                    phone=user.phone,
                        created_at=str(user.created_at),
                    company_id=str(first_role.company_id) if first_role else None,
                    role=first_role.role if first_role else None,
                    employee_name=employee_name
                ))
            return result
    
    except Exception as e:
        logger.error(f"❌ Error listing users: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal mengambil daftar user"
        )


@router.get("/{user_id}", response_model=UserWithRoleResponse)
async def get_user(
    user_id: str,
    company_id: Optional[str] = None,
    current_user: CurrentUser = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """
    Get user details
    Requires: Admin role
    """
    try:
        logger.info(f"Getting user {user_id} by admin {current_user.user_id}")
        
        auth_repo = AuthRepository(db)
        
        user = auth_repo.get_user_by_id(UUID(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User tidak ditemukan"
            )
        
        # Get role for specified company or first role
        if company_id:
            role = auth_repo.get_user_company_role(user.id, UUID(company_id))
        else:
            roles = auth_repo.get_user_company_roles(user.id)
            role = roles[0] if roles else None
        
        # Get employee info if exists
        from app.models.database import Employee
        employee = db.query(Employee).filter(Employee.user_id == user.id).first()
        employee_name = f"{employee.first_name} {employee.last_name}" if employee else None
        
        return UserWithRoleResponse(
            user_id=str(user.id),
            phone=user.phone,
            created_at=str(user.created_at),
            company_id=str(role.company_id) if role else None,
            role=role.role if role else None,
            employee_name=employee_name
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal mengambil informasi user"
        )


@router.put("/{user_id}/role", response_model=RoleResponse)
async def assign_role(
    user_id: str,
    request: AssignRoleRequest,
    current_user: CurrentUser = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """
    Assign or update user role in a company
    Requires: Admin role
    """
    try:
        logger.info(f"👤 Assigning role to user {user_id} by admin {current_user.user_id}")
        
        auth_repo = AuthRepository(db)
        
        # Verify user exists
        user = auth_repo.get_user_by_id(UUID(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User tidak ditemukan"
            )
        
        # Validate role
        valid_roles = ["admin", "hr", "employee"]
        if request.role not in valid_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Role tidak valid. Pilih: {', '.join(valid_roles)}"
            )
        
        # Assign to company
        result = auth_repo.assign_user_to_company(
            user.id, 
            UUID(request.company_id), 
            request.role
        )
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Gagal assign role"
            )
        
        logger.info(f"✅ Role {request.role} assigned to user {user_id}")
        
        return RoleResponse(
            success=True,
            message=f"Role {request.role} berhasil di-assign"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error assigning role: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal assign role"
        )


@router.delete("/{user_id}")
async def remove_user_from_company(
    user_id: str,
    company_id: str,
    current_user: CurrentUser = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """
    Remove user from company (soft delete)
    Requires: Admin role
    """
    try:
        logger.info(f"👤 Removing user {user_id} from company {company_id}")
        
        auth_repo = AuthRepository(db)
        
        # Verify user exists
        user = auth_repo.get_user_by_id(UUID(user_id))
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User tidak ditemukan"
            )
        
        # Soft delete - set is_active to False
        user_company_role = auth_repo.get_user_company_role(UUID(user_id), UUID(company_id))
        if not user_company_role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User tidak memiliki akses ke perusahaan ini"
            )
        
        user_company_role.is_active = False
        db.commit()
        
        logger.info(f"✅ User {user_id} removed from company {company_id}")
        
        return {
            "success": True,
            "message": "User berhasil dihapus dari perusahaan"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error removing user: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal menghapus user"
        )
