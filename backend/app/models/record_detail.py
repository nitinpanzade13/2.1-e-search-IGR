import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class RecordDetail(Base):
    __tablename__ = "record_details"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    village_id = Column(UUID(as_uuid=True), ForeignKey("villages.id", ondelete="CASCADE"), nullable=False, index=True)
    year = Column(Integer, nullable=False, index=True)
    sr_no = Column(String(64), nullable=True)
    doc_no = Column(String(128), nullable=False, index=True)
    doc_type = Column(String(255), nullable=True)
    office = Column(String(255), nullable=True)
    date = Column(String(64), nullable=True)
    seller = Column(Text, nullable=True)
    buyer = Column(Text, nullable=True)
    other_info = Column(Text, nullable=True)
    indexii_url = Column(Text, nullable=True)
    source_query = Column(String(128), nullable=True)
    is_truncated = Column(Boolean, default=False, nullable=False)
    reported_count = Column(Integer, nullable=True)
    
    fetched_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    village = relationship("Village")
