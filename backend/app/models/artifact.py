import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Enum, BigInteger, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.enums import ArtifactType

def utcnow():
    return datetime.now(timezone.utc)

class Artifact(Base):
    __tablename__ = "artifacts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    artifact_type = Column(Enum(ArtifactType, name="artifact_type_enum"), nullable=False)
    
    storage_provider = Column(String, nullable=False, default="LOCAL")
    storage_path = Column(String, nullable=False)
    
    checksum = Column(String, nullable=True)
    size_bytes = Column(BigInteger, nullable=True)
    content_type = Column(String, nullable=True)
    
    source_request_id = Column(UUID(as_uuid=True), ForeignKey("source_request_ledger.id", use_alter=True, name="fk_artifact_source_request"), nullable=True)
    metadata_json = Column(JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)
    
    # We will define relationship from SourceRequestLedger to Artifact later
