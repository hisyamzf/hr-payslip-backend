"""
Authentication Repository
Handle database operations untuk auth (User, OTP, RefreshToken)
"""

import logging
from typing import Optional
from uuid import UUID
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.database import User, UserCompanyRole, OTPToken, RefreshToken
from app.repositories.base_repository import BaseRepository

logger = logging.getLogger(__name__)


class AuthRepository(BaseRepository):
    """Repository untuk auth-related database operations"""
    
    def __init__(self, db: Session):
        super().__init__(db, None)
    
    # ==================== User Operations ====================
    
    def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID"""
        try:
            return self.db.query(User).filter(User.id == user_id).first()
        except Exception as e:
            logger.error(f"❌ Error getting user by id: {str(e)}")
            return None
    
    def get_user_by_phone(self, phone: str) -> Optional[User]:
        """Get user by phone number"""
        try:
            return self.db.query(User).filter(User.phone == phone).first()
        except Exception as e:
            logger.error(f"❌ Error getting user by phone: {str(e)}")
            return None
    
    def create_user(self, phone: str) -> Optional[User]:
        """Create new user"""
        try:
            user = User(
                phone=phone
            )
            self.db.add(user)
            self.db.commit()
            logger.info(f"✅ User created: {user.id}")
            return user
        except Exception as e:
            logger.error(f"❌ Error creating user: {str(e)}")
            self.db.rollback()
            return None
    
    def get_or_create_user(self, phone: str) -> Optional[User]:
        """Get existing user atau create baru"""
        user = self.get_user_by_phone(phone)
        if user:
            return user
        return self.create_user(phone)
    
    # ==================== User Company Role Operations ====================
    
    def get_user_company_role(self, user_id: UUID, company_id: UUID) -> Optional[UserCompanyRole]:
        """Get user's role dalam company"""
        try:
            return self.db.query(UserCompanyRole).filter(
                and_(
                    UserCompanyRole.user_id == user_id,
                    UserCompanyRole.company_id == company_id,
                    UserCompanyRole.is_active == True
                )
            ).first()
        except Exception as e:
            logger.error(f"❌ Error getting user company role: {str(e)}")
            return None
    
    def get_user_company_roles(self, user_id: UUID) -> list:
        """Get semua company roles untuk user"""
        try:
            return self.db.query(UserCompanyRole).filter(
                and_(
                    UserCompanyRole.user_id == user_id,
                    UserCompanyRole.is_active == True
                )
            ).all()
        except Exception as e:
            logger.error(f"❌ Error getting user company roles: {str(e)}")
            return []
    
    def assign_user_to_company(self, 
                              user_id: UUID, 
                              company_id: UUID, 
                              role: str) -> Optional[UserCompanyRole]:
        """Assign user ke company dengan role"""
        try:
            # Check if already exists
            existing = self.get_user_company_role(user_id, company_id)
            if existing:
                existing.is_active = True
                existing.role = role  # Update the role!
                self.db.commit()
                logger.info(f"✅ User-company role updated: {role}")
                return existing
            
            # Create new
            user_role = UserCompanyRole(
                user_id=user_id,
                company_id=company_id,
                role=role,
                is_active=True
            )
            self.db.add(user_role)
            self.db.commit()
            logger.info(f"✅ User assigned to company with role: {role}")
            return user_role
        except Exception as e:
            logger.error(f"❌ Error assigning user to company: {str(e)}")
            self.db.rollback()
            return None
    
    # ==================== OTP Operations ====================
    
    def get_active_otp(self, phone: str) -> Optional[OTPToken]:
        """Get OTP aktif untuk nomor telepon"""
        try:
            from datetime import datetime, timezone
            
            return self.db.query(OTPToken).filter(
                and_(
                    OTPToken.phone == phone,
                    OTPToken.is_used == False,
                    OTPToken.expires_at > datetime.now(timezone.utc)
                )
            ).order_by(OTPToken.created_at.desc()).first()
        except Exception as e:
            logger.error(f"❌ Error getting active OTP: {str(e)}")
            return None
    
    def mark_otp_used(self, otp_id: UUID) -> bool:
        """Mark OTP sebagai used"""
        try:
            otp = self.db.query(OTPToken).filter(OTPToken.id == otp_id).first()
            if not otp:
                return False
            
            otp.is_used = True
            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"❌ Error marking OTP as used: {str(e)}")
            self.db.rollback()
            return False
    
    # ==================== Refresh Token Operations ====================
    
    def get_refresh_token(self, token_hash: str) -> Optional[RefreshToken]:
        """Get refresh token by hash"""
        try:
            from datetime import datetime, timezone
            
            return self.db.query(RefreshToken).filter(
                and_(
                    RefreshToken.token_hash == token_hash,
                    RefreshToken.is_revoked == False,
                    RefreshToken.expires_at > datetime.now(timezone.utc)
                )
            ).first()
        except Exception as e:
            logger.error(f"❌ Error getting refresh token: {str(e)}")
            return None
    
    def revoke_user_tokens(self, user_id: UUID) -> int:
        """Revoke semua refresh tokens untuk user (logout dari semua devices)"""
        try:
            from datetime import datetime, timezone
            
            count = self.db.query(RefreshToken).filter(
                and_(
                    RefreshToken.user_id == user_id,
                    RefreshToken.is_revoked == False
                )
            ).update({"is_revoked": True, "revoked_at": datetime.now(timezone.utc)})
            
            self.db.commit()
            logger.info(f"✅ Revoked {count} refresh tokens for user {user_id}")
            return count
        except Exception as e:
            logger.error(f"❌ Error revoking tokens: {str(e)}")
            self.db.rollback()
            return 0
