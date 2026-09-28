import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Numeric, Date, Enum, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.enums import ProcessingStatus, PartyRole

def utcnow():
    return datetime.now(timezone.utc)

class Registration(Base):
    __tablename__ = "registrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    
    year = Column(Integer, nullable=False, index=True)
    doc_no = Column(String, nullable=False, index=True)
    doc_type = Column(String, nullable=False)
    
    office_id = Column(UUID(as_uuid=True), ForeignKey("offices.id"), nullable=True, index=True)
    office_name_raw = Column(String, nullable=True)
    office_name_normalized = Column(String, nullable=True, index=True)
    
    execution_date = Column(Date, nullable=True)
    registration_date = Column(Date, nullable=True, index=True)
    registration_date_raw = Column(String, nullable=True)
    
    seller_names_raw = Column(String, nullable=True)
    buyer_names_raw = Column(String, nullable=True)
    
    consideration_amount = Column(Numeric(15, 2), nullable=True)
    market_value = Column(Numeric(15, 2), nullable=True)
    stamp_duty = Column(Numeric(15, 2), nullable=True)
    registration_fee = Column(Numeric(15, 2), nullable=True)
    
    assessment_raw = Column(String, nullable=True)
    remarks_raw = Column(String, nullable=True)
    other_info_raw = Column(String, nullable=True)
    candidate_properties = Column(JSONB, nullable=True)
    
    source_token = Column(String, nullable=True, index=True)
    indexii_url = Column(String, nullable=True)
    
    source_identity_status = Column(String, nullable=True)
    processing_status = Column(Enum(ProcessingStatus, name="processing_status_enum"), default=ProcessingStatus.DISCOVERED, index=True)
    
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    
    office = relationship("Office")
    parties = relationship("Party", back_populates="registration", cascade="all, delete-orphan", order_by="Party.party_order")
    properties = relationship("Property", back_populates="registration", cascade="all, delete-orphan", order_by="Property.property_order")
    
    # Needs a string backref name for PdfTask because we import it in job.py
    pdf_task = relationship("PdfTask", back_populates="registration", uselist=False)
    
    search_jobs = relationship("SearchJobRegistration", back_populates="registration", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_registrations_office_doc_year", "office_id", "doc_no", "year"),
    )

class Party(Base):
    __tablename__ = "parties"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_id = Column(UUID(as_uuid=True), ForeignKey("registrations.id"), nullable=False, index=True)
    
    role = Column(Enum(PartyRole, name="party_role_enum"), nullable=False, index=True)
    party_order = Column(Integer, nullable=False)
    
    name = Column(String, nullable=True)
    age = Column(Integer, nullable=True)
    address = Column(String, nullable=True)
    
    raw_text = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    registration = relationship("Registration", back_populates="parties")

class Property(Base):
    __tablename__ = "properties"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_id = Column(UUID(as_uuid=True), ForeignKey("registrations.id"), nullable=False, index=True)
    
    property_order = Column(Integer, nullable=False)
    
    survey_no = Column(String, nullable=True, index=True)
    cts_no = Column(String, nullable=True, index=True)
    
    area_sqm = Column(Numeric(10, 2), nullable=True)
    area_value = Column(Numeric(10, 2), nullable=True)
    area_unit = Column(String, nullable=True)
    
    description_raw = Column(String, nullable=True)
    area_raw = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    
    registration = relationship("Registration", back_populates="properties")
