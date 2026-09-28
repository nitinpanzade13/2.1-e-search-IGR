from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api.dependencies import get_db
from app.models.registration import Registration, Party, Property
from app.models.job import PdfTask, SearchJob, BulkFetchJob
from app.models.artifact import Artifact
from app.models.enums import ProcessingStatus, PdfTaskStatus
from app.schemas.admin_stats import AdminStatsResponse

router = APIRouter()

@router.get("/stats", response_model=AdminStatsResponse)
def get_admin_stats(db: Session = Depends(get_db)):
    # Registrations
    reg_total = db.query(Registration).count()
    reg_by_status = dict(
        db.query(Registration.processing_status, func.count(Registration.id))
        .group_by(Registration.processing_status)
        .all()
    )
    # Ensure all enum values are strings
    reg_by_status_str = {
        (status.name if hasattr(status, 'name') else str(status)): count 
        for status, count in reg_by_status.items() if status is not None
    }
    
    # PDF Tasks
    pdf_total = db.query(PdfTask).count()
    pdf_by_status = dict(
        db.query(PdfTask.status, func.count(PdfTask.id))
        .group_by(PdfTask.status)
        .all()
    )
    pdf_by_status_str = {
        (status.name if hasattr(status, 'name') else str(status)): count 
        for status, count in pdf_by_status.items() if status is not None
    }
    
    # Simple counts
    parties_total = db.query(Party).count()
    properties_total = db.query(Property).count()
    artifacts_total = db.query(Artifact).count()
    
    # Search Jobs
    search_jobs_total = db.query(SearchJob).count()
    sj_by_status = dict(
        db.query(SearchJob.status, func.count(SearchJob.id))
        .group_by(SearchJob.status)
        .all()
    )
    sj_by_status_str = {
        (status.name if hasattr(status, 'name') else str(status)): count 
        for status, count in sj_by_status.items() if status is not None
    }

    # Bulk Fetch Jobs
    bulk_fetch_jobs_total = db.query(BulkFetchJob).count()
    bfj_by_status = dict(
        db.query(BulkFetchJob.status, func.count(BulkFetchJob.id))
        .group_by(BulkFetchJob.status)
        .all()
    )
    bfj_by_status_str = {
        (status.name if hasattr(status, 'name') else str(status)): count 
        for status, count in bfj_by_status.items() if status is not None
    }
    
    stats = {
        "registrations": {
            "total": reg_total,
            "by_status": reg_by_status_str
        },
        "pdf_tasks": {
            "total": pdf_total,
            "by_status": pdf_by_status_str
        },
        "parties": {"total": parties_total},
        "properties": {"total": properties_total},
        "artifacts": {"total": artifacts_total},
        "search_jobs": {
            "total": search_jobs_total,
            "by_status": sj_by_status_str
        },
        "bulk_fetch_jobs": {
            "total": bulk_fetch_jobs_total,
            "by_status": bfj_by_status_str
        },
        "worker_health": []
    }
    
    from app.models.system import WorkerHealth
    import datetime
    workers = db.query(WorkerHealth).all()
    for w in workers:
        time_since = 999
        if w.last_heartbeat:
            time_since = (datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None) - w.last_heartbeat.replace(tzinfo=None)).total_seconds()
        is_online = w.is_online and time_since < 60
        stats["worker_health"].append({
            "worker_type": w.worker_type,
            "is_online": is_online,
            "last_heartbeat": w.last_heartbeat.isoformat() if w.last_heartbeat else None,
            "current_job_id": w.current_job_id
        })
        
    return stats
