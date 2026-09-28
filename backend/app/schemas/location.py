from pydantic import BaseModel
from typing import Optional
from uuid import UUID

class StateResponse(BaseModel):
    id: UUID
    name_en: str
    name_mr: Optional[str] = None
    source_id: str

    class Config:
        from_attributes = True

class DistrictResponse(BaseModel):
    id: UUID
    name_en: str
    name_mr: Optional[str] = None
    source_id: str
    state_id: UUID

    class Config:
        from_attributes = True

class TalukaResponse(BaseModel):
    id: UUID
    name_en: str
    name_mr: Optional[str] = None
    source_id: str
    district_id: UUID

    class Config:
        from_attributes = True

class VillageResponse(BaseModel):
    id: UUID
    name_en: str
    name_mr: Optional[str] = None
    source_id: str
    taluka_id: UUID

    class Config:
        from_attributes = True
