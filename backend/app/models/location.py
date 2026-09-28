import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.schema import UniqueConstraint
from app.core.database import Base

def utcnow():
    return datetime.now(timezone.utc)

class State(Base):
    __tablename__ = "states"
    __table_args__ = (
        UniqueConstraint("source_system", "source_id", name="uq_state_source"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_system = Column(String, nullable=False, default="IGR_MAHARASHTRA")
    source_id = Column(String, nullable=False)
    name_en = Column(String, nullable=False)
    name_mr = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    
    districts = relationship("District", back_populates="state")

class District(Base):
    __tablename__ = "districts"
    __table_args__ = (
        UniqueConstraint("source_system", "source_id", "state_id", name="uq_district_source"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    state_id = Column(UUID(as_uuid=True), ForeignKey("states.id"), nullable=False)
    source_system = Column(String, nullable=False, default="IGR_MAHARASHTRA")
    source_id = Column(String, nullable=False)
    name_en = Column(String, nullable=False)
    name_mr = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    state = relationship("State", back_populates="districts")
    talukas = relationship("Taluka", back_populates="district")

class Taluka(Base):
    __tablename__ = "talukas"
    __table_args__ = (
        UniqueConstraint("source_system", "source_id", "district_id", name="uq_taluka_source"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    district_id = Column(UUID(as_uuid=True), ForeignKey("districts.id"), nullable=False)
    source_system = Column(String, nullable=False, default="IGR_MAHARASHTRA")
    source_id = Column(String, nullable=False)
    name_en = Column(String, nullable=False)
    name_mr = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    district = relationship("District", back_populates="talukas")
    villages = relationship("Village", back_populates="taluka")

class Village(Base):
    __tablename__ = "villages"
    __table_args__ = (
        UniqueConstraint("source_system", "source_id", "taluka_id", name="uq_village_source"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    taluka_id = Column(UUID(as_uuid=True), ForeignKey("talukas.id"), nullable=False)
    source_system = Column(String, nullable=False, default="IGR_MAHARASHTRA")
    source_id = Column(String, nullable=False)
    name_en = Column(String, nullable=False)
    name_mr = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    taluka = relationship("Taluka", back_populates="villages")
