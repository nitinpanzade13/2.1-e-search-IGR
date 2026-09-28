import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.core.config import settings
from app.db.base import Base
from app.models.enums import ScopeType, BulkFetchJobStatus
from app.models.job import BulkFetchJob, SearchJob
from app.scraper.orchestration.planner import BulkFetchPlanner
from app.scraper.orchestration.service import BulkFetchService
from app.models.location import District, Taluka, Village

# The db fixture is now imported from conftest.py


client = TestClient(app)

def test_bulk_fetch_planning_district(db):
    # Setup test locations
    from app.models.location import State, District
    s = db.query(State).filter_by(source_id="TEST_MH").first()
    if not s:
        s = State(id=uuid4(), source_id="TEST_MH", name_en="Maharashtra")
        db.add(s)
        db.commit()
    
    d = db.query(District).filter_by(source_id="TEST_23").first()
    if not d:
        d = District(id=uuid4(), source_id="TEST_23", name_en="Test Pune", state_id=s.id)
        db.add(d)
        db.commit()
    
    # Need to add a Taluka and Village to expand properly
    t = db.query(Taluka).filter_by(source_id="T1").first()
    if not t:
        t = Taluka(id=uuid4(), source_id="T1", district_id=d.id, name_en="Test Taluka")
        db.add(t)
        db.commit()
        
    v = db.query(Village).filter_by(source_id="V1").first()
    if not v:
        v = Village(id=uuid4(), source_id="V1", taluka_id=t.id, name_en="Test Village")
        db.add(v)
        db.commit()

    # Create Bulk Job
    job = BulkFetchJob(
        scope_type=ScopeType.DISTRICT,
        district_id=str(d.id),
        requested_year_start=2025,
        requested_year_end=2026,
        status=BulkFetchJobStatus.PLANNING
    )
    db.add(job)
    db.commit()
    
    # Run Planner
    planner = BulkFetchPlanner(db)
    planner.plan_jobs(job.id)
    
    db.refresh(job)
    assert job.status == BulkFetchJobStatus.RUNNING
    
    jobs = db.query(SearchJob).filter_by(bulk_fetch_job_id=job.id).all()
    assert jobs[0].year in [2025, 2026]
    assert jobs[0].location_params["district_id"] == "TEST_23"
    assert jobs[0].location_params["taluka_id"] == "T1"
    assert jobs[0].location_params["village_id"] == "V1"

