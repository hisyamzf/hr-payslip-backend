from sqlalchemy import Column, String, UUID, DateTime, Date, JSON, Numeric, Integer, Boolean, ForeignKey, Index, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone = Column(String(20), nullable=False, unique=True)
    last_login_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    company_roles = relationship("UserCompanyRole", back_populates="user", cascade="all, delete-orphan")
    employees = relationship("Employee", back_populates="user")


class Company(Base):
    __tablename__ = "companies"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    code = Column(String(50), nullable=False, unique=True)
    country = Column(String(50), nullable=False)
    currency = Column(String(3), nullable=False, default='IDR')
    status = Column(String(20), nullable=False, default='active')
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    employees = relationship("Employee", back_populates="company", cascade="all, delete-orphan")
    payslips = relationship("Payslip", back_populates="company", cascade="all, delete-orphan")
    company_roles = relationship("UserCompanyRole", back_populates="company", cascade="all, delete-orphan")
    contracts = relationship("Contract", back_populates="company", cascade="all, delete-orphan")


class UserCompanyRole(Base):
    __tablename__ = "user_company_roles"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey('companies.id', ondelete='CASCADE'), nullable=False)
    role = Column(String(50), nullable=False)  # 'admin', 'client_admin', 'client'
    is_active = Column(Boolean(), nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    user = relationship("User", back_populates="company_roles")
    company = relationship("Company", back_populates="company_roles")
    
    __table_args__ = (
        UniqueConstraint('user_id', 'company_id', name='user_company_roles_uk'),
        Index('idx_user_company_roles_company', 'company_id'),
    )


class Employee(Base):
    __tablename__ = "employees"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey('companies.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    employee_number = Column(String(50), nullable=False)
    date_of_birth = Column(Date(), nullable=False)
    join_date = Column(Date(), nullable=False)
    email = Column(String(100))
    bank_account = Column(String(100))
    employment_status = Column(String(20), nullable=False, default='active')
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    company = relationship("Company", back_populates="employees")
    user = relationship("User", back_populates="employees")
    payslips = relationship("Payslip", back_populates="employee")
    contract = relationship("Contract", back_populates="employee", uselist=False)
    
    __table_args__ = (
        UniqueConstraint('company_id', 'employee_number', name='employees_company_number_uk'),
        Index('idx_employees_company_status', 'company_id', 'employment_status'),
    )


class Contract(Base):
    __tablename__ = "contracts"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey('companies.id', ondelete='CASCADE'), nullable=False)
    employee_id = Column(UUID(as_uuid=True), ForeignKey('employees.id', ondelete='CASCADE'), nullable=False, unique=True)
    contract_type = Column(String(50), nullable=False)
    job_title = Column(String(100), nullable=False)
    department = Column(String(100), nullable=False)
    base_salary = Column(Numeric(15, 2), nullable=False)
    start_date = Column(Date(), nullable=False)
    end_date = Column(Date())
    file_url = Column(String(500))
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    company = relationship("Company", back_populates="contracts")
    employee = relationship("Employee", back_populates="contract")
    
    __table_args__ = (
        Index('idx_contracts_employee', 'employee_id'),
        Index('idx_contracts_company', 'company_id'),
    )


class Payslip(Base):
    __tablename__ = "payslips"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey('companies.id', ondelete='CASCADE'), nullable=False)
    employee_id = Column(UUID(as_uuid=True), ForeignKey('employees.id', ondelete='RESTRICT'), nullable=False)
    period_start = Column(Date(), nullable=False)
    period_end = Column(Date(), nullable=False)
    payment_date = Column(Date(), nullable=False)
    full_name = Column(String(200), nullable=False)
    department = Column(String(100), nullable=False)
    position = Column(String(100), nullable=False)
    earnings = Column(JSON(), nullable=False, default={})
    deductions = Column(JSON(), nullable=False, default={})
    gross_salary = Column(Numeric(15, 2), nullable=False)
    total_deductions = Column(Numeric(15, 2), nullable=False)
    net_salary = Column(Numeric(15, 2), nullable=False)
    notes = Column(String(500))
    status = Column(String(20), nullable=False, default='draft')
    file_url = Column(String(500))
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    company = relationship("Company", back_populates="payslips")
    employee = relationship("Employee", back_populates="payslips")
    
    __table_args__ = (
        UniqueConstraint('company_id', 'employee_id', 'period_start', name='payslips_company_employee_period_uk'),
        Index('idx_payslips_company_status', 'company_id', 'status'),
        Index('idx_payslips_employee_period', 'employee_id', 'period_start'),
    )


class PayslipUploadSession(Base):
    __tablename__ = "payslip_upload_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    upload_session_id = Column(
    UUID(as_uuid=True),
    ForeignKey('payslip_upload_sessions.upload_session_id', ondelete='CASCADE'),
    nullable=False
)
    company_id = Column(UUID(as_uuid=True), ForeignKey('companies.id', ondelete='CASCADE'), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_hash = Column(String(255), nullable=False)
    parent_upload_session_id = Column(UUID(as_uuid=True))
    period_start = Column(Date(), nullable=False)
    period_end = Column(Date(), nullable=False)
    payment_date = Column(Date(), nullable=False)
    status = Column(String(50), nullable=False, default='pending')
    column_mapping = Column(JSON())
    processing_state = Column(JSON())
    result = Column(JSON())
    created_by = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_payslip_uploads_company_status', 'company_id', 'status'),
        Index('idx_payslip_uploads_file_hash', 'file_hash'),
    )


class PayslipUploadRow(Base):
    __tablename__ = "payslip_upload_rows"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    upload_session_id = Column(UUID(as_uuid=True), ForeignKey('payslip_upload_sessions.id', ondelete='CASCADE'), nullable=False)
    row_number = Column(Integer(), nullable=False)
    employee_number = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)  # 'success', 'failed', 'skipped'
    error_message = Column(String(500))
    payslip_id = Column(UUID(as_uuid=True), ForeignKey('payslips.id', ondelete='SET NULL'))
    raw_data = Column(JSON())
    processed_at = Column(DateTime(timezone=True))
    
    __table_args__ = (
        Index('idx_payslip_upload_rows_session_status', 'upload_session_id', 'status'),
    )


class OTPToken(Base):
    __tablename__ = "otp_tokens"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    phone = Column(String(20), nullable=False)
    otp_hash = Column(String(255), nullable=False)
    failed_attempts = Column(Integer(), nullable=False, default=0)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_used = Column(Boolean(), nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_otp_tokens_user_expires', 'user_id', 'expires_at'),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey('companies.id', ondelete='CASCADE'), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'))
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    action = Column(String(50), nullable=False)  # 'create', 'update', 'delete'
    old_values = Column(JSON())
    new_values = Column(JSON())
    ip_address = Column(String(50))
    user_agent = Column(String(500))
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_audit_logs_company_entity', 'company_id', 'entity_type', 'entity_id'),
        Index('idx_audit_logs_created_at', 'created_at'),
    )


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    token_hash = Column(String(255), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_revoked = Column(Boolean(), nullable=False, default=False)
    device_info = Column(String(500))
    ip_address = Column(String(45))
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
    revoked_at = Column(DateTime(timezone=True))
    
    user = relationship("User", back_populates="refresh_tokens")
    
    __table_args__ = (
        Index('idx_refresh_tokens_user_id', 'user_id'),
        Index('idx_refresh_tokens_token_hash', 'token_hash'),
        Index('idx_refresh_tokens_expires', 'expires_at'),
    )


User.refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")