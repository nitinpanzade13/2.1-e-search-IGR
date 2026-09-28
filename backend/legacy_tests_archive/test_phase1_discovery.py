import pytest
import uuid
import datetime
from unittest.mock import MagicMock
from app.scraper.worker.search_worker import SearchWorker
from app.scraper.domain.dtos import SearchRequestDTO, SearchResultDTO, SearchResponseDTO, SearchScopeDTO
from app.models.job import SearchJob, PdfTask
from app.models.enums import SearchJobStatus, CoverageStatus, ArtifactType
from app.models.registration import Registration
from app.models.location import State, District, Taluka, Village
from app.models.artifact import Artifact
from app.scraper.client.raw_response import RawSearchResponse
from app.scraper.client.response_classifier import ResponseClassification
from app.scraper.identity.models import IdentityResolutionDecision, ResolutionOutcome
from app.scraper.parser.candidate_parser import CandidatePropertyParser

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

def create_artifact(db):
    return str(uuid.uuid4())

def create_job(db, requested_count=None, truncated=False):
    dist_id = str(uuid.uuid4())
    tal_id = str(uuid.uuid4())
    vill_id = str(uuid.uuid4())
    s = db.query(State).filter_by(source_id="27").first()
    d = District(id=uuid.uuid4(), name_en="D", name_mr="D", source_system="IGR_MAHARASHTRA", source_id=dist_id, state_id=s.id)
    t = Taluka(id=uuid.uuid4(), name_en="T", name_mr="T", source_system="IGR_MAHARASHTRA", source_id=tal_id, district_id=d.id)
    v = Village(id=uuid.uuid4(), name_en="V", name_mr="V", source_system="IGR_MAHARASHTRA", source_id=vill_id, taluka_id=t.id)
    db.add_all([d, t, v])
    job = SearchJob(
        year=2026,
        location_params={"district_id": dist_id, "taluka_id": tal_id, "village_id": vill_id},
        survey_prefix="1",
        requested_count=requested_count,
        truncated=truncated
    )
    db.add(job)
    db.commit()
    return job

def test_truncation_coverage_status(db, worker, mocks):
    job = create_job(db)
    mocks["artifact_store"].save.return_value = create_artifact(db)
    mocks["classifier"].classify.return_value = ResponseClassification.SUCCESS
    mocks["client"].search.return_value = RawSearchResponse(body=b"5000 Records found", content_type="text/html", status_code=200, headers={}, url="http://test")
    
    row = SearchResultDTO(year=2026, survey_query="1", indexii_url="/IndexII/1", sr_no="1", doc_no="1", doc_type="T", office="Pune", date="01/01/2026", seller="A", buyer="B", other_info="info")
    mocks["parser"].parse.return_value = SearchResponseDTO(
        results=[row], 
        reported_count=5000, 
        retrieved_count=5000, 
        truncated=True, 
        year=2026, 
        survey_query="1", 
        location=SearchScopeDTO()
    )
    
    mocks["identity_resolver"].resolve.return_value = IdentityResolutionDecision(
        outcome=ResolutionOutcome.NEW_REGISTRATION, candidate_ids=[], reason=""
    )
    
    reg = Registration(id=uuid.uuid4(), year=2026, doc_no="1", doc_type="T", indexii_url="/IndexII/1")
    db.add(reg)
    mocks["persistence"].persist.return_value = reg
    
    worker.execute(job.id)
    
    updated_job = db.query(SearchJob).get(job.id)
    assert updated_job.status == SearchJobStatus.COMPLETED, f"Job failed! Category: {updated_job.last_error_category}, Error: {updated_job.last_error}"
    assert updated_job.coverage_status == CoverageStatus.TRUNCATED
    assert updated_job.retrieved_count == 5000
    
def test_no_pdf_request_in_phase1(db, worker, mocks):
    job = create_job(db)
    mocks["artifact_store"].save.return_value = create_artifact(db)
    mocks["classifier"].classify.return_value = ResponseClassification.SUCCESS
    mocks["client"].search.return_value = RawSearchResponse(body=b"<html></html>", content_type="text/html", status_code=200, headers={}, url="http://test")
    
    row = SearchResultDTO(year=2026, survey_query="1", indexii_url="/IndexII/123", sr_no="1", doc_no="123", doc_type="T", office="Pune", date="01/01/2026", seller="A", buyer="B", other_info="info")
    mocks["parser"].parse.return_value = SearchResponseDTO(
        results=[row], reported_count=1, retrieved_count=1, truncated=False, year=2026, survey_query="1", location=SearchScopeDTO()
    )
    
    mocks["identity_resolver"].resolve.return_value = IdentityResolutionDecision(
        outcome=ResolutionOutcome.NEW_REGISTRATION, candidate_ids=[], reason=""
    )
    
    reg = Registration(id=uuid.uuid4(), year=2026, doc_no="123", doc_type="T", indexii_url="/IndexII/123")
    db.add(reg)
    mocks["persistence"].persist.return_value = reg
    
    worker.execute(job.id)
    db.refresh(job)
    assert job.status == SearchJobStatus.COMPLETED, f"Job failed! Category: {job.last_error_category}, Error: {job.last_error}"
    
    task = db.query(PdfTask).filter_by(registration_id=reg.id).first()
    assert task is not None
    assert task.status.name == "QUEUED"
    
    assert mocks["client"].search.call_count == 1
    assert len(mocks["client"].mock_calls) == 1

