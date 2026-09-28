from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
import datetime

from app.api.dependencies import get_db
from app.models.job import BulkFetchJob, SearchJob
from app.models.enums import BulkFetchJobStatus
from app.schemas.admin_bulk import BulkFetchCreateRequest, BulkFetchJobResponse, SearchJobChildResponse
from app.scraper.orchestration.planner import BulkFetchPlanner
from app.scraper.orchestration.service import BulkFetchService

router = APIRouter(prefix="/admin/bulk-fetch", tags=["Admin Bulk Fetch"])

def run_planner(job_id: UUID):
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        planner = BulkFetchPlanner(db)
        planner.plan_jobs(job_id)
    finally:
        db.close()

@router.post("", response_model=BulkFetchJobResponse)
def create_bulk_fetch(req: BulkFetchCreateRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    if req.year_start > req.year_end:
        raise HTTPException(status_code=400, detail="year_start must be <= year_end")

    job = BulkFetchJob(
        scope_type=req.scope_type,
        state_id=req.state_id,
        district_id=req.district_id,
        taluka_id=req.taluka_id,
        village_id=req.village_id,
        requested_year_start=req.year_start,
        requested_year_end=req.year_end,
        status=BulkFetchJobStatus.PLANNING,
        started_at=datetime.datetime.now(datetime.timezone.utc)
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # Run planner in background so API is fast
    background_tasks.add_task(run_planner, job.id)
    
    from app.models.system import WorkerHealth
    health = db.query(WorkerHealth).filter_by(worker_type="SEARCH").first()
    is_worker_online = False
    if health and health.is_online and health.last_heartbeat:
        time_since_heartbeat = (datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - health.last_heartbeat.replace(tzinfo=None)).total_seconds()
        if time_since_heartbeat < 60:
            is_worker_online = True
            
    if not is_worker_online:
        job.error_message = "Bulk job created, but no Search Worker is currently available."
        db.commit()

    return job

@router.get("", response_model=List[BulkFetchJobResponse])
def list_bulk_fetches(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    jobs = db.query(BulkFetchJob).order_by(BulkFetchJob.created_at.desc()).offset(skip).limit(limit).all()
    # To keep list fast, we won't aggregate on the fly for all, but maybe just return as is
    # Normalize legacy rows that might have NULL for newly added unit fields
    for job in jobs:
        job.total_units = job.total_units or 0
        job.queued_units = job.queued_units or 0
        job.running_units = job.running_units or 0
        job.completed_units = job.completed_units or 0
        job.failed_units = job.failed_units or 0
        job.truncated_units = job.truncated_units or 0
        job.rate_limited_units = job.rate_limited_units or 0
        job.paused_units = job.paused_units or 0
        job.total_records_reported = job.total_records_reported or 0
        job.total_records_retrieved = job.total_records_retrieved or 0
    return jobs

@router.get("/{job_id}", response_model=BulkFetchJobResponse)
def get_bulk_fetch(job_id: UUID, db: Session = Depends(get_db)):
    svc = BulkFetchService(db)
    svc.aggregate_progress(job_id) # Update stats before returning
    job = db.query(BulkFetchJob).get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    from sqlalchemy import func
    from app.models.job import PdfTask, SearchJobRegistration
    
    pdf_query = (
        db.query(PdfTask.status, func.count(func.distinct(PdfTask.id)))
        .select_from(PdfTask)
        .join(SearchJobRegistration, SearchJobRegistration.registration_id == PdfTask.registration_id)
        .join(SearchJob, SearchJob.id == SearchJobRegistration.search_job_id)
        .filter(SearchJob.bulk_fetch_job_id == job_id)
        .group_by(PdfTask.status)
        .all()
    )
    
    pdf_stats_dict = {status.name if hasattr(status, 'name') else str(status): count for status, count in pdf_query}
    pdf_stats_dict["total"] = sum(pdf_stats_dict.values())
    
    from app.models.location import District, Taluka, Village
    
    district_name = None
    district_source_id = None
    if job.district_id:
        d = db.query(District).filter_by(id=job.district_id).first()
        if d: 
            district_name = d.name_en
            district_source_id = d.source_id
            
    taluka_name = None
    taluka_source_id = None
    if job.taluka_id:
        t = db.query(Taluka).filter_by(id=job.taluka_id).first()
        if t: 
            taluka_name = t.name_en
            taluka_source_id = t.source_id
            
    village_name = None
    village_source_id = None
    if job.village_id:
        v = db.query(Village).filter_by(id=job.village_id).first()
        if v: 
            village_name = v.name_en
            village_source_id = v.source_id
    
    # Create dict that matches schema
    response_data = {c.name: getattr(job, c.name) for c in job.__table__.columns}
    response_data["pdf_stats"] = pdf_stats_dict
    response_data["district_name"] = district_name
    response_data["district_source_id"] = district_source_id
    response_data["taluka_name"] = taluka_name
    response_data["taluka_source_id"] = taluka_source_id
    response_data["village_name"] = village_name
    response_data["village_source_id"] = village_source_id
    
    return response_data


@router.get("/{job_id}/jobs", response_model=List[SearchJobChildResponse])
def get_bulk_fetch_jobs(job_id: UUID, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    jobs = db.query(SearchJob).filter(SearchJob.bulk_fetch_job_id == job_id).order_by(SearchJob.created_at.desc()).offset(skip).limit(limit).all()
    return jobs

@router.post("/{job_id}/pause")
def pause_bulk_fetch(job_id: UUID, db: Session = Depends(get_db)):
    svc = BulkFetchService(db)
    success = svc.pause_job(job_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot pause job in its current state")
    return {"message": "Job paused"}

@router.post("/{job_id}/resume")
def resume_bulk_fetch(job_id: UUID, db: Session = Depends(get_db)):
    svc = BulkFetchService(db)
    success = svc.resume_job(job_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot resume job in its current state")
    return {"message": "Job resumed"}

@router.post("/{job_id}/cancel")
def cancel_bulk_fetch(job_id: UUID, db: Session = Depends(get_db)):
    svc = BulkFetchService(db)
    success = svc.cancel_job(job_id)
    if not success:
        raise HTTPException(status_code=400, detail="Cannot cancel job in its current state")
    return {"message": "Job cancelled"}
