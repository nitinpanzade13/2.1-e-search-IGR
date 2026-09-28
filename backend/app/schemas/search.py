from pydantic import BaseModel
from typing import Optional, List, Any
from uuid import UUID
from datetime import datetime
from app.schemas.registration import RegistrationResponse

class SearchCreateRequest(BaseModel):
    year: int
    district_id: int
    taluka_id: int
    village_id: int
    survey_query: Optional[str] = None
    article_id: Optional[str] = None
    article_name: Optional[str] = None

class SearchCreateResponse(BaseModel):
    job_id: UUID
    status: str

class SearchJobResponse(BaseModel):
    job_id: UUID
    status: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result_count: int = 0
    truncated: bool = False
    error: Optional[str] = None

    class Config:
        from_attributes = True

class SearchResultResponse(BaseModel):
    items: List[RegistrationResponse]
    page: int
    page_size: int
    total: int
    truncated: bool = False
    provenance_unavailable: bool = False

    class Config:
        from_attributes = True
