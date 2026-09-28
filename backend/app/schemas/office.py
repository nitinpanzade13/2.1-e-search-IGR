from pydantic import BaseModel
from typing import Optional
from uuid import UUID

class OfficeResponse(BaseModel):
    id: UUID
    district_id: Optional[UUID] = None
    name: str
    name_mr: Optional[str] = None
    source_id: str

    class Config:
        from_attributes = True
