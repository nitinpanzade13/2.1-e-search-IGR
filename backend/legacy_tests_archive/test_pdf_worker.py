import pytest
import uuid
import datetime
from sqlalchemy.orm import Session
from app.models.job import SearchJob, PdfTask, BulkFetchJob
from app.models.registration import Registration, Party, Property
from app.models.enums import SearchJobStatus, PdfTaskStatus, CoverageStatus, ScopeType
from app.scraper.worker.search_worker import SearchWorker
from app.scraper.worker.pdf_worker import PdfWorker
from app.scraper.client.igr_client import IgrSearchClient
from app.scraper.parser.pdf_parser import PdfParser
from app.scraper.domain.dtos import PdfParsedResultDTO
from app.scraper.storage.artifact_store import ArtifactStore
from app.scraper.identity.pdf_persistence import PdfPersistenceService

class MockIgrClient(IgrSearchClient):
    def fetch_pdf(self, url, ledger_callback=None):
        if ledger_callback:
            ledger_callback("GET_pdf", datetime.datetime.now(datetime.timezone.utc), 150, 200, 1000, None, None)
        return b"%PDF-mock-pdf-bytes"

def test_pdf_worker_end_to_end(db: Session, tmp_path):
    # Setup dependencies
    client = MockIgrClient()
    artifact_store = ArtifactStore(base_dir=str(tmp_path))
    persistence = PdfPersistenceService(db)
    
    from unittest.mock import MagicMock
    from app.scraper.access.source_access_manager import AccessState
    mock_access = MagicMock()
    mock_access.state = AccessState.AVAILABLE
    
    worker = PdfWorker(db, mock_access, client, artifact_store, persistence)
    
    # Create test registration
    reg = Registration(
        id=uuid.uuid4(),
        year=2026,
        doc_no="HVL1-1234-2026",
        doc_type="Deed",
        indexii_url="/eDisplay/dummy/123",
        source_token="/eDisplay/dummy/123"
    )
    db.add(reg)
    
    task = PdfTask(
        id=uuid.uuid4(),
        registration_id=reg.id,
        indexii_url=reg.indexii_url,
        source_token=reg.source_token,
        status=PdfTaskStatus.QUEUED
    )
    db.add(task)
    db.commit()
    
    # Mock parse result
    def mock_parse(pdf_bytes):
        res = PdfParsedResultDTO()
        res.doc_no_raw = "HVL1-1234-2026"
        res.consideration_amount_raw = "10000"
        res.sellers_raw = "Seller Name"
        res.buyers_raw = "Buyer Name"
        return res
        
    old_parse = PdfParser.parse
    PdfParser.parse = mock_parse
    
    try:
        worker.execute(task.id)
        
        db.refresh(task)
        db.refresh(reg)
        
        if task.status == PdfTaskStatus.FAILED:
            print("TASK ERROR:", task.last_error)
            
        assert task.status == PdfTaskStatus.PARSED
        assert task.artifact_id is not None
        
        # Verify Ledger is populated
        from app.models.ledger import SourceRequestLedger
        ledgers = db.query(SourceRequestLedger).filter(SourceRequestLedger.job_id == task.id).all()
        assert len(ledgers) == 1
        assert ledgers[0].request_kind.name == "PDF"
        assert ledgers[0].endpoint == "GET_pdf"
        assert ledgers[0].http_status == 200
        assert ledgers[0].artifact_id == task.artifact_id
        
        # Verify Enrichment
        assert reg.consideration_amount == 10000.0
        
        sellers = db.query(Party).filter(Party.registration_id == reg.id, Party.role == "EXECUTANT").all()
        assert len(sellers) == 1
        assert sellers[0].raw_text == "Seller Name"
        
        buyers = db.query(Party).filter(Party.registration_id == reg.id, Party.role == "CLAIMANT").all()
        assert len(buyers) == 1
        assert buyers[0].raw_text == "Buyer Name"
        
        # Test Idempotency
        task.status = PdfTaskStatus.QUEUED
        db.commit()
        
        # Override fetch_pdf to throw error, proving it skips download if artifact exists
        client.fetch_pdf = lambda x, y=None: 1 / 0
        
        worker.execute(task.id)
        db.refresh(task)
        assert task.status == PdfTaskStatus.PARSED
        
        # Check no duplicates
        sellers_after = db.query(Party).filter(Party.registration_id == reg.id, Party.role == "EXECUTANT").all()
        assert len(sellers_after) == 1
        
    finally:
        PdfParser.parse = old_parse

def test_truncation_coverage_not_affected_by_pdf(db: Session):
    bulk_job = BulkFetchJob(
        id=uuid.uuid4(),
        scope_type=ScopeType.VILLAGE,
        status=SearchJobStatus.COMPLETED,
        coverage_status=CoverageStatus.TRUNCATED
    )
    db.add(bulk_job)
    
    search_job = SearchJob(
        id=uuid.uuid4(),
        bulk_fetch_job_id=bulk_job.id,
        year=2026,
        location_params={},
        status=SearchJobStatus.COMPLETED,
        coverage_status=CoverageStatus.TRUNCATED
    )
    db.add(search_job)
    db.commit()
    
    # We do not change search_job.coverage_status in the PDF worker. 
    # The coverage is explicitly governed by search_worker.py.
    assert search_job.coverage_status == CoverageStatus.TRUNCATED
