"""
OTP Service untuk phone-based authentication
Handle OTP generation, sending, dan verification
"""

import logging
import os
import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from sqlalchemy.orm import Session
from app.models.database import OTPToken, User, RefreshToken
from uuid import UUID

logger = logging.getLogger(__name__)


class OTPService:
    """
    Service untuk manage OTP authentication
    - Generate OTP
    - Send OTP via third-party provider (configurable)
    - Verify OTP
    - Manage OTP expiration dan failed attempts
    """
    
    # Constants
    OTP_LENGTH = 6
    OTP_EXPIRATION_MINUTES = 5
    MAX_FAILED_ATTEMPTS = 3
    
    def __init__(self, 
                 otp_expiration_minutes: int = OTP_EXPIRATION_MINUTES,
                 max_failed_attempts: int = MAX_FAILED_ATTEMPTS):
        self.otp_expiration_minutes = otp_expiration_minutes
        self.max_failed_attempts = max_failed_attempts
    
    @staticmethod
    def _generate_otp_code(length: int = OTP_LENGTH) -> str:
        """
        Generate random OTP code
        Returns 6-digit numeric string
        """
        return ''.join([str(secrets.randbelow(10)) for _ in range(length)])
    
    @staticmethod
    def _hash_otp(otp_code: str) -> str:
        """
        Hash OTP code using SHA256 (store hashed version di database)
        """
        return hashlib.sha256(otp_code.encode()).hexdigest()
    
    async def request_otp(self, 
                         db: Session, 
                         phone: str) -> Tuple[bool, str, Optional[str]]:
        """
        Request OTP untuk nomor telepon
        
        Flow:
        1. Normalize phone number
        2. Cek atau buat User dengan phone ini
        3. Generate OTP code
        4. Create/Update OTPToken record
        5. Send OTP via third-party provider
        
        Returns:
            (success, message, request_id)
        """
        try:
            # Normalize phone
            phone = self._normalize_phone(phone)
            logger.info(f"📱 OTP request untuk: {phone}")
            
            # Check if user exists - reject if not registered
            user = db.query(User).filter(User.phone == phone).first()
            if not user:
                logger.warning(f"⚠️ Phone not registered: {phone}")
                return False, "Nomor telepon tidak terdaftar. Silakan hubungi administrator.", None
            
            # Generate OTP
            otp_code = self._generate_otp_code()
            otp_hash = self._hash_otp(otp_code)
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=self.otp_expiration_minutes)
            
            # Revoke OTP lama yang masih aktif
            old_otps = db.query(OTPToken).filter(
                OTPToken.user_id == user.id,
                OTPToken.is_used == False,
                OTPToken.expires_at > datetime.now(timezone.utc)
            ).all()
            
            for old_otp in old_otps:
                old_otp.is_used = True
            
            # Create OTP record baru
            otp_token = OTPToken(
                user_id=user.id,
                phone=phone,
                otp_hash=otp_hash,
                failed_attempts=0,
                expires_at=expires_at,
                is_used=False
            )
            db.add(otp_token)
            db.commit()
            
            # Send OTP via provider
            success = await self._send_otp_via_provider(phone, otp_code)
            
            if success:
                logger.info(f"✅ OTP sent to {phone}")
                return True, f"OTP telah dikirim ke {phone}", str(otp_token.id)
            else:
                logger.error(f"❌ Failed to send OTP to {phone}")
                return False, "Gagal mengirim OTP. Coba lagi nanti.", None
                
        except Exception as e:
            logger.error(f"❌ OTP request error: {str(e)}")
            return False, f"Error: {str(e)}", None
    
    async def verify_otp(self,
                        db: Session,
                        phone: str,
                        otp_code: str) -> Tuple[bool, str, Optional[UUID]]:
        """
        Verify OTP yang user masukkan
        
        Returns:
            (success, message, user_id)
        """
        try:
            phone = self._normalize_phone(phone)
            logger.info(f"🔍 Verifying OTP untuk {phone}")
            
            # DEV MODE: Accept test OTP code (only for existing users)
            dev_mode = True  # os.getenv("DEV_MODE", "false").lower() == "true"
            if dev_mode and otp_code == "123456":
                logger.info(f"🔓 DEV MODE: Accepting test OTP for {phone}")
                user = db.query(User).filter(User.phone == phone).first()
                if not user:
                    logger.warning(f"⚠️ DEV MODE: Phone not registered: {phone}")
                    return False, "Nomor telepon tidak terdaftar", None
                user.last_login_at = datetime.now(timezone.utc)
                db.commit()
                logger.info(f"✅ DEV MODE login for user {user.id}")
                return True, "Login berhasil (dev mode)", user.id
            
            # Hash OTP yang di-input
            otp_hash = self._hash_otp(otp_code)
            
            # Cari OTP record
            otp_token = db.query(OTPToken).filter(
                OTPToken.phone == phone,
                OTPToken.is_used == False,
                OTPToken.expires_at > datetime.now(timezone.utc)
            ).order_by(OTPToken.created_at.desc()).first()
            
            if not otp_token:
                logger.warning(f"⚠️  No valid OTP untuk {phone}")
                return False, "OTP tidak valid atau sudah kadaluarsa", None
            
            # Check failed attempts
            if otp_token.failed_attempts >= self.max_failed_attempts:
                logger.warning(f"⚠️  Too many failed attempts for {phone}")
                return False, "Terlalu banyak percobaan. Mohon request OTP baru", None
            
            # Verify OTP
            if otp_token.otp_hash == otp_hash:
                # Mark as used
                otp_token.is_used = True
                otp_token.failed_attempts = 0
                
                # Update user last login - query user directly since no relationship defined
                user = db.query(User).filter(User.id == otp_token.user_id).first()
                if user:
                    user.last_login_at = datetime.now(timezone.utc)
                
                db.commit()
                logger.info(f"✅ OTP verified for user {otp_token.user_id}")
                return True, "OTP verified", otp_token.user_id
            else:
                # Increment failed attempts
                otp_token.failed_attempts += 1
                db.commit()
                
                remaining = self.max_failed_attempts - otp_token.failed_attempts
                logger.warning(f"⚠️  Invalid OTP for {phone}. Remaining: {remaining}")
                
                if remaining > 0:
                    return False, f"OTP salah. Sisa percobaan: {remaining}", None
                else:
                    return False, "Terlalu banyak percobaan. Mohon request OTP baru", None
        
        except Exception as e:
            logger.error(f"❌ OTP verification error: {str(e)}")
            return False, f"Error: {str(e)}", None
    
    @staticmethod
    def _normalize_phone(phone: str) -> str:
        """
        Normalize phone number ke format +62xxx
        Support input: 62xxx, +62xxx, 0xxx
        """
        original_phone = phone
        # Remove whitespace dan special chars
        phone = phone.strip().replace(" ", "").replace("-", "")
        
        # Skip if already normalized (+62 format)
        if phone.startswith("+62"):
            return phone
        
        # Handle +62 prefix without +
        if phone.startswith("62") and len(phone) > 10:
            phone = "+" + phone
            return phone
        
        # Handle 0 prefix (Indonesia)
        if phone.startswith("0"):
            phone = "62" + phone[1:]
        
        # Ensure +62 prefix
        if not phone.startswith("+"):
            phone = "+" + phone
        
        logger.info(f"📱 Phone normalized: {original_phone} -> {phone}")
        return phone
    
    async def _send_otp_via_provider(self, phone: str, otp_code: str) -> bool:
        """
        Send OTP via third-party SMS provider
        
        TODO: Implement actual provider integration:
        - Twilio
        - Nexmo/Vonage
        - AWS SNS
        - Firebase
        - Custom provider
        
        For now: Mock implementation
        """
        try:
            # Mock: Log OTP untuk development
            logger.info(f"📨 [MOCK] Sending OTP to {phone}: {otp_code}")
            
            # TODO: Integrate dengan actual SMS provider
            # Example untuk Twilio:
            # from twilio.rest import Client
            # client = Client(ACCOUNT_SID, AUTH_TOKEN)
            # message = client.messages.create(
            #     body=f"Kode OTP Anda: {otp_code}",
            #     from_=TWILIO_PHONE_NUMBER,
            #     to=phone
            # )
            
            # Simulate success
            return True
        
        except Exception as e:
            logger.error(f"❌ Failed to send OTP: {str(e)}")
            return False
    
    async def request_email_otp(self, db: Session, email: str) -> Tuple[bool, str, Optional[str]]:
        """
        Request OTP untuk email
        DEV MODE: Mock (always succeed)
        PROD MODE: Send real email
        """
        try:
            is_dev_mode = os.getenv('DEV_MODE', 'true').lower() == 'true'
            logger.info(f"📧 Email OTP request for: {email} (DEV_MODE: {is_dev_mode})")
            
            # Check if user exists by email
            user = db.query(User).filter(User.email == email).first()
            if not user:
                logger.warning(f"⚠️ Email not registered: {email}")
                return False, "Email tidak terdaftar. Silakan hubungi administrator.", None
            
            # Generate OTP
            otp_code = self._generate_otp_code()
            otp_hash = self._hash_otp(otp_code)
            expires_at = datetime.now(timezone.utc) + timedelta(minutes=self.otp_expiration_minutes)
            
            # Revoke old OTPs
            old_otps = db.query(OTPToken).filter(
                OTPToken.user_id == user.id,
                OTPToken.is_used == False,
                OTPToken.expires_at > datetime.now(timezone.utc)
            ).all()
            
            for old_otp in old_otps:
                old_otp.is_used = True
            
            # Create OTP record
            otp_token = OTPToken(
                user_id=user.id,
                phone=email,  # Use email as phone field
                otp_hash=otp_hash,
                failed_attempts=0,
                expires_at=expires_at,
                is_used=False
            )
            db.add(otp_token)
            db.commit()
            
            # Send email (mock in dev, real in prod)
            if is_dev_mode:
                logger.info(f"📧 DEV MODE: Email OTP for {email}: {otp_code}")
                return True, f"OTP dikirim (DEV MODE). Kode: {otp_code}", str(otp_token.id)
            else:
                # Send real email
                success = await self._send_email_otp(email, otp_code)
                if success:
                    return True, "OTP dikirim ke email Anda", str(otp_token.id)
                else:
                    return False, "Gagal mengirim OTP ke email", None
        
        except Exception as e:
            logger.error(f"❌ Error requesting email OTP: {str(e)}")
            return False, "Gagal memproses request OTP", None
    
    async def verify_email_otp(self, db: Session, email: str, otp_code: str) -> Tuple[bool, str, Optional[str]]:
        """
        Verify Email OTP
        """
        try:
            is_dev_mode = os.getenv('DEV_MODE', 'true').lower() == 'true'
            logger.info(f"🔐 Verifying email OTP for: {email}")
            
            # Find user by email
            user = db.query(User).filter(User.email == email).first()
            if not user:
                return False, "Email tidak terdaftar", None
            
            # Find valid OTP
            otp_token = db.query(OTPToken).filter(
                OTPToken.user_id == user.id,
                OTPToken.phone == email,
                OTPToken.is_used == False,
                OTPToken.expires_at > datetime.now(timezone.utc)
            ).order_by(OTPToken.created_at.desc()).first()
            
            if not otp_token:
                return False, "OTP tidak ditemukan atau sudah expired", None
            
            # Check attempts
            if otp_token.failed_attempts >= self.max_failed_attempts:
                otp_token.is_used = True
                db.commit()
                return False, "Terlalu banyak percobaan gagal. Silakan request OTP lagi.", None
            
            # Verify OTP
            if is_dev_mode:
                # DEV MODE: Accept any 6-digit code
                if len(otp_code) == 6 and otp_code.isdigit():
                    otp_token.is_used = True
                    db.commit()
                    return True, "OTP verified", str(user.id)
            else:
                # PROD MODE: Verify hash
                otp_hash = self._hash_otp(otp_code)
                if otp_token.otp_hash == otp_hash:
                    otp_token.is_used = True
                    db.commit()
                    return True, "OTP verified", str(user.id)
            
            # Failed attempt
            otp_token.failed_attempts += 1
            db.commit()
            return False, "Kode OTP salah", None
        
        except Exception as e:
            logger.error(f"❌ Error verifying email OTP: {str(e)}")
            return False, "Gagal memverifikasi OTP", None
    
    async def _send_email_otp(self, email: str, otp_code: str) -> bool:
        """
        Send OTP via email (placeholder for real implementation)
        """
        # TODO: Implement real email sending (e.g., using SendGrid, Mailgun, or SMTP)
        logger.info(f"📧 Sending email OTP to {email}: {otp_code}")
        return True
    
    @staticmethod
    def cleanup_expired_otps(db: Session) -> int:
        """
        Delete expired OTP records (cleanup task)
        """
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=1)
        
        count = db.query(OTPToken).filter(
            OTPToken.created_at < cutoff_time,
            OTPToken.is_used == True
        ).delete()
        
        db.commit()
        logger.info(f"🧹 Cleaned up {count} expired OTP records")
        return count
