import pytest
import uuid
import datetime
from unittest.mock import Mock, MagicMock
from sqlalchemy.orm import Session
from app.scraper.worker.search_worker import SearchWorker
from app.scraper.domain.dtos import SearchRequestDTO, SearchResultDTO, SearchResponseDTO, SearchScopeDTO
from app.scraper.domain.exceptions import (
    SourceAccessUnavailable, IGRRateLimitError, IGRNetworkError, IGRCaptchaError, IGRSessionError, IGRValidationError, IGRUnexpectedResponseError, IdentityResolutionError
)
from app.models.job import SearchJob, PdfTask
from app.models.processing import ParserRun
from app.models.ledger import SourceRequestLedger
from app.models.enums import SearchJobStatus, RequestKind, CoverageStatus
from app.scraper.client.raw_response import RawSearchResponse
from app.scraper.client.response_classifier import ResponseClassification
from app.scraper.identity.models import IdentityResolutionDecision, ResolutionOutcome
# The db fixture is now imported from conftest.py

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    pass # Migrations handled centrally now

@pytest.fixture
def mocks():
    return {
        "access": MagicMock(),
        "client": MagicMock(),
        "captcha_solver": MagicMock(),
        "classifier": MagicMock(),
        "artifact_store": MagicMock(),
        "parser": MagicMock(),
        "identity_resolver": MagicMock(),
        "persistence": MagicMock()
    }

@pytest.fixture
def worker(db, mocks):
    mocks["access"].current_context = "test_context"
    return SearchWorker(
        db_session=db,
        access_manager=mocks["access"],
        client=mocks["client"],
        captcha_solver=mocks["captcha_solver"],
        classifier=mocks["classifier"],
        artifact_store=mocks["artifact_store"],
        parser=mocks["parser"],
        identity_resolver=mocks["identity_resolver"],
        persistence_service=mocks["persistence"]
    )

def create_job(db) -> SearchJob:
    from app.models.location import State, District, Taluka, Village
    import uuid
    
    st = db.query(State).filter_by(source_id="27").first()
    if not st:
        st = State(id=uuid.uuid4(), source_system="IGR_MAHARASHTRA", source_id="27", name_en="Maharashtra")
        db.add(st)
        
    d = db.query(District).filter_by(source_id="23").first()
    if not d:
        d = District(id=uuid.uuid4(), state_id=st.id, source_system="IGR_MAHARASHTRA", source_id="23", name_en="पुणे")
        db.add(d)
    elif d.name_en != "पुणे":
        d.name_en = "पुणे"
        db.commit()
        
    t = db.query(Taluka).filter_by(source_id="1", district_id=d.id).first()
    if not t:
        t = Taluka(id=uuid.uuid4(), district_id=d.id, source_system="IGR_MAHARASHTRA", source_id="1", name_en="हवेली")
        db.add(t)
    elif t.name_en != "हवेली":
        t.name_en = "हवेली"
        db.commit()
        
    v = db.query(Village).filter_by(source_id="43", taluka_id=t.id).first()
    if not v:
        v = Village(id=uuid.uuid4(), taluka_id=t.id, source_system="IGR_MAHARASHTRA", source_id="43", name_en="खराडी (पुणे महापालिकेमध्ये समाविष्ट)")
        db.add(v)
    elif v.name_en != "खराडी (पुणे महापालिकेमध्ये समाविष्ट)":
        v.name_en = "खराडी (पुणे महापालिकेमध्ये समाविष्ट)"
        db.commit()
        
    db.commit()

    job = SearchJob(
        year=2026,
        location_params={"district_id": "23", "taluka_id": "1", "village_id": "43"},
        survey_prefix="123",
        status=SearchJobStatus.QUEUED
    )
    db.add(job)
    db.commit()
    return job

def create_artifact(db) -> str:
    import uuid
    return str(uuid.uuid4())

