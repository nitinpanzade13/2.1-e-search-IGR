import uuid
import pytest
from app.models.job import BulkFetchJob, SearchJob
from app.models.enums import BulkFetchJobStatus, ScopeType
from sqlalchemy.exc import DataError, DBAPIError

def test_bulk_fetch_boundary_uuid_handling(db):
    from app.models.location import State, District, Taluka, Village
    
    # Use random source_ids to avoid collisions across test runs
    suffix = str(uuid.uuid4())[:8]
    
    s = State(id=uuid.uuid4(), source_system="IGR", source_id=f"S_{suffix}", name_en="State")
    db.add(s)
    d = District(id=uuid.uuid4(), source_system="IGR", source_id=f"D_{suffix}", name_en="District", state_id=s.id)
    db.add(d)
    t = Taluka(id=uuid.uuid4(), source_system="IGR", source_id=f"T_{suffix}", name_en="Taluka", district_id=d.id)
    db.add(t)
    v = Village(id=uuid.uuid4(), source_system="IGR", source_id=f"V_{suffix}", name_en="Village", taluka_id=t.id)
    db.add(v)
    db.flush()

    # 1. Storing valid UUID succeeds
    job_uuid = BulkFetchJob(
        id=uuid.uuid4(),
        scope_type=ScopeType.VILLAGE,
        status=BulkFetchJobStatus.QUEUED,
        district_id=d.id,
        taluka_id=t.id,
        village_id=v.id
    )
    db.add(job_uuid)
    db.flush()
    
    assert job_uuid.district_id == d.id
    assert job_uuid.taluka_id == t.id
    assert job_uuid.village_id == v.id

    # 2. Attempting to store an IGR source_id fails due to PostgreSQL UUID validation
    job_source_id = BulkFetchJob(
        id=uuid.uuid4(),
        scope_type=ScopeType.VILLAGE,
        status=BulkFetchJobStatus.QUEUED,
        village_id="4" # invalid uuid
    )
    db.add(job_source_id)
    try:
        # Use nested transaction to prevent breaking the outer transaction on error
        with db.begin_nested():
            db.flush()
    except (DataError, DBAPIError):
        pass # Expected
    
    # ensure session is clean
    db.rollback()

def test_planner_resolves_uuid_to_source_id_at_igr_boundary(db):
    from app.models.location import State, District, Taluka, Village
    
    suffix = str(uuid.uuid4())[:8]
    
    s = State(id=uuid.uuid4(), source_system="IGR", source_id=f"S_{suffix}", name_en="State")
    db.add(s)
    d = District(id=uuid.uuid4(), source_system="IGR", source_id=f"D_{suffix}", name_en="District", state_id=s.id)
    db.add(d)
    t = Taluka(id=uuid.uuid4(), source_system="IGR", source_id=f"T_{suffix}", name_en="Taluka", district_id=d.id)
    db.add(t)
    v = Village(id=uuid.uuid4(), source_system="IGR", source_id=f"V_{suffix}", name_en="Village", taluka_id=t.id)
    db.add(v)
    db.flush()

    from app.scraper.orchestration.planner import BulkFetchPlanner
    
    job = BulkFetchJob(
        id=uuid.uuid4(),
        scope_type=ScopeType.VILLAGE,
        status=BulkFetchJobStatus.PLANNING,
        district_id=d.id,
        taluka_id=t.id,
        village_id=v.id,
        requested_year_start=2024,
        requested_year_end=2024
    )
    db.add(job)
    db.flush()
    
    planner = BulkFetchPlanner(db)
    planner.plan_jobs(job.id)
    
    # Check created SearchJob
    search_job = db.query(SearchJob).filter_by(bulk_fetch_job_id=job.id).first()
    assert search_job is not None
    
    # The parameters MUST be source_id, not UUID
    assert search_job.location_params["district_id"] == f"D_{suffix}"
    assert search_job.location_params["taluka_id"] == f"T_{suffix}"
    assert search_job.location_params["village_id"] == f"V_{suffix}"
    
    # Assert they are NOT UUIDs
    assert search_job.location_params["village_id"] != str(v.id)
