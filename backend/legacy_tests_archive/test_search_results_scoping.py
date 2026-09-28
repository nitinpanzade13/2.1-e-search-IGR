import pytest
from uuid import uuid4
from fastapi.testclient import TestClient
from app.main import app
from app.models.location import District, State
from app.models.office import Office
from app.models.job import SearchJob, SearchJobRegistration
from app.models.registration import Registration
from app.models.enums import SearchJobStatus

client = TestClient(app)

@pytest.fixture
def base_data(db):
    state = db.query(State).filter_by(source_id="27").first()
    if not state:
        state = State(source_id="27", name_en="Maharashtra")
        db.add(state)
        db.commit()
        db.refresh(state)

    dist = db.query(District).filter_by(source_id="101").first()
    if not dist:
        dist = District(source_id="101", name_en="Test District", state_id=state.id)
        db.add(dist)
        db.commit()
        db.refresh(dist)

    office = Office(source_id="202", name="Test Office", district_id=dist.id)
    db.add(office)
    db.commit()
    db.refresh(office)
    return dist, office

def test_search_results_scoping_isolation(db, base_data):
    dist, office = base_data
    
    # Create two jobs for two different villages in the same district
    job_a = SearchJob(year=2026, location_params={"district_id": dist.source_id, "village_id": "900"}, status=SearchJobStatus.COMPLETED)
    job_b = SearchJob(year=2026, location_params={"district_id": dist.source_id, "village_id": "901"}, status=SearchJobStatus.COMPLETED)
    db.add_all([job_a, job_b])
    db.commit()
    
    # Create Registrations
    reg_1 = Registration(year=2026, doc_no="1001", doc_type="Type A", office_id=office.id)
    reg_2 = Registration(year=2026, doc_no="1002", doc_type="Type A", office_id=office.id)
    db.add_all([reg_1, reg_2])
    db.commit()
    
    # Link job_a to reg_1, job_b to reg_2
    link_a = SearchJobRegistration(search_job_id=job_a.id, registration_id=reg_1.id)
    link_b = SearchJobRegistration(search_job_id=job_b.id, registration_id=reg_2.id)
    db.add_all([link_a, link_b])
    db.commit()
    
    # GET results for A -> only Registration 1
    res_a = client.get(f"/api/v1/search/{job_a.id}/results")
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert data_a["total"] == 1
    assert data_a["items"][0]["id"] == str(reg_1.id)
    assert not data_a.get("provenance_unavailable")
    
    # GET results for B -> only Registration 2
    res_b = client.get(f"/api/v1/search/{job_b.id}/results")
    assert res_b.status_code == 200
    data_b = res_b.json()
    assert data_b["total"] == 1
    assert data_b["items"][0]["id"] == str(reg_2.id)

def test_multiple_jobs_linking_same_registration(db, base_data):
    dist, office = base_data
    
    job_a = SearchJob(year=2026, location_params={"district_id": dist.source_id}, status=SearchJobStatus.COMPLETED)
    job_b = SearchJob(year=2026, location_params={"district_id": dist.source_id}, status=SearchJobStatus.COMPLETED)
    reg_1 = Registration(year=2026, doc_no="9999", doc_type="Type X", office_id=office.id)
    db.add_all([job_a, job_b, reg_1])
    db.commit()
    
    # Both jobs discover same registration
    link_a = SearchJobRegistration(search_job_id=job_a.id, registration_id=reg_1.id)
    link_b = SearchJobRegistration(search_job_id=job_b.id, registration_id=reg_1.id)
    db.add_all([link_a, link_b])
    db.commit()
    
    # Ensure both return reg_1
    for job_id in [job_a.id, job_b.id]:
        res = client.get(f"/api/v1/search/{job_id}/results")
        data = res.json()
        assert data["total"] == 1
        assert data["items"][0]["id"] == str(reg_1.id)
        
def test_historical_job_without_provenance(db):
    # Job has completed and retrieved records, but no links
    job = SearchJob(year=2020, location_params={"district_id": "99"}, status=SearchJobStatus.COMPLETED, retrieved_count=50)
    db.add(job)
    db.commit()
    
    res = client.get(f"/api/v1/search/{job.id}/results")
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 0
    assert data["provenance_unavailable"] == True
