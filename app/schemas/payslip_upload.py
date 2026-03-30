from pydantic import BaseModel, Field
from datetime import date
from typing import Optional, Dict, Any, List
from uuid import UUID

# Request schemas
class CreateUploadSessionRequest(BaseModel):
    period_start: date
    period_end: date
    payment_date: date

class SubmitColumnMappingRequest(BaseModel):
    fixed_columns: Dict[str, Optional[str]]
    earnings: List[Dict[str, Any]]
    deductions: List[Dict[str, Any]]

class ProcessUploadRequest(BaseModel):
    upload_session_id: UUID

# Response schemas
class UploadSessionResponse(BaseModel):
    upload_session_id: UUID
    company_id: UUID
    status: str
    period_start: date
    period_end: date
    file_hash: Optional[str] = None
    created_at: str

class PayslipUploadRowResponse(BaseModel):
    row_number: int
    employee_number: str
    status: str
    error_message: Optional[str] = None
    payslip_id: Optional[UUID] = None

class ProcessResultResponse(BaseModel):
    success: int
    failed: int
    total: int
    errors: List[Dict[str, Any]]

class Config:
    from_attributes = True