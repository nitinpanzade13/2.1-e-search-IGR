import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, DateTime, Boolean, ForeignKey, Integer, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from app.core.database import Base
from app.models.enums import SearchJobStatus, PdfTaskStatus, IngestionRunStatus, BulkFetchJobStatus, CoverageStatus, ScopeType
import app.models.artifact  # Register Artifact in SQLAlchemy before PdfTask relationship resolves

def utcnow():
    return datetime.now(timezone.utc)

class BulkFetchJob(Base):
    __tablename__ = "bulk_fetch_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scope_type = Column(Enum(ScopeType, name="scope_type_enum"), nullable=False, index=True)
    
    state_id = Column(String, nullable=True)
    district_id = Column(UUID(as_uuid=True), ForeignKey("districts.id"), nullable=True, index=True)
    taluka_id = Column(UUID(as_uuid=True), ForeignKey("talukas.id"), nullable=True, index=True)
    village_id = Column(UUID(as_uuid=True), ForeignKey("villages.id"), nullable=True, index=True)
    
    requested_year_start = Column(Integer, nullable=True)
    requested_year_end = Column(Integer, nullable=True)
    
    status = Column(Enum(BulkFetchJobStatus, name="bulk_fetch_job_status_enum"), default=BulkFetchJobStatus.QUEUED, index=True)
    coverage_status = Column(Enum(CoverageStatus, name="coverage_status_enum"), default=CoverageStatus.UNKNOWN)
    
    total_units = Column(Integer, default=0)
    queued_units = Column(Integer, default=0)
    running_units = Column(Integer, default=0)
    completed_units = Column(Integer, default=0)
    failed_units = Column(Integer, default=0)
    truncated_units = Column(Integer, default=0)
    rate_limited_units = Column(Integer, default=0)
    paused_units = Column(Integer, default=0)
    
    total_records_reported = Column(Integer, default=0)
    total_records_retrieved = Column(Integer, default=0)
    
    error_message = Column(String, nullable=True)
    
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    scope = Column(JSONB, nullable=True)
    status = Column(Enum(IngestionRunStatus, name="ingestion_run_status_enum"), default=IngestionRunStatus.PLANNED)

    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    total_jobs = Column(Integer, default=0)
    completed_jobs = Column(Integer, default=0)
    failed_jobs = Column(Integer, default=0)
    truncated_jobs = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

class SearchJob(Base):
    __tablename__ = "search_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ingestion_run_id = Column(UUID(as_uuid=True), ForeignKey("ingestion_runs.id"), nullable=True, index=True)
    bulk_fetch_job_id = Column(UUID(as_uuid=True), ForeignKey("bulk_fetch_jobs.id"), nullable=True, index=True)
    
    year = Column(Integer, nullable=False, index=True)
    location_params = Column(JSONB, nullable=False) # e.g. {"district_id": "...", "taluka_id": "...", "village_id": "..."}
    survey_prefix = Column(String, nullable=True)
    
    status = Column(Enum(SearchJobStatus, name="search_job_status_enum"), default=SearchJobStatus.QUEUED, index=True)
    coverage_status = Column(Enum(CoverageStatus, name="coverage_status_enum", create_type=False), default=CoverageStatus.UNKNOWN)
    
    requested_count = Column(Integer, nullable=True)
    retrieved_count = Column(Integer, nullable=True)
    truncated = Column(Boolean, default=False)
    
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    attempt_count = Column(Integer, default=0)
    last_error = Column(String, nullable=True)
    last_error_category = Column(String, nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    
    ingestion_run = relationship("IngestionRun")
    bulk_fetch_job = relationship("BulkFetchJob")
    registrations = relationship("SearchJobRegistration", back_populates="search_job", cascade="all, delete-orphan")


class SearchJobRegistration(Base):
    __tablename__ = "search_job_registrations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    search_job_id = Column(UUID(as_uuid=True), ForeignKey("search_jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    registration_id = Column(UUID(as_uuid=True), ForeignKey("registrations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    created_at = Column(DateTime(timezone=True), default=utcnow)
    
    search_job = relationship("SearchJob", back_populates="registrations")
    registration = relationship("Registration", back_populates="search_jobs")

    from sqlalchemy import UniqueConstraint
    __table_args__ = (
        UniqueConstraint("search_job_id", "registration_id", name="uq_search_job_registration"),
    )


class PdfTask(Base):
    __tablename__ = "pdf_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    registration_id = Column(UUID(as_uuid=True), ForeignKey("registrations.id"), nullable=False, index=True)
    
    indexii_url = Column(String, nullable=False)
    source_token = Column(String, nullable=False)
    
    status = Column(Enum(PdfTaskStatus, name="pdf_task_status_enum"), default=PdfTaskStatus.QUEUED, index=True)
    
    attempt_count = Column(Integer, default=0)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True, index=True)
    
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    
    last_error = Column(String, nullable=True)
    last_error_category = Column(String, nullable=True)
    
    artifact_id = Column(UUID(as_uuid=True), ForeignKey("artifacts.id"), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    
    registration = relationship("Registration", back_populates="pdf_task")
    artifact = relationship("Artifact")
