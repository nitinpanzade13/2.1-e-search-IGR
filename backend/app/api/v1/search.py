import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Query
from sqlalchemy.orm import Session
from typing import Optional
from decimal import Decimal

from app.api.dependencies import get_db, get_search_worker
from app.core.config import settings
from app.models.job import SearchJob
from app.models.enums import SearchJobStatus
from app.models.registration import Registration
from app.models.office import Office
from app.models.location import District
from app.schemas.search import SearchCreateRequest, SearchCreateResponse, SearchJobResponse, SearchResultResponse
from app.schemas.registration import RegistrationResponse, PartyResponse, PropertyResponse
from app.scraper.worker.search_worker import SearchWorker

router = APIRouter()



def run_worker_bg(job_id: uuid.UUID, db: Session, worker: SearchWorker):
    # The worker handles its own try/except and updates the DB state
    try:
        worker.execute(job_id)
    finally:
        # FastAPI BackgroundTasks does not auto-close the injected DB session if we pass it directly
        # Wait, if we use Depends(get_db) in the endpoint, FastAPI closes it after the request completes.
        # But BackgroundTasks run AFTER the request completes! So the session will be closed!
        # We need a new session for the background task.
        pass

def run_worker_isolated(job_id: uuid.UUID):
    from app.core.database import SessionLocal
    from app.api.dependencies import get_search_worker
    
    db = SessionLocal()
    try:
        worker = get_search_worker(db)
        worker.execute(job_id)
    except Exception as e:
        import traceback
        traceback.print_exc()
    finally:
        db.close()


@router.post("", response_model=SearchCreateResponse)
def create_search(
    request: SearchCreateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    # In Demo Mode, we just create a job and mark it completed
    demo_mode = getattr(settings, "SCRAPER_TEST_MODE", False)
    
    loc_params = {
        "district_id": str(request.district_id),
        "taluka_id": str(request.taluka_id),
        "village_id": str(request.village_id),
    }
    if request.article_id:
        loc_params["article_id"] = str(request.article_id)
    if request.article_name:
        loc_params["article_name"] = str(request.article_name)

    job = SearchJob(
        year=request.year,
        location_params=loc_params,
        survey_prefix=request.survey_query,
        status=SearchJobStatus.COMPLETED if demo_mode else SearchJobStatus.QUEUED
    )
    
    if demo_mode:
        job.started_at = datetime.now(timezone.utc)
        job.completed_at = datetime.now(timezone.utc)
        job.retrieved_count = 0
        job.requested_count = 0
        
    db.add(job)
    db.commit()
    db.refresh(job)

    if not demo_mode:
        # Trigger background task with a fresh DB session internally
        background_tasks.add_task(run_worker_isolated, job.id)

    return {"job_id": job.id, "status": job.status.name}

@router.get("/{job_id}", response_model=SearchJobResponse)
def get_search_job(job_id: uuid.UUID, db: Session = Depends(get_db)):
    job = db.query(SearchJob).filter(SearchJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    return {
        "job_id": job.id,
        "status": job.status.name,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "completed_at": job.completed_at,
        "result_count": job.retrieved_count or 0,
        "truncated": job.truncated,
        "error": job.last_error
    }

@router.get("/{job_id}/results", response_model=SearchResultResponse)
def get_search_results(
    job_id: uuid.UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    job = db.query(SearchJob).filter(SearchJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    from app.models.job import SearchJobRegistration
    
    query = db.query(Registration).join(
        SearchJobRegistration,
        SearchJobRegistration.registration_id == Registration.id
    ).filter(
        SearchJobRegistration.search_job_id == job.id
    )
    
    # Year consistency filter
    query = query.filter(Registration.year == job.year)
    
    total = query.count()
    items = query.order_by(Registration.doc_no).offset((page - 1) * page_size).limit(page_size).all()
    
    # Handle historical SearchJobs that have no provenance links
    provenance_unavailable = False
    if total == 0 and job.status == SearchJobStatus.COMPLETED and job.retrieved_count and job.retrieved_count > 0:
        provenance_unavailable = True
    
    return {
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "truncated": job.truncated,
        "provenance_unavailable": provenance_unavailable
    }
