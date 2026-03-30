from sqlalchemy.orm import Session
from app.models.database import PayslipUploadSession, PayslipUploadRow
from uuid import UUID
from datetime import datetime
from typing import Optional
import json

class UploadSessionRepository:
    def __init__(self, session: Session):
        self.session = session
    
    def create_session(self, data: dict) -> PayslipUploadSession:
        """Create upload session"""
        session = PayslipUploadSession(**data)
        self.session.add(session)
        return session
    
    def get_session(self, upload_session_id: UUID) -> Optional[PayslipUploadSession]:
        """Get session by ID"""
        return self.session.query(PayslipUploadSession).filter(
            PayslipUploadSession.upload_session_id == upload_session_id
        ).first()
    
    def update_status(self, upload_session_id: UUID, status: str, **kwargs):
        """Update session status and other fields"""
        session = self.get_session(upload_session_id)
        if session:
            session.status = status
            session.updated_at = datetime.utcnow()
            for key, value in kwargs.items():
                if hasattr(session, key):
                    setattr(session, key, value)
        return session
    
    def update_processing_state(self, upload_session_id: UUID, state: dict):
        """Update processing state checkpoint"""
        session = self.get_session(upload_session_id)
        if session:
            session.processing_state = state
            session.updated_at = datetime.utcnow()
        return session
    
    def set_result(self, upload_session_id: UUID, result: dict):
        """Set final result of upload"""
        session = self.get_session(upload_session_id)
        if session:
            session.result = result
            session.status = 'completed'
            session.updated_at = datetime.utcnow()
        return session
    
    def create_upload_row(self, data: dict) -> PayslipUploadRow:
        """Create upload row tracking"""
        row = PayslipUploadRow(**data)
        self.session.add(row)
        return row
    
    def update_upload_row(self, upload_session_id: UUID, row_number: int, status: str, error_message: str = None, payslip_id: UUID = None):
        """Update row status after processing"""
        row = self.session.query(PayslipUploadRow).filter(
            PayslipUploadRow.upload_session_id == upload_session_id,
            PayslipUploadRow.row_number == row_number
        ).first()
        
        if row:
            row.status = status
            row.error_message = error_message
            row.payslip_id = payslip_id
            row.processed_at = datetime.utcnow()
        return row