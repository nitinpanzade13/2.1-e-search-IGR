from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, distinct
from typing import Optional, Dict, Any

from app.api.dependencies import get_db
from app.models.location import Village
from app.models.record_detail import RecordDetail
from app.models.village_fetch import VillageFetch
from app.schemas.record_detail import RecordDetailListResponse, RecordDetailResponse

router = APIRouter(tags=["Records"])

@router.get("/records", response_model=RecordDetailListResponse)
def list_records(
    village_id: Optional[UUID] = None,
    year: Optional[int] = None,
    q: Optional[str] = None,
    doc_no: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    query = db.query(RecordDetail)

    if village_id is not None:
        query = query.filter(RecordDetail.village_id == village_id)

    if year is not None:
        query = query.filter(RecordDetail.year == year)

    if doc_no:
        query = query.filter(RecordDetail.doc_no.ilike(f"%{doc_no.strip()}%"))

    if q:
        search_filter = f"%{q.strip()}%"
        query = query.filter(
            or_(
                RecordDetail.doc_no.ilike(search_filter),
                RecordDetail.seller.ilike(search_filter),
                RecordDetail.buyer.ilike(search_filter),
                RecordDetail.other_info.ilike(search_filter),
                RecordDetail.doc_type.ilike(search_filter),
                RecordDetail.office.ilike(search_filter)
            )
        )

    total = query.count()
    items = query.order_by(RecordDetail.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    return RecordDetailListResponse(
        items=[RecordDetailResponse.model_validate(it) for it in items],
        total=total,
        page=page,
        page_size=page_size
    )

@router.get("/records/stats/summary")
def get_records_summary(db: Session = Depends(get_db)) -> Dict[str, Any]:
    total_records = db.query(func.count(RecordDetail.id)).scalar() or 0
    total_fetches = db.query(func.count(VillageFetch.id)).scalar() or 0
    villages_covered = db.query(func.count(distinct(RecordDetail.village_id))).scalar() or 0

    return {
        "total_records": total_records,
        "total_village_fetches": total_fetches,
        "villages_covered": villages_covered,
    }

@router.get("/records/{record_id}", response_model=RecordDetailResponse)
def get_record(record_id: UUID, db: Session = Depends(get_db)):
    rec = db.query(RecordDetail).filter_by(id=record_id).first()
    if not rec:
        raise HTTPException(status_code=404, detail="Record not found")
    return RecordDetailResponse.model_validate(rec)

@router.get("/villages/{village_id}/records", response_model=RecordDetailListResponse)
def get_village_records(
    village_id: UUID,
    year: Optional[int] = None,
    q: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    village = db.query(Village).filter_by(id=village_id).first()
    if not village:
        raise HTTPException(status_code=404, detail="Village not found")

    return list_records(
        village_id=village_id,
        year=year,
        q=q,
        doc_no=None,
        page=page,
        page_size=page_size,
        db=db
    )
