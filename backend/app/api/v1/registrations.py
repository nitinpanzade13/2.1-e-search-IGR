from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID

from app.api.dependencies import get_db
from app.models.registration import Registration, Party, Property
from app.schemas.registration import RegistrationResponse, PartyResponse, PropertyResponse

router = APIRouter()

@router.get("/{registration_id}", response_model=RegistrationResponse)
def get_registration(registration_id: UUID, db: Session = Depends(get_db)):
    reg = db.query(Registration).filter(Registration.id == registration_id).first()
    if not reg:
        raise HTTPException(status_code=404, detail="Registration not found")
    return reg

@router.get("/{registration_id}/parties", response_model=List[PartyResponse])
def get_registration_parties(registration_id: UUID, db: Session = Depends(get_db)):
    parties = db.query(Party).filter(Party.registration_id == registration_id).order_by(Party.party_order).all()
    return parties

@router.get("/{registration_id}/properties", response_model=List[PropertyResponse])
def get_registration_properties(registration_id: UUID, db: Session = Depends(get_db)):
    properties = db.query(Property).filter(Property.registration_id == registration_id).order_by(Property.property_order).all()
    return properties