def create_registration(db):
    from app.models.registration import Registration
    reg = Registration(office_name_raw="test", doc_no="123", doc_type="Deed", year=2026)
    db.add(reg)
    db.commit()
    return reg

def create_bulk_job(db, status):
    from app.models.job import BulkFetchJob
    from app.models.enums import SearchJobStatus, BulkFetchJobStatus, ScopeType, CoverageStatus
    from app.models.location import District, Taluka, Village
    d = db.query(District).first()
    t = db.query(Taluka).first()
    v = db.query(Village).first()
    bj = BulkFetchJob(
        scope_type=ScopeType.DISTRICT,
        state_id="1", 
        district_id=d.id if d else None, 
        taluka_id=t.id if t else None, 
        village_id=v.id if v else None,
        requested_year_start=2026, requested_year_end=2026,
        status=status,
        started_at=datetime.datetime.now(datetime.timezone.utc)
    )
    db.add(bj)
    db.flush()
    return bj

def test_purity_assertion():
    import sys
    import app.scraper.worker.search_worker as sw
    assert "requests" not in sw.__dict__
    assert "NetworkProvider" not in sw.__dict__

def test_access_denied_before_request(worker, db, mocks):
    job = create_job(db)
    mocks["access"].acquire.side_effect = SourceAccessUnavailable("denied")
    worker.execute(job.id)
    db.refresh(job)
    assert job.status == SearchJobStatus.PAUSED
    assert job.last_error_category == "SOURCE_ACCESS_UNAVAILABLE"
    mocks["client"].search.assert_not_called()

def test_successful_flow_and_ledger(worker, db, mocks):
    job = create_job(db)
    
    # Simulate client invoking ledger callback multiple times (e.g. GET page, GET captcha, POST search)
    def fake_search(request, captcha, ledger_callback=None):
        if ledger_callback:
            start = datetime.datetime.now(datetime.timezone.utc)
            ledger_callback("GET_search_page", start, 100, 200, 500, None, None)
            ledger_callback("GET_captcha", start + datetime.timedelta(seconds=1), 150, 200, 50, None, None)
            ledger_callback("POST_search", start + datetime.timedelta(seconds=2), 500, 200, 1000, None, None)
        return RawSearchResponse(status_code=200, content_type="text/html", body=b"html", headers={}, url="")
        
    mocks["client"].search.side_effect = fake_search
    mocks["classifier"].classify.return_value = ResponseClassification.SUCCESS
    
    artifact_id = create_artifact(db)
    mocks["artifact_store"].save.return_value = artifact_id
    
    parsed_row = SearchResultDTO(
        year=2026, survey_query="123", sr_no="1", doc_no="111", doc_type="Deed",
        office="Pune", date="2026", seller="A", buyer="B", other_info="None", indexii_url="/test"
    )
    resp_dto = SearchResponseDTO(
        results=[parsed_row], retrieved_count=1, truncated=False, year=2026, survey_query="123", location=SearchScopeDTO()
    )
    mocks["parser"].parse.return_value = resp_dto
    
    decision = IdentityResolutionDecision(outcome=ResolutionOutcome.NEW_REGISTRATION, candidate_ids=[], reason="")
    mocks["identity_resolver"].resolve.return_value = decision
    
    real_reg = create_registration(db)
    real_reg.indexii_url = "/test"
    db.commit()
    mocks["persistence"].persist.return_value = real_reg
    
    worker.execute(job.id)
    db.refresh(job)
    
    if job.status != SearchJobStatus.COMPLETED:
        with open("error.log", "w", encoding="utf-8") as f:
            f.write(f"JOB ERROR: {job.last_error_category} {job.last_error}\n")
        
    assert job.status == SearchJobStatus.COMPLETED
    assert job.retrieved_count == 1
    
    # Ledger should have 3 rows
    ledgers = db.query(SourceRequestLedger).filter(SourceRequestLedger.job_id == job.id).order_by(SourceRequestLedger.started_at).all()
    assert len(ledgers) == 3
    assert ledgers[0].endpoint == "GET_search_page"
    assert ledgers[1].endpoint == "GET_captcha"
    assert ledgers[2].endpoint == "POST_search"
    # Only the last one gets artifact ID
    assert ledgers[0].artifact_id is None
    assert str(ledgers[2].artifact_id) == artifact_id
    
    # Parser Run
    prun = db.query(ParserRun).filter(ParserRun.artifact_id == artifact_id).first()
    assert prun.is_success is True
    
    # PDF Task
    ptask = db.query(PdfTask).filter(PdfTask.registration_id == real_reg.id).first()
    assert ptask is not None

