"""
Role-Based Access Control (RBAC) utilities
Handle role checking and authorization logic
"""

from enum import Enum
from typing import Optional
from sqlalchemy.orm import Session
from uuid import UUID
from fastapi import HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.models.database import User, UserCompanyRole, RefreshToken
from app.config.database import get_db
import os
import jwt
from datetime import datetime

import logging

logger = logging.getLogger(__name__)


class UserRole(str, Enum):
    """User roles in the system"""
    ADMIN = "admin"
    HR = "hr"
    EMPLOYEE = "employee"


def get_user_role_enum(role_value: str) -> Optional[UserRole]:
    """Convert role string value to UserRole enum"""
    for role in UserRole:
        if role.value == role_value:
            return role
    return None


class CurrentUser:
    """Dependency to get current user from JWT/token"""
    def __init__(self, user_id: UUID, company_id: UUID, role: UserRole):
        self.user_id = user_id
        self.company_id = company_id
        self.role = role


security = HTTPBearer()


def get_user_role_in_company(
    db: Session,
    user_id: UUID,
    company_id: UUID
) -> Optional[str]:
    """
    Fetch user's role in a specific company
    
    Returns:
        role string ('admin', 'hr', 'employee') or None
    """
    try:
        user_role = db.query(UserCompanyRole).filter(
            UserCompanyRole.user_id == user_id,
            UserCompanyRole.company_id == company_id,
            UserCompanyRole.is_active == True
        ).first()
        
        if user_role:
            return user_role.role
        
        return None
    
    except Exception as e:
        logger.error(f"Error fetching user role: {str(e)}")
        return None


def check_access_payslip(
    current_user: CurrentUser,
    db: Session,
    payslip_company_id: UUID,
    payslip_employee_id: UUID,
    employee_user_id: UUID = None
):
    """
    Check if current user can access a payslip
    
    Access rules:
    - 'admin': Can access ALL payslips
    - 'hr': Can access payslips in their company
    - 'employee': Can only access their own payslip
    
    Args:
        current_user: CurrentUser object with user_id, company_id, role
        db: Database session
        payslip_company_id: Company ID of the payslip
        payslip_employee_id: Employee ID of the payslip owner
        employee_user_id: User ID of the employee (for 'employee' role check)
    
    Raises:
        HTTPException: If user doesn't have access
    """
    
    if current_user.role == UserRole.ADMIN:
        return True
    
    if payslip_company_id != current_user.company_id:
        logger.warning(
            f"User {current_user.user_id} trying to access payslip "
            f"from different company {payslip_company_id}"
        )
        raise HTTPException(
            status_code=403,
            detail="Access denied: Payslip belongs to different company"
        )
    
    if current_user.role == UserRole.HR:
        return True
    
    if current_user.role == UserRole.EMPLOYEE:
        if employee_user_id and current_user.user_id != employee_user_id:
            logger.warning(
                f"User {current_user.user_id} trying to access "
                f"another employee's payslip {payslip_employee_id}"
            )
            raise HTTPException(
                status_code=403,
                detail="Access denied: You can only access your own payslip"
            )
        return True
    
    raise HTTPException(status_code=403, detail="Access denied")


def check_list_access(
    current_user: CurrentUser,
    db: Session,
    target_company_id: UUID,
    target_employee_id: UUID = None
):
    """
    Check if current user can list payslips
    
    Access rules:
    - 'admin': List all payslips
    - 'hr': List all payslips in company
    - 'employee': Only query returns own payslip
    
    Args:
        current_user: CurrentUser object
        db: Database session
        target_company_id: Company being queried
        target_employee_id: Employee being queried (for filtering client access)
    
    Raises:
        HTTPException: If access denied
    """
    
    if current_user.role == UserRole.ADMIN:
        return True
    
    if target_company_id != current_user.company_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: Can only access payslips from your company"
        )
    
    if current_user.role == UserRole.HR:
        return True
    
    if current_user.role == UserRole.EMPLOYEE:
        return True
    
    raise HTTPException(status_code=403, detail="Access denied")


def check_admin_access(current_user: CurrentUser):
    """Check if user has admin access"""
    if current_user.role not in [UserRole.ADMIN, UserRole.HR]:
        raise HTTPException(
            status_code=403,
            detail="Access denied: Admin privileges required"
        )


