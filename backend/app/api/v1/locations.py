from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.api.dependencies import get_db
from app.models.location import State, District, Taluka, Village
from app.schemas.location import DistrictResponse, TalukaResponse, VillageResponse

from uuid import UUID

router = APIRouter()

@router.get("/districts", response_model=List[DistrictResponse])
def get_districts(db: Session = Depends(get_db)):
    districts = db.query(District).filter(District.is_active == True).order_by(District.name_en).all()
    return districts

@router.get("/districts/{district_id}/talukas", response_model=List[TalukaResponse])
def get_talukas(district_id: UUID, db: Session = Depends(get_db)):
    district = db.query(District).filter(District.id == district_id, District.source_system == "IGR_MAHARASHTRA").first()
    if not district:
        raise HTTPException(status_code=404, detail="District not found")
    talukas = db.query(Taluka).filter(Taluka.district_id == district.id, Taluka.is_active == True).order_by(Taluka.name_en).all()
    return talukas

@router.get("/talukas/{taluka_id}/villages", response_model=List[VillageResponse])
def get_villages(taluka_id: UUID, db: Session = Depends(get_db)):
    taluka = db.query(Taluka).filter(Taluka.id == taluka_id, Taluka.source_system == "IGR_MAHARASHTRA").first()
    if not taluka:
        raise HTTPException(status_code=404, detail="Taluka not found")
    villages = db.query(Village).filter(Village.taluka_id == taluka.id, Village.is_active == True).order_by(Village.name_en).all()
    return villages