def test_bulk_fetch_api_create(db):
    from app.models.location import State, District
    s = db.query(State).filter_by(source_id="S_API").first()
    if not s:
        s = State(id=uuid4(), source_system="IGR", source_id="S_API", name_en="State")
        db.add(s)
        db.commit()
    d = db.query(District).filter_by(source_id="D_API").first()
    if not d:
        d = District(id=uuid4(), source_system="IGR", source_id="D_API", name_en="District", state_id=s.id)
        db.add(d)
        db.commit()

    payload = {
        "scope_type": "DISTRICT",
        "district_id": str(d.id),
        "year_start": 2026,
        "year_end": 2026
    }
    response = client.post("/api/v1/admin/bulk-fetch", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["scope_type"] == "DISTRICT"
    assert data["status"] == "PLANNING"

def test_bulk_fetch_empty_aggregates(db):
    from app.models.location import State, District
    s = db.query(State).filter_by(source_id="S_EMP").first()
    if not s:
        s = State(id=uuid4(), source_system="IGR", source_id="S_EMP", name_en="State")
        db.add(s)
        db.commit()
    d = db.query(District).filter_by(source_id="D_EMP").first()
    if not d:
        d = District(id=uuid4(), source_system="IGR", source_id="D_EMP", name_en="District", state_id=s.id)
        db.add(d)
        db.commit()
        
    # Create a bulk job with no child SearchJobs yet
    job = BulkFetchJob(
        scope_type=ScopeType.DISTRICT,
        district_id=d.id,
        requested_year_start=2026,
        requested_year_end=2026,
        status=BulkFetchJobStatus.QUEUED
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    # By default, SQLAlchemy might set some columns to None if fetched without defaults triggering in legacy ways, 
    # but we can explicitly test the API response
    response = client.get(f"/api/v1/admin/bulk-fetch/{job.id}")
    assert response.status_code == 200
    data = response.json()
    
    assert data["rate_limited_units"] == 0
    assert data["paused_units"] == 0
    assert data["total_units"] == 0
    assert data["completed_units"] == 0

    response_list = client.get(f"/api/v1/admin/bulk-fetch")
    assert response_list.status_code == 200
    list_data = response_list.json()
    # Find our job
    job_in_list = next((j for j in list_data if j["id"] == str(job.id)), None)
    assert job_in_list is not None
    assert job_in_list["rate_limited_units"] == 0
    assert job_in_list["paused_units"] == 0
    assert job_in_list["total_units"] == 0
    assert job_in_list["completed_units"] == 0

def test_bulk_fetch_detail_location_names(db):
    from app.models.location import State, District
    
    s = db.query(State).filter_by(source_id="S_DETAIL").first()
    if not s:
        s = State(id=uuid4(), source_system="IGR_MAHARASHTRA", source_id="S_DETAIL", name_en="State Detail")
        db.add(s)
        db.commit()
    
    d = db.query(District).filter_by(source_id="D_DETAIL").first()
    if not d:
        d = District(id=uuid4(), source_system="IGR_MAHARASHTRA", source_id="D_DETAIL", name_en="Test District Detail", state_id=s.id)
        db.add(d)
        db.commit()
    
    job = BulkFetchJob(
        scope_type=ScopeType.DISTRICT,
        district_id=d.id,
        requested_year_start=2026,
        requested_year_end=2026,
        status=BulkFetchJobStatus.RUNNING
    )
    db.add(job)
    db.commit()

    response = client.get(f"/api/v1/admin/bulk-fetch/{job.id}")
    if response.status_code != 200:
        print(response.json())
    assert response.status_code == 200
    data = response.json()
    assert data["district_name"] == "Test District Detail"

def test_bulk_fetch_pause_transition(db):
    job = BulkFetchJob(scope_type=ScopeType.VILLAGE, status=BulkFetchJobStatus.RUNNING)
    db.add(job)
    db.commit()
    
    res = client.post(f"/api/v1/admin/bulk-fetch/{job.id}/pause")
    assert res.status_code == 200
    db.refresh(job)
    assert job.status == BulkFetchJobStatus.PAUSED

def test_bulk_fetch_resume_transition(db):
    job = BulkFetchJob(scope_type=ScopeType.VILLAGE, status=BulkFetchJobStatus.PAUSED)
    db.add(job)
    db.commit()
    
    res = client.post(f"/api/v1/admin/bulk-fetch/{job.id}/resume")
    assert res.status_code == 200
    db.refresh(job)
    assert job.status == BulkFetchJobStatus.RUNNING

def test_bulk_fetch_cancel_transition(db):
    job = BulkFetchJob(scope_type=ScopeType.VILLAGE, status=BulkFetchJobStatus.RUNNING)
    db.add(job)
    db.commit()
    
    res = client.post(f"/api/v1/admin/bulk-fetch/{job.id}/cancel")
    assert res.status_code == 200
    db.refresh(job)
    assert job.status == BulkFetchJobStatus.CANCELLED

def test_invalid_bulk_fetch_pause_transition(db):
    job = BulkFetchJob(scope_type=ScopeType.VILLAGE, status=BulkFetchJobStatus.COMPLETED)
    db.add(job)
    db.commit()
    
    res = client.post(f"/api/v1/admin/bulk-fetch/{job.id}/pause")
    assert res.status_code == 400

def test_village_bulk_fetch_blank_article_execution(db):
    """
    Regression test verifying:
    1. Create a VILLAGE Bulk Fetch with Article Name blank via API.
    2. Verify API accepts it and creates BulkFetchJob.
    3. Run Planner to verify SearchJob is created.
    4. Run SearchWorker to verify IGR request is constructed with empty article_id and article_name.
    5. Verify no validation error is caused by Article Name being blank.
    """
    from unittest.mock import MagicMock
    from app.models.enums import SearchJobStatus
    from app.scraper.worker.search_worker import SearchWorker
    from app.scraper.client.raw_response import RawSearchResponse
    from app.scraper.client.response_classifier import ResponseClassification

    # Setup location master objects
    from app.models.location import State, District, Taluka, Village
    s = db.query(State).filter_by(source_id="27").first()
    if not s:
        s = State(id=uuid4(), source_system="IGR_MAHARASHTRA", source_id="27", name_en="Maharashtra")
        db.add(s)
        db.commit()

    d = db.query(District).filter_by(source_id="23").first()
    if not d:
        d = District(id=uuid4(), source_system="IGR_MAHARASHTRA", source_id="23", name_en="Pune", state_id=s.id)
        db.add(d)
        db.commit()

    t = db.query(Taluka).filter_by(source_id="1", district_id=d.id).first()
    if not t:
        t = Taluka(id=uuid4(), source_id="1", district_id=d.id, name_en="Haveli")
        db.add(t)
        db.commit()

    v = db.query(Village).filter_by(source_id="5", taluka_id=t.id).first()
    if not v:
        v = Village(id=uuid4(), source_id="5", taluka_id=t.id, name_en="Kharadi")
        db.add(v)
        db.commit()

    # Step 1 & 2: Create VILLAGE Bulk Fetch with blank article selection
    payload = {
        "scope_type": "VILLAGE",
        "district_id": str(d.id),
        "taluka_id": str(t.id),
        "village_id": str(v.id),
        "year_start": 2026,
        "year_end": 2026,
        "article_id": "",
        "article_name": ""
    }
    response = client.post("/api/v1/admin/bulk-fetch", json=payload)
    assert response.status_code == 200, response.text
    bulk_data = response.json()
    bulk_job_id = bulk_data["id"]

    # Step 3: Verify BulkFetchJob exists and run planner
    import uuid
    bulk_uuid = uuid.UUID(bulk_job_id) if isinstance(bulk_job_id, str) else bulk_job_id
    bulk_job = db.query(BulkFetchJob).get(bulk_uuid)
    assert bulk_job is not None
    planner = BulkFetchPlanner(db)
    planner.plan_jobs(bulk_job.id)

    # Step 4: Verify SearchJob child created
    search_jobs = db.query(SearchJob).filter_by(bulk_fetch_job_id=bulk_job.id).all()
    assert len(search_jobs) == 1
    child_job = search_jobs[0]
    assert child_job.location_params["district_id"] == "23"
    assert child_job.location_params["village_id"] == "5"

    # Step 5 & 6: Execute SearchWorker with mock dependencies and capture constructed SearchRequestDTO
    mock_access = MagicMock()
    mock_access.current_context = "ctx"
    mock_client = MagicMock()
    
    mock_raw = RawSearchResponse(
        status_code=200,
        content_type="text/html",
        body=b"<html><body>No records found</body></html>",
        headers={},
        url="http://fake"
    )
    mock_client.search.return_value = mock_raw
    
    mock_solver = MagicMock()
    mock_classifier = MagicMock()
    mock_classifier.classify.return_value = ResponseClassification.SUCCESS
    
    mock_artifact_store = MagicMock()
    mock_artifact_store.save.return_value = str(uuid4())
    
    mock_parser = MagicMock()
    mock_parser_result = MagicMock()
    mock_parser_result.retrieved_count = 0
    mock_parser_result.reported_count = 0
    mock_parser_result.truncated = False
    mock_parser_result.results = []
    mock_parser.parse.return_value = mock_parser_result

    mock_resolver = MagicMock()
    mock_persistence = MagicMock()

    worker = SearchWorker(
        db_session=db,
        access_manager=mock_access,
        client=mock_client,
        captcha_solver=mock_solver,
        classifier=mock_classifier,
        artifact_store=mock_artifact_store,
        parser=mock_parser,
        identity_resolver=mock_resolver,
        persistence_service=mock_persistence
    )

    worker.execute(child_job.id)

    db.refresh(child_job)
    assert child_job.status == SearchJobStatus.COMPLETED
    assert child_job.last_error is None

    # Assert constructed SearchRequestDTO sent to client.search has empty article fields
    assert mock_client.search.called
    called_request_dto = mock_client.search.call_args[0][0]
    assert called_request_dto.article_id == ""
    assert called_request_dto.article_name == ""

    
