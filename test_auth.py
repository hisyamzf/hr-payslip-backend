"""
Test OTP Authentication Flow
Test phone + OTP login system
"""

import pytest
import asyncio
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from uuid import UUID

from app.services.otp_service import OTPService
from app.services.token_service import TokenService
from app.repositories.auth_repository import AuthRepository
from app.models.database import User, OTPToken, RefreshToken, UserCompanyRole
from app.config.database import SessionLocal


class TestOTPService:
    """Test OTP Service"""
    
    @pytest.fixture
    def db(self):
        """Database session fixture"""
        db = SessionLocal()
        yield db
        db.close()
    
    @pytest.fixture
    def otp_service(self):
        """OTP Service fixture"""
        return OTPService(otp_expiration_minutes=5, max_failed_attempts=3)
    
    def test_normalize_phone(self, otp_service):
        """Test phone number normalization"""
        # Test dengan +62
        assert otp_service._normalize_phone("+62812345678") == "+62812345678"
        
        # Test dengan 62
        assert otp_service._normalize_phone("62812345678") == "+62812345678"
        
        # Test dengan 0
        assert otp_service._normalize_phone("0812345678") == "+62812345678"
        
        # Test dengan spasi
        assert otp_service._normalize_phone("+62 812 345 678") == "+62812345678"
    
    def test_generate_otp_code(self, otp_service):
        """Test OTP code generation"""
        otp_code = otp_service._generate_otp_code(6)
        
        assert len(otp_code) == 6
        assert otp_code.isdigit()
    
    def test_hash_otp(self, otp_service):
        """Test OTP hashing"""
        otp_code = "123456"
        hashed = otp_service._hash_otp(otp_code)
        
        # Should be consistent
        assert otp_service._hash_otp(otp_code) == hashed
        
        # Different code should produce different hash
        assert otp_service._hash_otp("654321") != hashed
    
    @pytest.mark.asyncio
    async def test_request_otp(self, db: Session, otp_service: OTPService):
        """Test OTP request"""
        phone = "+62812345678"
        
        success, message, request_id = await otp_service.request_otp(db, phone)
        
        assert success is True
        assert request_id is not None
        assert "dikirim" in message.lower()
        
        # Check user created
        user = db.query(User).filter(User.phone == phone).first()
        assert user is not None
        
        # Check OTP token created
        otp_token = db.query(OTPToken).filter(
            OTPToken.user_id == user.id,
            OTPToken.is_used == False
        ).first()
        assert otp_token is not None
        assert otp_token.failed_attempts == 0
    
    @pytest.mark.asyncio
    async def test_verify_otp_success(self, db: Session, otp_service: OTPService):
        """Test successful OTP verification"""
        phone = "+62812345678"
        
        # Request OTP first
        success, message, _ = await otp_service.request_otp(db, phone)
        assert success
        
        # Get OTP token (note: in real test, we'd capture the OTP code)
        # For this test, we'll manually create a known OTP
        user = db.query(User).filter(User.phone == phone).first()
        otp_code = "123456"
        otp_hash = otp_service._hash_otp(otp_code)
        
        # Update the OTP token with our test code
        otp_token = db.query(OTPToken).filter(
            OTPToken.user_id == user.id,
            OTPToken.is_used == False
        ).first()
        otp_token.otp_hash = otp_hash
        db.commit()
        
        # Now verify
        success, message, returned_user_id = await otp_service.verify_otp(
            db, phone, otp_code
        )
        
        assert success is True
        assert returned_user_id == user.id
    
    @pytest.mark.asyncio
    async def test_verify_otp_invalid(self, db: Session, otp_service: OTPService):
        """Test invalid OTP verification"""
        phone = "+62812345678"
        
        # Request OTP
        success, _, _ = await otp_service.request_otp(db, phone)
        assert success
        
        # Try wrong OTP
        success, message, returned_user_id = await otp_service.verify_otp(
            db, phone, "999999"
        )
        
        assert success is False
        assert returned_user_id is None
        assert "salah" in message.lower()
    
    @pytest.mark.asyncio
    async def test_verify_otp_max_attempts(self, db: Session, otp_service: OTPService):
        """Test max failed attempts"""
        phone = "+62812345678"
        
        # Request OTP
        success, _, _ = await otp_service.request_otp(db, phone)
        assert success
        
        # Try wrong OTP 3 times
        for i in range(3):
            success, _, _ = await otp_service.verify_otp(
                db, phone, f"99999{i}"
            )
            assert success is False
        
        # Fourth attempt should be blocked
        success, message, _ = await otp_service.verify_otp(
            db, phone, "000000"
        )
        assert success is False
        assert "terlalu banyak" in message.lower()


