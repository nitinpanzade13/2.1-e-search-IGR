from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import date, datetime
from decimal import Decimal

class PartyResponse(BaseModel):
    id: UUID
    role: str
    party_order: int
    name: Optional[str] = None
    age: Optional[int] = None
    address: Optional[str] = None
    raw_text: Optional[str] = None

    class Config:
        from_attributes = True

class PropertyResponse(BaseModel):
    id: UUID
    property_order: int
    survey_no: Optional[str] = None
    cts_no: Optional[str] = None
    area_sqm: Optional[Decimal] = None
    area_value: Optional[Decimal] = None
    area_unit: Optional[str] = None
    description_raw: Optional[str] = None
    area_raw: Optional[str] = None

    class Config:
        from_attributes = True

class RegistrationResponse(BaseModel):
    id: UUID
    year: int
    doc_no: str
    doc_type: str
    office_id: Optional[UUID] = None
    office_name_raw: Optional[str] = None
    execution_date: Optional[date] = None
    registration_date: Optional[date] = None
    consideration_amount: Optional[Decimal] = None
    market_value: Optional[Decimal] = None
    stamp_duty: Optional[Decimal] = None
    registration_fee: Optional[Decimal] = None
    indexii_url: Optional[str] = None
    processing_status: Optional[str] = None
    seller_names_raw: Optional[str] = None
    buyer_names_raw: Optional[str] = None
    
    parties: List[PartyResponse] = []
    properties: List[PropertyResponse] = []

    class Config:
        from_attributes = True
