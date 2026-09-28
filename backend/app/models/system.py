import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Boolean, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class NetworkConfig(Base):
    __tablename__ = "network_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    profile_name = Column(String, nullable=False, unique=True, index=True)
    interface_name = Column(String, default="Wi-Fi", nullable=False)
    priority = Column(Integer, default=10, nullable=False)
    role = Column(String, default="FAILOVER", nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False)
    connection_timeout = Column(Integer, default=30, nullable=False)  # seconds
    validation_timeout = Column(Integer, default=10, nullable=False)  # seconds
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