class TestTokenService:
    """Test Token Service"""
    
    @pytest.fixture
    def token_service(self):
        """Token Service fixture"""
        return TokenService()
    
    @pytest.fixture
    def db(self):
        """Database session fixture"""
        db = SessionLocal()
        yield db
        db.close()
    
    def test_create_access_token(self, token_service: TokenService):
        """Test access token creation"""
        user_id = "123e4567-e89b-12d3-a456-426614174000"
        company_id = "223e4567-e89b-12d3-a456-426614174000"
        role = "client"
        
        token = token_service.create_access_token(
            user_id=UUID(user_id),
            company_id=UUID(company_id),
            role=role
        )
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
    
    def test_verify_access_token(self, token_service: TokenService):
        """Test access token verification"""
        user_id = "123e4567-e89b-12d3-a456-426614174000"
        company_id = "223e4567-e89b-12d3-a456-426614174000"
        role = "client"
        
        # Create token
        token = token_service.create_access_token(
            user_id=UUID(user_id),
            company_id=UUID(company_id),
            role=role
        )
        
        # Verify token
        payload = token_service.verify_access_token(token)
        
        assert payload is not None
        assert payload["sub"] == user_id
        assert payload["company_id"] == company_id
        assert payload["role"] == role
        assert payload["type"] == "access"
    
    def test_verify_invalid_token(self, token_service: TokenService):
        """Test invalid token verification"""
        payload = token_service.verify_access_token("invalid.token.here")
        
        assert payload is None
    
    def test_create_refresh_token(self, token_service: TokenService, db: Session):
        """Test refresh token creation"""
        # Create a user first
        user = User(phone="+62812345678")
        db.add(user)
        db.commit()
        
        # Create refresh token
        token = token_service.create_refresh_token(
            db=db,
            user_id=user.id,
            device_info="Test Device",
            ip_address="127.0.0.1"
        )
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
        
        # Verify token stored in DB
        from hashlib import sha256
        token_hash = sha256(token.encode()).hexdigest()
        
        refresh_token = db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash
        ).first()
        
        assert refresh_token is not None
        assert refresh_token.user_id == user.id
        assert refresh_token.is_revoked is False


class TestAuthRepository:
    """Test Auth Repository"""
    
    @pytest.fixture
    def db(self):
        """Database session fixture"""
        db = SessionLocal()
        yield db
        db.close()
    
    @pytest.fixture
    def auth_repo(self, db: Session):
        """Auth Repository fixture"""
        return AuthRepository(db)
    
    def test_get_or_create_user(self, auth_repo: AuthRepository, db: Session):
        """Test get or create user"""
        phone = "+62812345678"
        
        # First call should create
        user1 = auth_repo.get_or_create_user(phone)
        assert user1 is not None
        assert user1.phone == phone
        
        # Second call should get existing
        user2 = auth_repo.get_or_create_user(phone)
        assert user2.id == user1.id
    
    def test_assign_user_to_company(self, auth_repo: AuthRepository, db: Session):
        """Test assigning user to company"""
        # Create user and company
        user = User(phone="+62812345678")
        db.add(user)
        db.commit()
        
        from app.models.database import Company
        company = Company(
            name="Test Company",
            code="TEST",
            country="Indonesia",
            currency="IDR"
        )
        db.add(company)
        db.commit()
        
        # Assign user to company
        role_obj = auth_repo.assign_user_to_company(
            user_id=user.id,
            company_id=company.id,
            role="client"
        )
        
        assert role_obj is not None
        assert role_obj.user_id == user.id
        assert role_obj.company_id == company.id
        assert role_obj.role == "client"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
