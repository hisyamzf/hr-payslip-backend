"""
Authentication API Endpoints
Phone + OTP Login Flow
"""

import logging
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Optional

from app.config.database import get_db
from app.services.otp_service import OTPService
from app.services.token_service import TokenService
from app.repositories.auth_repository import AuthRepository
from app.utils.auth import get_current_user, CurrentUser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


# ==================== Schemas ====================

class RequestOTPRequest(BaseModel):
    """Request OTP endpoint input"""
    phone: str = Field(..., example="+62812345678")


class RequestOTPResponse(BaseModel):
    """Request OTP endpoint response"""
    success: bool
    message: str
    request_id: Optional[str] = None


class VerifyOTPRequest(BaseModel):
    """Verify OTP endpoint input"""
    phone: str = Field(..., example="+62812345678")
    otp_code: str = Field(..., example="123456")


class TokenResponse(BaseModel):
    """Token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 3600  # seconds


class VerifyOTPResponse(BaseModel):
    """Verify OTP endpoint response"""
    success: bool
    message: str
    tokens: Optional[TokenResponse] = None


class RefreshTokenRequest(BaseModel):
    """Refresh token endpoint input"""
    refresh_token: str


class LogoutRequest(BaseModel):
    """Logout endpoint input"""
    refresh_token: str


class CurrentUserResponse(BaseModel):
    """Current user info response"""
    user_id: str
    phone: str
    company_id: str
    role: str
    companies: list = []


# ==================== Endpoints ====================

@router.post("/request-otp", response_model=RequestOTPResponse)
async def request_otp(
    request: RequestOTPRequest,
    db: Session = Depends(get_db)
):
    """
    Request OTP untuk login
    
    Flow:
    1. User input nomor telepon
    2. System generate OTP
    3. Send OTP via SMS
    
    Response:
    - success: bool
    - message: informasi untuk user
    - request_id: ID untuk tracking (optional)
    """
    try:
        logger.info(f"📱 OTP request for: {request.phone}")
        
        otp_service = OTPService()
        success, message, request_id = await otp_service.request_otp(db, request.phone)
        
        return RequestOTPResponse(
            success=success,
            message=message,
            request_id=request_id
        )
    
    except Exception as e:
        logger.error(f"❌ Error requesting OTP: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal memproses request OTP"
        )


@router.post("/verify-otp", response_model=VerifyOTPResponse)
async def verify_otp(
    request: VerifyOTPRequest,
    req: Request,
    db: Session = Depends(get_db)
):
    """
    Verify OTP dan return JWT tokens
    
    Flow:
    1. User input nomor telepon + OTP
    2. System verify OTP
    3. Create access token + refresh token
    4. Return tokens to client
    
    Response:
    - success: bool
    - tokens: {access_token, refresh_token, expires_in}
    """
    try:
        logger.info(f"🔐 OTP verification for: {request.phone}")
        
        otp_service = OTPService()
        logger.info(f"Calling verify_otp with phone={request.phone}, otp={request.otp_code}")
        success, message, user_id = await otp_service.verify_otp(
            db, 
            request.phone, 
            request.otp_code
        )
        logger.info(f"verify_otp returned: success={success}, message={message}, user_id={user_id}")
        
        if not success or not user_id:
            logger.warning(f"⚠️ OTP verification failed: {message}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=message
            )
        
        # Get user's company role (first role untuk now)
        auth_repo = AuthRepository(db)
        
        # Ensure user_id is UUID
        user_id_uuid = user_id if isinstance(user_id, UUID) else UUID(str(user_id))
        
        user_roles = auth_repo.get_user_company_roles(user_id_uuid)
        
        if not user_roles:
            logger.warning(f"⚠️ User has no company roles: {user_id_uuid}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User tidak memiliki akses ke perusahaan"
            )
        
        # Use first role
        first_role = user_roles[0]
        company_id = first_role.company_id
        auth_role = first_role.role  # Use business role directly: admin, hr, employee
        
        # Create tokens
        token_service = TokenService()
        access_token = token_service.create_access_token(
            user_id=user_id,
            company_id=company_id,
            role=auth_role
        )
        
        # Get device info dari request
        user_agent = req.headers.get("user-agent", "Unknown")
        client_host = req.client.host if req.client else "Unknown"
        
        logger.info("Creating refresh token...")
        refresh_token = token_service.create_refresh_token(
            db=db,
            user_id=user_id,
            device_info=user_agent,
            ip_address=client_host
        )
        
        logger.info(f"✅ OTP verified and tokens created for user {user_id}")
        
        return VerifyOTPResponse(
            success=True,
            message="Login berhasil",
            tokens=TokenResponse(
                access_token=access_token,
                refresh_token=refresh_token,
                token_type="bearer"
            )
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error verifying OTP: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal memverifikasi OTP"
        )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Refresh access token menggunakan refresh token
    
    Response:
    - access_token: token baru
    - refresh_token: token baru (optional, bisa same atau baru)
    """
    try:
        logger.info("🔄 Refreshing access token")
        
        token_service = TokenService()
        user_id = token_service.verify_refresh_token(db, request.refresh_token)
        
        if not user_id:
            logger.warning("⚠️ Invalid refresh token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token tidak valid atau sudah kadaluarsa"
            )
        
        # Get user's current company role
        auth_repo = AuthRepository(db)
        user_roles = auth_repo.get_user_company_roles(user_id)
        
        if not user_roles:
            logger.warning(f"⚠️ User has no company roles: {user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User tidak memiliki akses"
            )
        
        first_role = user_roles[0]
        
        # Create new access token
        new_access_token = token_service.create_access_token(
            user_id=user_id,
            company_id=first_role.company_id,
            role=first_role.role
        )
        
        logger.info(f"✅ Token refreshed for user {user_id}")
        
        return TokenResponse(
            access_token=new_access_token,
            refresh_token=request.refresh_token  # Return same refresh token
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error refreshing token: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal refresh token"
        )


@router.get("/me", response_model=CurrentUserResponse)
async def get_current_user_info(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user info
    
    Requires: Authorization header dengan access token
    """
    try:
        logger.info(f"👤 Getting user info for: {current_user.user_id}")
        
        auth_repo = AuthRepository(db)
        user = auth_repo.get_user_by_id(current_user.user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User tidak ditemukan"
            )
        
        # Get user's all company roles
        user_roles = auth_repo.get_user_company_roles(current_user.user_id)
        companies = [
            {
                "company_id": str(role.company_id),
                "role": role.role
            }
            for role in user_roles
        ]
        
        return CurrentUserResponse(
            user_id=str(user.id),
            phone=user.phone,
            company_id=str(current_user.company_id),
            role=current_user.role,
            companies=companies
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting user info: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal mengambil informasi user"
        )


@router.post("/logout")
async def logout(
    request: LogoutRequest,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Logout user (revoke refresh token)
    
    Requires: Authorization header + refresh token dalam body
    """
    try:
        logger.info(f"🚪 Logout for user: {current_user.user_id}")
        
        token_service = TokenService()
        success = token_service.revoke_refresh_token(db, request.refresh_token)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Gagal logout"
            )
        
        logger.info(f"✅ User logged out: {current_user.user_id}")
        
        return {
            "success": True,
            "message": "Logout berhasil"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error during logout: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Gagal logout"
        )