def test_ledger_persistence_failure(worker, db, mocks):
    job = create_job(db)
    
    # We will simulate a failure when writing to the ledger by patching the worker's db session
    original_add = db.add
    def fake_add(obj):
        if isinstance(obj, SourceRequestLedger):
            raise Exception("DB Disk Full")
        original_add(obj)
        
    db.add = fake_add
    
    # Simulate client invoking ledger callback
    def fake_search(request, captcha, ledger_callback=None):
        if ledger_callback:
            start = datetime.datetime.now(datetime.timezone.utc)
            # This should raise RuntimeError immediately
            ledger_callback("GET_search_page", start, 100, 200, 500, None, None)
            
            # We should NEVER reach here
            ledger_callback("GET_captcha", start, 150, 200, 50, None, None)
        return RawSearchResponse(status_code=200, content_type="text/html", body=b"html", headers={}, url="")
        
    mocks["client"].search.side_effect = fake_search
    
    worker.execute(job.id)
    
    # Restore db.add
    db.add = original_add
    
    db.refresh(job)
    assert job.status == SearchJobStatus.QUEUED  # Retryable
    assert job.last_error_category == "LEDGER_PERSISTENCE_ERROR"
    assert "Ledger persistence failed: DB Disk Full" in job.last_error
    
    # Ensure classification and parsing did not happen
    mocks["classifier"].classify.assert_not_called()
    mocks["parser"].parse.assert_not_called()
def test_rate_limited_exception(worker, db, mocks):
    job = create_job(db)
    mocks["client"].search.side_effect = IGRRateLimitError("RL")
    worker.execute(job.id)
    db.refresh(job)
    assert job.status == SearchJobStatus.RATE_LIMITED
    mocks["access"].report_rate_limited.assert_called_once()

def test_location_mapping_exact_strings(worker, db, mocks):
    job = create_job(db)
    
    # We want to check what arguments were passed to client.search
    mocks["client"].search.return_value = RawSearchResponse(status_code=200, content_type="text/html", body=b"html", headers={}, url="")
    mocks["classifier"].classify.return_value = ResponseClassification.SUCCESS
    mocks["artifact_store"].save.return_value = create_artifact(db)
    mocks["parser"].parse.return_value = SearchResponseDTO(results=[], retrieved_count=0, truncated=False, year=2026, survey_query="123", location=SearchScopeDTO())
    
    worker.execute(job.id)
    
    # Verify the exact parameters sent to the IgrSearchClient
    assert mocks["client"].search.call_count == 1
    request_dto = mocks["client"].search.call_args[0][0]
    
    assert request_dto.location.district_id == "23"
    assert request_dto.location.taluka_id == "1"
    assert request_dto.location.village_id == "43"
    
    # Must perfectly match the db name_en inserted in create_job
    assert request_dto.location.district_name == "पुणे"
    assert request_dto.location.taluka_name == "हवेली"
    assert request_dto.location.village_name == "खराडी (पुणे महापालिकेमध्ये समाविष्ट)"

