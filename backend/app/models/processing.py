import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class ParserRun(Base):
    __tablename__ = "parser_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    artifact_id = Column(UUID(as_uuid=True), ForeignKey("artifacts.id"), nullable=False)
    
    parser_name = Column(String, nullable=False)
    parser_version = Column(String, nullable=False)
    
    parsed_at = Column(DateTime(timezone=True), default=utcnow)
    
    is_success = Column(Boolean, default=True)
    error_message = Column(String, nullable=True)
    
    # E.g., which registrations were created/updated
    output_metadata = Column(JSONB, nullable=True)
    
    artifact = relationship("Artifact")
