from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID

class VillageFetchCreateRequest(BaseModel):
    district_id: UUID
    taluka_id: UUID
    village_id: UUID
    year: int = Field(..., ge=1985, le=2030)
    survey_range_start: Optional[int] = 1
    survey_range_end: Optional[int] = 100
    search_query: Optional[str] = None
    search_values: Optional[List[str]] = None
    article_id: Optional[str] = ""
    article_name: Optional[str] = ""

class VillageFetchResponse(BaseModel):
    id: UUID
    village_id: UUID
    village_name: Optional[str] = None
    taluka_name: Optional[str] = None
    district_name: Optional[str] = None
    year: int
    status: str
    survey_range_start: int = 1
    survey_range_end: int = 100
    current_search_value: Optional[str] = None
    processed_search_count: int
    records_found: int
    unique_records_saved: int
    duplicates_skipped: int
    truncated_searches_count: int = 0
    errors_count: int
    last_error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True