def test_location_mapping_fails_on_empty(worker, db, mocks):
    from app.models.location import State, District, Taluka, Village
    import uuid
    
    sid = uuid.uuid4().hex[:10]
    
    # Create unique isolated location for empty check
    st = db.query(State).filter_by(source_id="27").first()
    d = District(id=uuid.uuid4(), state_id=st.id, source_system="IGR_MAHARASHTRA", source_id=sid, name_en="   ")
    t = Taluka(id=uuid.uuid4(), district_id=d.id, source_system="IGR_MAHARASHTRA", source_id=sid, name_en="TestTaluka")
    v = Village(id=uuid.uuid4(), taluka_id=t.id, source_system="IGR_MAHARASHTRA", source_id=sid, name_en="TestVillage")
    db.add_all([d, t, v])
    db.commit()

    job = SearchJob(
        year=2026,
        location_params={"district_id": sid, "taluka_id": sid, "village_id": sid},
        survey_prefix="123",
        status=SearchJobStatus.QUEUED
    )
    db.add(job)
    db.commit()
    
    # The worker catches ValueErrors and logs them as VALIDATION_ERROR
    worker.execute(job.id)
    
    db.refresh(job)
    
    assert job.status == SearchJobStatus.FAILED
    assert job.last_error_category == "VALIDATION_ERROR"
    assert "Missing required IGR source name" in job.last_error
    
    mocks["client"].search.assert_not_called()

def test_network_error_exception(worker, db, mocks):
    job = create_job(db)
    mocks["client"].search.side_effect = IGRNetworkError("NE", retryable=True)
    from app.scraper.access.source_access_manager import AccessState
    mocks["access"].state = AccessState.AVAILABLE
    
    worker.execute(job.id)
    db.refresh(job)
    assert job.status == SearchJobStatus.QUEUED
    assert job.last_error_category == "NETWORK_RECOVERED"

def test_captcha_error_exception(worker, db, mocks):
    job = create_job(db)
    mocks["client"].search.side_effect = IGRCaptchaError("CE", retryable=True)
    worker.execute(job.id)
    db.refresh(job)
    assert job.status == SearchJobStatus.QUEUED

def test_session_error_exception(worker, db, mocks):
    job = create_job(db)
    mocks["client"].search.side_effect = IGRSessionError("SE", retryable=True)
    worker.execute(job.id)
    db.refresh(job)
    assert job.status == SearchJobStatus.QUEUED

def test_validation_error_exception(worker, db, mocks):
    job = create_job(db)
    mocks["client"].search.side_effect = IGRValidationError("VE", retryable=False)
    worker.execute(job.id)
    db.refresh(job)
    assert job.status == SearchJobStatus.FAILED

def test_unexpected_response_exception(worker, db, mocks):
    job = create_job(db)
    mocks["client"].search.side_effect = IGRUnexpectedResponseError("UR", retryable=False)
    worker.execute(job.id)
    db.refresh(job)
    assert job.status == SearchJobStatus.FAILED

def test_classification_rate_limited(worker, db, mocks):
    job = create_job(db)
    mocks["client"].search.return_value = RawSearchResponse(status_code=200, content_type="", body=b"", headers={}, url="")
    mocks["classifier"].classify.return_value = ResponseClassification.RATE_LIMITED
    mocks["artifact_store"].save.return_value = str(uuid.uuid4())
    from app.scraper.access.source_access_manager import AccessState
    mocks["access"].state = AccessState.AVAILABLE
    worker.execute(job.id)
    db.refresh(job)
    assert job.status == SearchJobStatus.QUEUED
    mocks["access"].report_rate_limited.assert_called_once()

def test_classification_captcha_failed(worker, db, mocks):
    job = create_job(db)
    mocks["client"].search.return_value = RawSearchResponse(status_code=200, content_type="", body=b"", headers={}, url="")
    mocks["classifier"].classify.return_value = ResponseClassification.CAPTCHA_FAILED
    mocks["artifact_store"].save.return_value = str(uuid.uuid4())
    worker.execute(job.id)
    db.refresh(job)
    assert job.status == SearchJobStatus.QUEUED
    assert job.last_error_category == "CAPTCHA_ERROR"

