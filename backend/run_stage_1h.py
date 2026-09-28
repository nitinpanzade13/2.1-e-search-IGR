import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

# Force override DATABASE_URL inside the script, so other modules importing settings.DATABASE_URL get it
settings.DATABASE_URL = settings.TEST_DATABASE_URL

from app.models.enums import SearchJobStatus, IngestionRunStatus
from app.models.job import SearchJob, IngestionRun, PdfTask
from app.models.ledger import SourceRequestLedger
from app.models.artifact import Artifact
from app.models.processing import ParserRun
import app.db.base
from app.scraper.client.igr_client import IgrSearchClient
from app.scraper.client.captcha import CaptchaSolver
from app.scraper.client.openai_captcha_solver import OpenAICaptchaSolver
from app.scraper.worker.search_worker import SearchWorker
from app.scraper.client.response_classifier import ResponseClassifier
from app.scraper.storage.artifact_store import ArtifactStore
from app.scraper.parser.html_parser import PureHtmlParser
from app.scraper.identity.resolver import IdentityResolver
from app.scraper.identity.repository import PostgresIdentityRepository
from app.scraper.identity.persistence import RegistrationPersistenceService
from app.scraper.access.source_access_manager import SourceAccessManager
from app.scraper.access.windows_network import WindowsNetworkProvider
import time

def main():
    if not settings.IGR_LIVE_TEST_ENABLED:
        print("BLOCKED: IGR_LIVE_TEST_ENABLED is False")
        sys.exit(1)

    print(f"Connecting to: {settings.TEST_DATABASE_URL}")
    engine = create_engine(settings.TEST_DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    # Create job
    run = IngestionRun(name="Stage 1H Live Test", status=IngestionRunStatus.RUNNING)
    db.add(run)
    db.flush()

    job = SearchJob(
        ingestion_run_id=run.id,
        year=2026,
        location_params={"district_id": "23", "taluka_id": "1", "village_id": "43"},
        survey_prefix="1",
        status=SearchJobStatus.QUEUED
    )
    db.add(job)
    db.commit()

    print(f"Created SearchJob ID: {job.id}")

    # Build dependencies
    network_provider = WindowsNetworkProvider(SessionLocal)
    from app.core.database import SessionLocal
    access_manager = SourceAccessManager(network_provider=network_provider, session_factory=SessionLocal)
    client = IgrSearchClient()
    captcha = OpenAICaptchaSolver()
    classifier = ResponseClassifier()
    artifact_store = ArtifactStore()
    parser = PureHtmlParser()
    repo = PostgresIdentityRepository(session=db)
    identity_resolver = IdentityResolver(repository=repo)
    persistence = RegistrationPersistenceService(session=db)
    
    worker = SearchWorker(
        db_session=db,
        access_manager=access_manager,
        client=client,
        captcha_solver=captcha,
        classifier=classifier,
        artifact_store=artifact_store,
        parser=parser,
        identity_resolver=identity_resolver,
        persistence_service=persistence
    )

    print("Executing SearchJob...")
    start = time.time()
    try:
        worker.execute(job.id)
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Job failed with exception: {e}")
        db.rollback()

    print(f"Execution finished in {time.time() - start:.2f}s")
    
    job = db.get(SearchJob, job.id)
    print(f"Final Job Status: {job.status.name}")
    print(f"Job Message: {job.last_error}")
    
    ledgers = db.query(SourceRequestLedger).filter_by(job_id=job.id).all()
    print(f"Ledgers: {len(ledgers)}")
    for l in ledgers:
        print(f"  {l.method} {l.endpoint} - {l.http_status} - {l.duration_ms}ms - ctx: {l.network_context}")
        
    artifacts = db.query(Artifact).join(SourceRequestLedger).filter(SourceRequestLedger.job_id == job.id).all()
    print(f"Artifacts: {len(artifacts)}")
    for a in artifacts:
        print(f"  ID: {a.id}, Type: {a.artifact_type.name}, Size: {a.size_bytes} bytes, SHA: {a.checksum}, Path: {a.storage_path}")
        
    pr = db.query(ParserRun).first()
    if pr:
        output_metadata = pr.output_metadata or {}
        print(f"ParserRun: parsed={output_metadata.get('total_scraped')}, success={pr.is_success}")
        
    print(f"SearchJob stats: requested={job.requested_count}, retrieved={job.retrieved_count}, truncated={job.truncated}")

    regs = db.query(Registration).count()
    print(f"Registrations persisted: {regs}")
    
    # Show some sample source tokens / indexii urls / UUIDs
    sample_regs = db.query(Registration).limit(3).all()
    print(f"Samples:")
    for r in sample_regs:
        print(f"  UUID: {r.id}, Doc: {r.doc_no}, SourceToken: {r.source_token}, Office: {r.office_name_raw}")
        
    pdf_tasks = db.query(PdfTask).count()
    print(f"PdfTasks created: {pdf_tasks}")

if __name__ == '__main__':
    main()
