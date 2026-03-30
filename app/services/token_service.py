"""
JWT Token Management utilities
Handle access token dan refresh token creation dan verification
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
import jwt
from uuid import UUID
from sqlalchemy.orm import Session
from app.models.database import RefreshToken, User
import os
import hashlib
import secrets

logger = logging.getLogger(__name__)

# Get JWT config dari environment
JWT_SECRET = os.getenv('JWT_SECRET', 'your-super-secret-jwt-key-change-in-production-minimum-32-chars')
JWT_ALGORITHM = os.getenv('JWT_ALGORITHM', 'HS256')
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv('ACCESS_TOKEN_EXPIRE_MINUTES', 60))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv('REFRESH_TOKEN_EXPIRE_DAYS', 7))


class TokenService:
    """
    Service untuk manage JWT tokens (access + refresh)
    """
    
    @staticmethod
    def create_access_token(
        user_id: UUID,
        company_id: UUID,
        role: str,
        expires_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES
    ) -> str:
        """
        Create access token (JWT)
        
        Payload:
        {
            "sub": user_id,
            "company_id": company_id,
            "role": role,
            "type": "access",
            "exp": expiration_time,
            "iat": issued_time
        }
        """
        try:
            now = datetime.now(timezone.utc)
            exp = now + timedelta(minutes=expires_minutes)
            
            payload = {
                "sub": str(user_id),
                "company_id": str(company_id),
                "role": role,
                "type": "access",
                "exp": exp,
                "iat": now
            }
            
            token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
            logger.debug(f"✅ Access token created for user {user_id}")
            return token
        
        except Exception as e:
            logger.error(f"❌ Error creating access token: {str(e)}")
            raise
    
    @staticmethod
    def create_refresh_token(
        db: Session,
        user_id: UUID,
        device_info: str = None,
        ip_address: str = None,
        expires_days: int = REFRESH_TOKEN_EXPIRE_DAYS
    ) -> str:
        """
        Create refresh token dan store di database
        
        Returns:
            token string untuk client
        """
        try:
            # Generate random token
            token_string = secrets.token_urlsafe(32)
            token_hash = hashlib.sha256(token_string.encode()).hexdigest()
            
            exp = datetime.now(timezone.utc) + timedelta(days=expires_days)
            
            # Store di database
            refresh_token = RefreshToken(
                user_id=user_id,
                token_hash=token_hash,
                expires_at=exp,
                is_revoked=False,
                device_info=device_info,
                ip_address=ip_address
            )
            db.add(refresh_token)
            db.commit()
            
            logger.debug(f"✅ Refresh token created and stored for user {user_id}")
            return token_string
        
        except Exception as e:
            logger.error(f"❌ Error creating refresh token: {str(e)}")
            db.rollback()
            raise
    
    @staticmethod
    def verify_access_token(token: str) -> Optional[Dict[str, Any]]:
        """
        Verify dan decode access token
        
        Returns:
            payload dict atau None jika invalid
        """
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            
            # Verify token type
            if payload.get("type") != "access":
                logger.warning("⚠️ Invalid token type")
                return None
            
            return payload
        
        except jwt.ExpiredSignatureError:
            logger.warning("⚠️ Token expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"⚠️ Invalid token: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"❌ Error verifying token: {str(e)}")
            return None
    
    @staticmethod
    def verify_refresh_token(db: Session, token: str) -> Optional[UUID]:
        """
        Verify refresh token
        
        Returns:
            user_id jika valid, None jika invalid
        """
        try:
            # Hash token yang di-submit
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            
            # Cari di database
            refresh_token = db.query(RefreshToken).filter(
                RefreshToken.token_hash == token_hash,
                RefreshToken.is_revoked == False,
                RefreshToken.expires_at > datetime.now(timezone.utc)
            ).first()
            
            if not refresh_token:
                logger.warning("⚠️ Refresh token not found or invalid")
                return None
            
            logger.debug(f"✅ Refresh token verified for user {refresh_token.user_id}")
            return refresh_token.user_id
        
        except Exception as e:
            logger.error(f"❌ Error verifying refresh token: {str(e)}")
            return None
    
    @staticmethod
    def revoke_refresh_token(db: Session, token: str) -> bool:
        """
        Revoke refresh token (logout)
        """
        try:
            token_hash = hashlib.sha256(token.encode()).hexdigest()
            
            refresh_token = db.query(RefreshToken).filter(
                RefreshToken.token_hash == token_hash
            ).first()
            
            if not refresh_token:
                logger.warning("⚠️ Refresh token not found for revocation")
                return False
            
            refresh_token.is_revoked = True
            refresh_token.revoked_at = datetime.now(timezone.utc)
            db.commit()
            
            logger.info(f"✅ Refresh token revoked for user {refresh_token.user_id}")
            return True
        
        except Exception as e:
            logger.error(f"❌ Error revoking refresh token: {str(e)}")
            db.rollback()
            return False
    
    @staticmethod
    def cleanup_expired_tokens(db: Session) -> int:
        """
        Delete expired refresh tokens (cleanup task)
        """
        try:
            cutoff_time = datetime.now(timezone.utc)
            
            count = db.query(RefreshToken).filter(
                RefreshToken.expires_at < cutoff_time
            ).delete()
            
            db.commit()
            logger.info(f"🧹 Cleaned up {count} expired refresh tokens")
            return count
        
        except Exception as e:
            logger.error(f"❌ Error cleaning up tokens: {str(e)}")
            db.rollback()
            return 0