def test_classification_captcha_failed_max_retries(worker, db, mocks):
    job = create_job(db)
    job.attempt_count = 4 # Exceeds max_retries = 3
    db.commit()
    mocks["client"].search.return_value = RawSearchResponse(status_code=200, content_type="", body=b"", headers={}, url="")
    mocks["classifier"].classify.return_value = ResponseClassification.CAPTCHA_FAILED
    mocks["artifact_store"].save.return_value = str(uuid.uuid4())
    worker.execute(job.id)
    db.refresh(job)
    assert job.status == SearchJobStatus.FAILED
    assert job.last_error_category == "CAPTCHA_ERROR"

def test_classification_validation_error(worker, db, mocks):
    job = create_job(db)
    mocks["client"].search.return_value = RawSearchResponse(status_code=200, content_type="", body=b"", headers={}, url="")
    mocks["classifier"].classify.return_value = ResponseClassification.VALIDATION_ERROR
    mocks["artifact_store"].save.return_value = str(uuid.uuid4())
    worker.execute(job.id)
    db.refresh(job)
    assert job.status == SearchJobStatus.FAILED
    assert job.last_error_category == "VALIDATION_ERROR"

def test_classification_session_error(worker, db, mocks):
    job = create_job(db)
    mocks["client"].search.return_value = RawSearchResponse(status_code=200, content_type="", body=b"", headers={}, url="")
    mocks["classifier"].classify.return_value = ResponseClassification.AUTH_SESSION_ERROR
    mocks["artifact_store"].save.return_value = str(uuid.uuid4())
    worker.execute(job.id)
    db.refresh(job)
    assert job.status == SearchJobStatus.QUEUED
    assert job.last_error_category == "SESSION_ERROR"

def test_classification_network_error(worker, db, mocks):
    job = create_job(db)
    mocks["client"].search.return_value = RawSearchResponse(status_code=200, content_type="", body=b"", headers={}, url="")
    mocks["classifier"].classify.return_value = ResponseClassification.NETWORK_ERROR
    mocks["artifact_store"].save.return_value = str(uuid.uuid4())
    from app.scraper.access.source_access_manager import AccessState
    mocks["access"].state = AccessState.AVAILABLE
    worker.execute(job.id)
    db.refresh(job)
    assert job.status == SearchJobStatus.QUEUED
    assert job.last_error_category == "NETWORK_ERROR"

def test_classification_unexpected_response(worker, db, mocks):
    job = create_job(db)
    mocks["client"].search.return_value = RawSearchResponse(status_code=200, content_type="", body=b"", headers={}, url="")
    mocks["classifier"].classify.return_value = ResponseClassification.UNEXPECTED_RESPONSE
    mocks["artifact_store"].save.return_value = str(uuid.uuid4())
    worker.execute(job.id)
    db.refresh(job)
    assert job.status == SearchJobStatus.FAILED
    assert job.last_error_category == "UNEXPECTED_RESPONSE_ERROR"

def test_artifact_persistence_failure(worker, db, mocks):
    job = create_job(db)
    mocks["client"].search.return_value = RawSearchResponse(status_code=200, content_type="", body=b"A", headers={}, url="")
    mocks["classifier"].classify.return_value = ResponseClassification.SUCCESS
    mocks["artifact_store"].save.side_effect = Exception("Disk full")
    
    worker.execute(job.id)
    db.refresh(job)
    assert job.status == SearchJobStatus.QUEUED # retryable
    assert job.last_error_category == "ARTIFACT_STORAGE_ERROR"
    mocks["parser"].parse.assert_not_called()

