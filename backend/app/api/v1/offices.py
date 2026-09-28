from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.api.dependencies import get_db
from app.models.office import Office
from app.schemas.office import OfficeResponse

router = APIRouter()

@router.get("", response_model=List[OfficeResponse])
def get_offices(
    district_id: Optional[UUID] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(Office).filter(Office.is_active == True)
    if district_id:
        query = query.filter(Office.district_id == district_id)
        
    offices = query.order_by(Office.name).all()
    return offices
