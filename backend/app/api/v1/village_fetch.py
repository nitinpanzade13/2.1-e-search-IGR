from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.api.dependencies import get_db
from app.models.location import District, Taluka, Village
from app.models.village_fetch import VillageFetch, VillageFetchStatus
from app.models.record_detail import RecordDetail
from app.schemas.village_fetch import VillageFetchCreateRequest, VillageFetchResponse
from app.schemas.record_detail import RecordDetailListResponse, RecordDetailResponse
from app.scraper.service.village_fetch_service import VillageFetchService
from app.core.config import settings

router = APIRouter(prefix="/village-fetches", tags=["Village Fetch"])

def run_fetch_background(fetch_id: UUID, search_values: Optional[List[str]] = None):
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"[BackgroundTask] Starting village fetch background task for fetch_id: {fetch_id}")
    
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        service = VillageFetchService(db)
        logger.info(f"[BackgroundTask] Executing fetch with {len(search_values) if search_values else 'default'} search values")
        service.execute_fetch(fetch_id, search_values)
        logger.info(f"[BackgroundTask] Village fetch {fetch_id} completed successfully")
    except Exception as e:
        logger.error(f"[BackgroundTask] Background fetch error for {fetch_id}: {e}", exc_info=True)
    finally:
        db.close()
        logger.info(f"[BackgroundTask] Background task for fetch_id: {fetch_id} finished")

@router.post("", response_model=VillageFetchResponse, status_code=201)
def create_village_fetch(
    req: VillageFetchCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    service = VillageFetchService(db)
    try:
        district, taluka, village = service.validate_hierarchy(req.district_id, req.taluka_id, req.village_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    fetch_run = service.create_fetch(
        district_id=req.district_id,
        taluka_id=req.taluka_id,
        village_id=req.village_id,
        year=req.year,
        search_query=req.search_query,
        survey_range_start=req.survey_range_start or 1,
        survey_range_end=req.survey_range_end or 100
    )

    if req.search_values:
        search_vals = req.search_values
    elif req.search_query:
        search_vals = [req.search_query]
    else:
        start_n = req.survey_range_start or 1
        end_n = req.survey_range_end or 100
        search_vals = [str(i) for i in range(start_n, end_n + 1)]
    
    # In test mode or normal mode, trigger background task
    demo_mode = getattr(settings, "SCRAPER_TEST_MODE", False)
    if demo_mode:
        fetch_run.status = VillageFetchStatus.COMPLETED.value
        db.commit()
    else:
        background_tasks.add_task(run_fetch_background, fetch_run.id, search_vals)

    res = VillageFetchResponse.model_validate(fetch_run)
    res.district_name = district.name_en
    res.taluka_name = taluka.name_en
    res.village_name = village.name_en
    return res

@router.get("", response_model=List[VillageFetchResponse])
def list_village_fetches(
    village_id: Optional[UUID] = None,
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    query = db.query(VillageFetch)
    if village_id:
        query = query.filter(VillageFetch.village_id == village_id)
    fetches = query.order_by(VillageFetch.created_at.desc()).offset(skip).limit(limit).all()
    results = []
    for f in fetches:
        res = VillageFetchResponse.model_validate(f)
        v = db.query(Village).filter_by(id=f.village_id).first()
        t = db.query(Taluka).filter_by(id=v.taluka_id).first() if v else None
        d = db.query(District).filter_by(id=t.district_id).first() if t else None
        res.village_name = v.name_en if v else None
        res.taluka_name = t.name_en if t else None
        res.district_name = d.name_en if d else None
        results.append(res)
    return results

@router.get("/{fetch_id}", response_model=VillageFetchResponse)
def get_village_fetch(fetch_id: UUID, db: Session = Depends(get_db)):
    fetch_run = db.query(VillageFetch).filter_by(id=fetch_id).first()
    if not fetch_run:
        raise HTTPException(status_code=404, detail="VillageFetch not found")

    village = db.query(Village).filter_by(id=fetch_run.village_id).first()
    taluka = db.query(Taluka).filter_by(id=village.taluka_id).first() if village else None
    district = db.query(District).filter_by(id=taluka.district_id).first() if taluka else None

    res = VillageFetchResponse.model_validate(fetch_run)
    res.village_name = village.name_en if village else None
    res.taluka_name = taluka.name_en if taluka else None
    res.district_name = district.name_en if district else None
    return res

@router.get("/{fetch_id}/records", response_model=RecordDetailListResponse)
def get_village_fetch_records(
    fetch_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    q: Optional[str] = None,
    db: Session = Depends(get_db)
):
    fetch_run = db.query(VillageFetch).filter_by(id=fetch_id).first()
    if not fetch_run:
        raise HTTPException(status_code=404, detail="VillageFetch not found")

    query = db.query(RecordDetail).filter(
        RecordDetail.village_id == fetch_run.village_id,
        RecordDetail.year == fetch_run.year
    )

    if q:
        search_filter = f"%{q.strip()}%"
        from sqlalchemy import or_
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

@router.post("/{fetch_id}/pause")
def pause_village_fetch(fetch_id: UUID, db: Session = Depends(get_db)):
    service = VillageFetchService(db)
    if not service.pause_fetch(fetch_id):
        raise HTTPException(status_code=400, detail="Cannot pause fetch in its current state")
    return {"status": "PAUSED", "message": "Fetch paused"}

@router.post("/{fetch_id}/resume")
def resume_village_fetch(fetch_id: UUID, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    service = VillageFetchService(db)
    if not service.resume_fetch(fetch_id):
        raise HTTPException(status_code=400, detail="Cannot resume fetch in its current state")
    background_tasks.add_task(run_fetch_background, fetch_id, None)
    return {"status": "RUNNING", "message": "Fetch resumed"}

@router.post("/{fetch_id}/cancel")
def cancel_village_fetch(fetch_id: UUID, db: Session = Depends(get_db)):
    service = VillageFetchService(db)
    if not service.cancel_fetch(fetch_id):
        raise HTTPException(status_code=400, detail="Cannot cancel fetch in its current state")
    return {"status": "CANCELLED", "message": "Fetch cancelled"}