def require_admin():
    """Dependency factory to require admin or hr role"""
    def dependency(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in [UserRole.ADMIN, UserRole.HR]:
            raise HTTPException(
                status_code=403,
                detail="Access denied: Admin privileges required"
            )
        return current_user
    return dependency


def verify_jwt_token(token: str) -> dict:
    """
    Verify and decode JWT token
    
    Args:
        token: JWT access token
        
    Returns:
        Decoded token payload
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    jwt_secret = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
    jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")
    
    try:
        payload = jwt.decode(
            token,
            jwt_secret,
            algorithms=[jwt_algorithm]
        )
        
        if payload.get("exp") and datetime.utcnow().timestamp() > payload["exp"]:
            raise HTTPException(
                status_code=401,
                detail="Token has expired"
            )
        
        return payload
    
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid JWT token: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail="Invalid token"
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> CurrentUser:
    """
    Extract current user from JWT token
    
    Validates:
    1. JWT token from Authorization header
    2. Extract user_id and company_id from token claims
    3. Verify user's role for the company
    
    Returns:
        CurrentUser with verified data
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    token = credentials.credentials
    
    payload = verify_jwt_token(token)
    
    user_id = payload.get("sub")
    company_id = payload.get("company_id")
    
    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Invalid token: missing user id"
        )
    
    try:
        user_uuid = UUID(user_id)
    except ValueError:
        raise HTTPException(
            status_code=401,
            detail="Invalid token: invalid user id format"
        )
    
    if company_id:
        try:
            company_uuid = UUID(company_id)
        except ValueError:
            raise HTTPException(
                status_code=401,
                detail="Invalid token: invalid company id format"
            )
        
        role = get_user_role_in_company(db, user_uuid, company_uuid)
        
        if not role:
            raise HTTPException(
                status_code=403,
                detail="Access denied: User not associated with company"
            )
        
        role_enum = get_user_role_enum(role)
        if not role_enum:
            raise HTTPException(
                status_code=403,
                detail=f"Invalid role: {role}"
            )
        
        return CurrentUser(
            user_id=user_uuid,
            company_id=company_uuid,
            role=role_enum
        )
    
    raise HTTPException(
        status_code=401,
        detail="Invalid token: missing company context"
    )


def create_access_token(user_id: str, company_id: str, role: str) -> str:
    """
    Create JWT access token
    
    Args:
        user_id: User UUID
        company_id: Company UUID
        role: User role
        
    Returns:
        JWT token string
    """
    from datetime import timedelta
    
    jwt_secret = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
    jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")
    access_token_expire_minutes = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
    
    expire = datetime.utcnow() + timedelta(minutes=access_token_expire_minutes)
    
    payload = {
        "sub": str(user_id),
        "company_id": str(company_id),
        "role": role,
        "exp": expire.timestamp(),
        "iat": datetime.utcnow().timestamp()
    }
    
    return jwt.encode(payload, jwt_secret, algorithm=jwt_algorithm)


def create_refresh_token(
    db: Session,
    user_id: str,
    device_info: str = None,
    ip_address: str = None
) -> str:
    """
    Create JWT refresh token and save to database
    
    Args:
        db: Database session
        user_id: User UUID
        device_info: Device/browser info
        ip_address: Client IP address
        
    Returns:
        JWT refresh token string
    """
    from datetime import timedelta
    import hashlib
    
    jwt_secret = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
    jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")
    refresh_token_expire_days = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
    
    expire = datetime.utcnow() + timedelta(days=refresh_token_expire_days)
    
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "exp": expire.timestamp(),
        "iat": datetime.utcnow().timestamp()
    }
    
    token = jwt.encode(payload, jwt_secret, algorithm=jwt_algorithm)
    
    from app.models.database import RefreshToken
    
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    
    refresh_token = RefreshToken(
        user_id=UUID(user_id),
        token_hash=token_hash,
        expires_at=expire,
        is_revoked=False,
        device_info=device_info,
        ip_address=ip_address
    )
    
    db.add(refresh_token)
    db.commit()
    
    logger.info(f"Created refresh token for user {user_id}")
    
    return token


def verify_refresh_token(db: Session, token: str) -> dict:
    """
    Verify refresh token and check if not revoked
    
    Args:
        db: Database session
        token: JWT refresh token
        
    Returns:
        Decoded token payload
        
    Raises:
        HTTPException: If token invalid or revoked
    """
    import hashlib
    
    jwt_secret = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
    jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")
    
    try:
        payload = jwt.decode(
            token,
            jwt_secret,
            algorithms=[jwt_algorithm]
        )
        
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=401,
                detail="Invalid token type"
            )
        
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        
        stored_token = db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash
        ).first()
        
        if not stored_token:
            raise HTTPException(
                status_code=401,
                detail="Token not found"
            )
        
        if stored_token.is_revoked:
            raise HTTPException(
                status_code=401,
                detail="Token has been revoked"
            )
        
        if stored_token.expires_at < datetime.utcnow():
            raise HTTPException(
                status_code=401,
                detail="Token has expired"
            )
        
        return payload
    
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Refresh token has expired"
        )
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid refresh token: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail="Invalid refresh token"
        )


def revoke_refresh_token(db: Session, token: str) -> bool:
    """
    Revoke a refresh token (logout)
    
    Args:
        db: Database session
        token: JWT refresh token
        
    Returns:
        True if revoked successfully
    """
    import hashlib
    
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    
    stored_token = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash
    ).first()
    
    if stored_token:
        stored_token.is_revoked = True
        stored_token.revoked_at = datetime.utcnow()
        db.commit()
        logger.info(f"Revoked refresh token for user {stored_token.user_id}")
        return True
    
    return False


def revoke_all_user_tokens(db: Session, user_id: str) -> int:
    """
    Revoke all refresh tokens for a user (logout from all devices)
    
    Args:
        db: Database session
        user_id: User UUID
        
    Returns:
        Number of tokens revoked
    """
    count = db.query(RefreshToken).filter(
        RefreshToken.user_id == UUID(user_id),
        RefreshToken.is_revoked == False
    ).update({
        'is_revoked': True,
        'revoked_at': datetime.utcnow()
    })
    
    db.commit()
    logger.info(f"Revoked {count} refresh tokens for user {user_id}")
    
    return count