def test_parser_failure_preserves_artifact(worker, db, mocks):
    job = create_job(db)
    def fake_search(request, captcha, ledger_callback=None):
        if ledger_callback:
            start = datetime.datetime.now(datetime.timezone.utc)
            ledger_callback("POST", start, 100, 200, 500, None, None)
        return RawSearchResponse(status_code=200, content_type="", body=b"X", headers={}, url="")
    mocks["client"].search.side_effect = fake_search
    mocks["classifier"].classify.return_value = ResponseClassification.SUCCESS
    artifact_id = create_artifact(db)
    mocks["artifact_store"].save.return_value = artifact_id
    mocks["parser"].parse.side_effect = Exception("Parse failed")
    
    worker.execute(job.id)
    db.refresh(job)
    assert job.status == SearchJobStatus.FAILED
    
    # Artifact ID should be in ledger
    ledger = db.query(SourceRequestLedger).filter(SourceRequestLedger.job_id == job.id).first()
    assert str(ledger.artifact_id) == artifact_id
    
    prun = db.query(ParserRun).filter(ParserRun.artifact_id == artifact_id).first()
    assert prun.is_success is False

def test_registration_persistence_failure(worker, db, mocks):
    job = create_job(db)
    mocks["client"].search.return_value = RawSearchResponse(status_code=200, content_type="", body=b"", headers={}, url="")
    mocks["classifier"].classify.return_value = ResponseClassification.SUCCESS
    mocks["artifact_store"].save.return_value = create_artifact(db)
    
    parsed_row = SearchResultDTO(year=2026, survey_query="1", sr_no="1", doc_no="1", doc_type="A", office="O", date="D", seller="S", buyer="B", other_info="I", indexii_url="/")
    mocks["parser"].parse.return_value = SearchResponseDTO(results=[parsed_row], retrieved_count=1, truncated=False, year=2026, survey_query="1", location=SearchScopeDTO())
    
    mocks["identity_resolver"].resolve.return_value = IdentityResolutionDecision(outcome=ResolutionOutcome.NEW_REGISTRATION, candidate_ids=[], reason="")
    mocks["persistence"].persist.side_effect = Exception("DB DEAD")
    
    worker.execute(job.id)
    db.refresh(job)
    assert job.status == SearchJobStatus.FAILED
    assert job.last_error_category == "PERSISTENCE_ERROR"

def test_identity_ambiguous_and_possible_duplicate(worker, db, mocks):
    job = create_job(db)
    mocks["client"].search.return_value = RawSearchResponse(status_code=200, content_type="", body=b"", headers={}, url="")
    mocks["classifier"].classify.return_value = ResponseClassification.SUCCESS
    mocks["artifact_store"].save.return_value = create_artifact(db)
    
    row1 = SearchResultDTO(year=2026, survey_query="1", sr_no="1", doc_no="1", doc_type="A", office="O", date="D", seller="S", buyer="B", other_info="I", indexii_url="/")
    row2 = SearchResultDTO(year=2026, survey_query="1", sr_no="2", doc_no="2", doc_type="B", office="O", date="D", seller="S", buyer="B", other_info="I", indexii_url="/")
    mocks["parser"].parse.return_value = SearchResponseDTO(results=[row1, row2], retrieved_count=2, truncated=False, year=2026, survey_query="1", location=SearchScopeDTO())
    
    def mock_resolve(row):
        if row.doc_no == "1": return IdentityResolutionDecision(outcome=ResolutionOutcome.AMBIGUOUS, candidate_ids=[], reason="")
        return IdentityResolutionDecision(outcome=ResolutionOutcome.POSSIBLE_DUPLICATE, candidate_ids=[], reason="")
        
    mocks["identity_resolver"].resolve.side_effect = mock_resolve
    
    # When persistence receives AMBIGUOUS or POSSIBLE_DUPLICATE, it raises IdentityResolutionError in the 1E-B architecture
    mocks["persistence"].persist.side_effect = IdentityResolutionError("rejected")
    
    worker.execute(job.id)
    db.refresh(job)
    assert job.status == SearchJobStatus.COMPLETED # They were skipped safely
    
