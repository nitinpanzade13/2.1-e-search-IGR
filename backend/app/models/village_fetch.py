import uuid
from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class VillageFetchStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class VillageFetch(Base):
    __tablename__ = "village_fetches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    village_id = Column(UUID(as_uuid=True), ForeignKey("villages.id", ondelete="CASCADE"), nullable=False, index=True)
    year = Column(Integer, nullable=False)
    status = Column(String(32), default="QUEUED", nullable=False, index=True)
    survey_range_start = Column(Integer, default=1, nullable=False)
    survey_range_end = Column(Integer, default=100, nullable=False)
    current_search_value = Column(String(64), nullable=True)
    processed_search_count = Column(Integer, default=0, nullable=False)
    records_found = Column(Integer, default=0, nullable=False)
    unique_records_saved = Column(Integer, default=0, nullable=False)
    duplicates_skipped = Column(Integer, default=0, nullable=False)
    truncated_searches_count = Column(Integer, default=0, nullable=False)
    errors_count = Column(Integer, default=0, nullable=False)
    last_error = Column(Text, nullable=True)
    
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)

    village = relationship("Village")
