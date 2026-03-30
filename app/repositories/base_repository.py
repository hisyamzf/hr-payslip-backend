from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import TypeVar, Generic, List, Optional
from uuid import UUID

T = TypeVar('T')

class BaseRepository(Generic[T]):
    def __init__(self, session: Session, model: T = None):
        self.session = session
        self.db = session  # Alias for compatibility
        self.model = model
    
    def create(self, obj: dict) -> T:
        """Create new record"""
        db_obj = self.model(**obj)
        self.session.add(db_obj)
        return db_obj
    
    def get_by_id(self, id: UUID) -> Optional[T]:
        """Get record by ID"""
        return self.session.query(self.model).filter(self.model.id == id).first()
    
    def update(self, id: UUID, obj: dict) -> Optional[T]:
        """Update record"""
        db_obj = self.get_by_id(id)
        if db_obj:
            for key, value in obj.items():
                setattr(db_obj, key, value)
        return db_obj
    
    def flush(self):
        """Flush changes (within transaction)"""
        self.session.flush()
    
    def commit(self):
        """Commit transaction"""
        self.session.commit()
    
    def rollback(self):
        """Rollback transaction"""
        self.session.rollback()