def test_5000_truncation_handling(worker, db, mocks):
    job = create_job(db)
    mocks["client"].search.return_value = RawSearchResponse(status_code=200, content_type="text/html", body=b"", headers={}, url="")
    mocks["classifier"].classify.return_value = ResponseClassification.SUCCESS
    mocks["artifact_store"].save.return_value = create_artifact(db)
    
    resp_dto = SearchResponseDTO(
        results=[], retrieved_count=5000, truncated=True, year=2026, survey_query="123", location=SearchScopeDTO()
    )
    mocks["parser"].parse.return_value = resp_dto
    
    worker.execute(job.id)
    db.refresh(job)
    assert job.status == SearchJobStatus.COMPLETED
    assert job.coverage_status == CoverageStatus.TRUNCATED
    assert job.retrieved_count == 5000
    assert job.truncated is True

def test_multiple_registrations_existing_and_new(worker, db, mocks):
    job = create_job(db)
    mocks["client"].search.return_value = RawSearchResponse(status_code=200, content_type="", body=b"", headers={}, url="")
    mocks["classifier"].classify.return_value = ResponseClassification.SUCCESS
    mocks["artifact_store"].save.return_value = create_artifact(db)
    
    row1 = SearchResultDTO(year=2026, survey_query="1", sr_no="1", doc_no="1", doc_type="A", office="O", date="D", seller="S", buyer="B", other_info="I", indexii_url="/1")
    row2 = SearchResultDTO(year=2026, survey_query="1", sr_no="2", doc_no="2", doc_type="B", office="O", date="D", seller="S", buyer="B", other_info="I", indexii_url="/2")
    mocks["parser"].parse.return_value = SearchResponseDTO(results=[row1, row2], retrieved_count=2, truncated=False, year=2026, survey_query="1", location=SearchScopeDTO())
    
    mocks["identity_resolver"].resolve.return_value = IdentityResolutionDecision(outcome=ResolutionOutcome.NEW_REGISTRATION, candidate_ids=[], reason="")
    
    reg1 = create_registration(db)
    reg1.indexii_url = "/1"
    reg2 = create_registration(db)
    reg2.indexii_url = "/2"
    db.commit()
    
    mocks["persistence"].persist.side_effect = [reg1, reg2]
    
    worker.execute(job.id)
    db.refresh(job)
    assert job.status == SearchJobStatus.COMPLETED
    assert db.query(PdfTask).filter(PdfTask.registration_id.in_([reg1.id, reg2.id])).count() == 2

from app.models.enums import BulkFetchJobStatus
def test_bulk_fetch_job_status_paused_blocks_execution(worker, db, mocks):
    bj = create_bulk_job(db, BulkFetchJobStatus.PAUSED)
    job = create_job(db)
    job.bulk_fetch_job_id = bj.id
    db.commit()
    worker.execute(job.id)
    db.refresh(job)
    assert job.status == SearchJobStatus.QUEUED
    mocks["client"].search.assert_not_called()

def test_bulk_fetch_job_status_cancelled_blocks_execution(worker, db, mocks):
    bj = create_bulk_job(db, BulkFetchJobStatus.CANCELLED)
    job = create_job(db)
    job.bulk_fetch_job_id = bj.id
    db.commit()
    worker.execute(job.id)
    db.refresh(job)
    assert job.status == SearchJobStatus.QUEUED
    mocks["client"].search.assert_not_called()

def test_bulk_fetch_job_status_completed_blocks_execution(worker, db, mocks):
    bj = create_bulk_job(db, BulkFetchJobStatus.COMPLETED)
    job = create_job(db)
    job.bulk_fetch_job_id = bj.id
    db.commit()
    worker.execute(job.id)
    db.refresh(job)
    assert job.status == SearchJobStatus.QUEUED
    mocks["client"].search.assert_not_called()