def test_candidate_property_parser_does_not_fail():
    # Prove that the candidate property extraction never becomes a failure point
    raw_text = "स. क्र. 21/1 हिस्सा क्र. 12"
    candidates = CandidatePropertyParser.parse(raw_text)
    assert len(candidates) == 1
    assert candidates[0].get("survey") == "21/1"
    
    # Random unparseable string
    candidates = CandidatePropertyParser.parse("Random unstructured marathi text without numbers")
    assert candidates == []

    # Should not throw exception on None
    candidates = CandidatePropertyParser.parse(None)
    assert candidates == []

def test_deduplication_overlapping_searches(db):
    from app.scraper.identity.resolver import IdentityResolver
    from app.scraper.identity.repository import PostgresIdentityRepository
    
    repo = PostgresIdentityRepository(db)
    resolver = IdentityResolver(repo)
    
    doc_id = str(uuid.uuid4())[:10]
    idx_url = f"/IndexII/{doc_id}"
    
    # Simulate first search result
    res1 = SearchResultDTO(year=2026, survey_query="1", indexii_url=idx_url, office="Pune", doc_no=doc_id, sr_no="1", doc_type="T", date="01/01/2026", seller="A", buyer="B", other_info="info")
    decision1 = resolver.resolve(res1)
    
    assert decision1.outcome == ResolutionOutcome.NEW_REGISTRATION
    
    # Persist the registration (like persistence service would)
    reg1 = Registration(id=uuid.uuid4(), year=2026, doc_no=doc_id, doc_type="T", indexii_url=idx_url, source_token=idx_url)
    db.add(reg1)
    db.commit()
    
    # Simulate overlapping search query "11" finding the exact same document
    res2 = SearchResultDTO(year=2026, survey_query="11", indexii_url=idx_url, office="Pune", doc_no=doc_id, sr_no="2", doc_type="T", date="01/01/2026", seller="A", buyer="B", other_info="info")
    decision2 = resolver.resolve(res2)
    
    assert decision2.outcome == ResolutionOutcome.EXISTING_CONFIRMED
    assert reg1.id in decision2.candidate_ids
    # This proves they are persisted only once, because decision2 points to EXISTING_CONFIRMED

def test_survey_number_does_not_merge_registrations(db):
    from app.scraper.identity.resolver import IdentityResolver
    from app.scraper.identity.repository import PostgresIdentityRepository
    
    repo = PostgresIdentityRepository(db)
    resolver = IdentityResolver(repo)
    
    doc1 = str(uuid.uuid4())[:10]
    doc2 = str(uuid.uuid4())[:10]
    
    # Same survey, DIFFERENT doc_no / indexii_url
    res1 = SearchResultDTO(year=2026, survey_query="21", indexii_url=f"/IndexII/{doc1}", office="Pune", doc_no=doc1, other_info="स. क्र. 21/1", sr_no="1", doc_type="T", date="01/01/2026", seller="A", buyer="B")
    reg1 = Registration(id=uuid.uuid4(), year=2026, doc_no=doc1, doc_type="T", indexii_url=f"/IndexII/{doc1}", source_token=f"/IndexII/{doc1}")
    reg1.candidate_properties = CandidatePropertyParser.parse(res1.other_info)
    db.add(reg1)
    db.commit()
    
    # Search finds a new document on the same survey
    res2 = SearchResultDTO(year=2026, survey_query="21", indexii_url=f"/IndexII/{doc2}", office="Pune", doc_no=doc2, other_info="स. क्र. 21/1", sr_no="2", doc_type="T", date="01/01/2026", seller="C", buyer="D")
    decision2 = resolver.resolve(res2)
    
    # Because identity relies on indexii_url and doc_no, NOT survey/candidate_properties
    assert decision2.outcome == ResolutionOutcome.NEW_REGISTRATION
    # This proves they remain separate registrations

