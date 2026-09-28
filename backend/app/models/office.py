import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class Office(Base):
    __tablename__ = "offices"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    district_id = Column(UUID(as_uuid=True), ForeignKey("districts.id"), nullable=True)
    source_system = Column(String, nullable=False, default="IGR_MAHARASHTRA")
    source_id = Column(String, nullable=False) # e.g. "0006"
    name = Column(String, nullable=False)
    name_mr = Column(String, nullable=True)
    
    metadata_json = Column(JSONB, nullable=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    
    district = relationship("District")
