from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from uuid import UUID
from app.models.enums import ScopeType, BulkFetchJobStatus, CoverageStatus

class BulkFetchCreateRequest(BaseModel):
    scope_type: ScopeType
    state_id: Optional[str] = None
    district_id: Optional[UUID] = None
    taluka_id: Optional[UUID] = None
    village_id: Optional[UUID] = None
    year_start: int = Field(..., ge=1985, le=2030)
    year_end: int = Field(..., ge=1985, le=2030)
    article_id: Optional[str] = None
    article_name: Optional[str] = None

class BulkFetchJobResponse(BaseModel):
    id: UUID
    scope_type: ScopeType
    status: BulkFetchJobStatus
    coverage_status: CoverageStatus
    
    district_id: Optional[UUID] = None
    district_source_id: Optional[str] = None
    district_name: Optional[str] = None
    
    taluka_id: Optional[UUID] = None
    taluka_source_id: Optional[str] = None
    taluka_name: Optional[str] = None
    
    village_id: Optional[UUID] = None
    village_source_id: Optional[str] = None
    village_name: Optional[str] = None
    
    requested_year_start: Optional[int] = None
    requested_year_end: Optional[int] = None
    
    total_units: int
    queued_units: int
    running_units: int
    completed_units: int
    failed_units: int
    truncated_units: int
    rate_limited_units: int
    paused_units: int
    
    total_records_reported: int
    total_records_retrieved: int
    
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    error_message: Optional[str] = None
    pdf_stats: Optional[Dict[str, int]] = None

class SearchJobChildResponse(BaseModel):
    id: UUID
    year: int
    location_params: dict
    status: str
    requested_count: Optional[int]
    retrieved_count: Optional[int]
    truncated: bool
    created_at: datetime
    completed_at: Optional[datetime]
    last_error: Optional[str]
