from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from uuid import UUID

class RecordDetailResponse(BaseModel):
    id: UUID
    village_id: UUID
    year: int
    sr_no: Optional[str] = None
    doc_no: str
    doc_type: Optional[str] = None
    office: Optional[str] = None
    date: Optional[str] = None
    seller: Optional[str] = None
    buyer: Optional[str] = None
    other_info: Optional[str] = None
    indexii_url: Optional[str] = None
    source_query: Optional[str] = None
    is_truncated: bool = False
    reported_count: Optional[int] = None
    fetched_at: datetime

    class Config:
        from_attributes = True

class RecordDetailListResponse(BaseModel):
    items: List[RecordDetailResponse]
    total: int
    page: int
    page_size: int