def test_bulk_fetch_job_status_rate_limited_blocks_execution(worker, db, mocks):
    bj = create_bulk_job(db, BulkFetchJobStatus.RATE_LIMITED)
    job = create_job(db)
    job.bulk_fetch_job_id = bj.id
    db.commit()
    worker.execute(job.id)
    db.refresh(job)
    assert job.status == SearchJobStatus.QUEUED
    mocks["client"].search.assert_not_called()

def test_bulk_fetch_job_status_missing_blocks_execution(worker, db, mocks, monkeypatch):
    bj = create_bulk_job(db, BulkFetchJobStatus.RUNNING)
    job = create_job(db)
    job.bulk_fetch_job_id = bj.id
    db.commit()
    
    # Mock the query so that it returns None when looking up the parent
    original_query = db.query
    def mock_query(*args, **kwargs):
        from app.models.job import BulkFetchJob
        q = original_query(*args, **kwargs)
        if args[0] is BulkFetchJob:
            mock_q = MagicMock()
            mock_q.get.return_value = None
            return mock_q
        return q
        
    monkeypatch.setattr(db, "query", mock_query)
    
    worker.execute(job.id)
    db.refresh(job)
    assert job.status == SearchJobStatus.QUEUED
    mocks["client"].search.assert_not_called()

def test_bulk_fetch_job_status_running_permits_execution(worker, db, mocks):
    bj = create_bulk_job(db, BulkFetchJobStatus.RUNNING)
    job = create_job(db)
    job.bulk_fetch_job_id = bj.id
    db.commit()
    
    mocks["client"].search.side_effect = IGRNetworkError("NE", retryable=True)
    
    from app.scraper.access.source_access_manager import AccessState
    mocks["access"].state = AccessState.AVAILABLE
    
    worker.execute(job.id)
    db.refresh(job)
    
    # It should have executed and encountered the network error
    assert job.status == SearchJobStatus.QUEUED
    assert job.last_error_category == "NETWORK_RECOVERED"
    mocks["client"].search.assert_called_once()

def test_mixed_child_states_aggregate_correctly(db):
    from app.scraper.orchestration.service import BulkFetchService
    bj = create_bulk_job(db, BulkFetchJobStatus.RUNNING)
    
    # Add 5 jobs with mixed states
    states = [SearchJobStatus.COMPLETED, SearchJobStatus.FAILED, SearchJobStatus.TRUNCATED, SearchJobStatus.RATE_LIMITED, SearchJobStatus.QUEUED]
    for st in states:
        j = SearchJob(
            bulk_fetch_job_id=bj.id, year=2026, location_params={"district_id": "1"}, survey_prefix="1", status=st,
            requested_count=10, retrieved_count=5, truncated=(st == SearchJobStatus.TRUNCATED)
        )
        db.add(j)
    db.commit()
    
    svc = BulkFetchService(db)
    svc.aggregate_progress(bj.id)
    db.refresh(bj)
    
    assert bj.total_units == 5
    assert bj.completed_units == 1
    assert bj.failed_units == 1
    assert bj.truncated_units == 1
    assert bj.rate_limited_units == 1
    assert bj.queued_units == 1
    assert bj.total_records_reported == 50
    assert bj.total_records_retrieved == 25
    assert bj.status == BulkFetchJobStatus.RATE_LIMITED # RATE_LIMITED takes precedence
    
    # Clear and set all COMPLETED
    db.query(SearchJob).filter(SearchJob.bulk_fetch_job_id == bj.id).update({"status": SearchJobStatus.COMPLETED})
    db.commit()
    
    bj.status = BulkFetchJobStatus.RUNNING
    db.commit()
    svc.aggregate_progress(bj.id)
    db.refresh(bj)
    
    assert bj.completed_units == 5
    assert bj.status == BulkFetchJobStatus.COMPLETED


