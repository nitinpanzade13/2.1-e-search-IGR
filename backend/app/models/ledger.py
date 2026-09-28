import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Integer, Enum, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.enums import RequestKind

def utcnow():
    return datetime.now(timezone.utc)

class SourceRequestLedger(Base):
    __tablename__ = "source_request_ledger"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_kind = Column(Enum(RequestKind, name="request_kind_enum"), nullable=False, index=True)
    
    # Generic reference to either search_jobs or pdf_tasks
    job_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    
    endpoint = Column(String, nullable=False)
    url_hash = Column(String, nullable=True)
    
    attempt_number = Column(Integer, default=1)
    
    started_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    
    http_status = Column(Integer, nullable=True)
    content_type = Column(String, nullable=True)
    response_size_bytes = Column(Integer, nullable=True)
    
    rate_limited = Column(Boolean, default=False, index=True)
    
    failure_category = Column(String, nullable=True)
    error_message = Column(String, nullable=True)
    
    network_context = Column(JSONB, nullable=True)
    
    artifact_id = Column(UUID(as_uuid=True), ForeignKey("artifacts.id"), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow, index=True)
    
    artifact = relationship("Artifact", foreign_keys=[artifact_id])

    __table_args__ = (
        Index("ix_ledger_kind_created", "request_kind", "created_at"),
    )
