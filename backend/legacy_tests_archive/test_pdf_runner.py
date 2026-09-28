import pytest
import uuid
import datetime
import threading
import time
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.job import PdfTask
from app.models.registration import Registration
from app.models.enums import PdfTaskStatus
from app.scraper.worker.pdf_runner import PdfProductionRunner, PdfRunnerConfig
from app.scraper.domain.exceptions import IGRRateLimitError, IGRNetworkError, IGRUnexpectedResponseError

class MockPdfWorker:
    def __init__(self, db, throw_error=None):
        self.db = db
        self.throw_error = throw_error
        
    def execute(self, task_id):
        print(f"MOCK EXECUTE CALLED WITH {task_id}")
        task = self.db.query(PdfTask).get(task_id)
        if self.throw_error:
            if isinstance(self.throw_error, (IGRRateLimitError, IGRNetworkError)):
                task.status = PdfTaskStatus.RATE_LIMITED if isinstance(self.throw_error, IGRRateLimitError) else PdfTaskStatus.FAILED
                self.db.commit()
                raise self.throw_error
            elif isinstance(self.throw_error, IGRUnexpectedResponseError) and "404" in str(self.throw_error):
                task.status = PdfTaskStatus.FAILED
                self.db.commit()
            else:
                task.status = PdfTaskStatus.FAILED
                self.db.commit()
        else:
            task.status = PdfTaskStatus.PARSED
            self.db.commit()


@pytest.fixture
def setup_tasks(db: Session, monkeypatch):
    monkeypatch.setattr("app.scraper.worker.pdf_runner.SessionLocal", lambda: db)
    db.rollback() # Clear any aborted transaction state
    db.execute(text("TRUNCATE TABLE pdf_tasks CASCADE"))
    db.execute(text("TRUNCATE TABLE registrations CASCADE"))
    db.commit()
    reg = Registration(id=uuid.uuid4(), year=2026, doc_no="TEST-1", doc_type="Deed")
    db.add(reg)
    t1 = PdfTask(id=uuid.uuid4(), registration_id=reg.id, indexii_url="/test1", source_token="t1", status=PdfTaskStatus.QUEUED)
    t2 = PdfTask(id=uuid.uuid4(), registration_id=reg.id, indexii_url="/test2", source_token="t2", status=PdfTaskStatus.QUEUED)
    db.add_all([t1, t2])
    db.commit()
    return t1, t2

def test_runner_claims_queued_task(db: Session, setup_tasks, monkeypatch):
    t1, t2 = setup_tasks
    
    config = PdfRunnerConfig(limit=1, dry_run=False, min_delay_seconds=0)
    runner = PdfProductionRunner(config)
    
    # Mock worker
    mock_worker = MockPdfWorker(db)
    monkeypatch.setattr("app.scraper.worker.pdf_runner.PdfWorker", lambda *args, **kwargs: mock_worker)
    
    runner.run(db)
    
    print(f"BEFORE REFRESH: t1={t1.status}, t2={t2.status}")
    db.refresh(t1)
    db.refresh(t2)
    print(f"AFTER REFRESH: t1={t1.status}, t2={t2.status}")
    statuses = [t1.status, t2.status]
    assert PdfTaskStatus.PARSED in statuses
    assert PdfTaskStatus.QUEUED in statuses

def test_dry_run_makes_zero_http_requests(db: Session, setup_tasks, monkeypatch):
    t1, t2 = setup_tasks
    config = PdfRunnerConfig(limit=10, dry_run=True, min_delay_seconds=0)
    runner = PdfProductionRunner(config)
    
    called_worker = False
    def execute_mock(*args):
        nonlocal called_worker
        called_worker = True
        
    mock_worker = MockPdfWorker(db)
    mock_worker.execute = execute_mock
    monkeypatch.setattr("app.scraper.worker.pdf_runner.PdfWorker", lambda *args, **kwargs: mock_worker)
    
    runner.run(db)
    
    assert not called_worker
    db.refresh(t1)
    assert t1.status == PdfTaskStatus.QUEUED

def test_rate_limit_stops_batch(db: Session, setup_tasks, monkeypatch):
    t1, t2 = setup_tasks
    # Setting limit higher to prove it stops early
    config = PdfRunnerConfig(limit=10, rate_limit_cooldown_seconds=1, min_delay_seconds=0)
    runner = PdfProductionRunner(config)
    
    mock_worker = MockPdfWorker(db, throw_error=IGRRateLimitError())
    monkeypatch.setattr("app.scraper.worker.pdf_runner.PdfWorker", lambda *args, **kwargs: mock_worker)
    
    start = time.time()
    runner.run(db)
    elapsed = time.time() - start
    
    assert elapsed >= 1.0 # Proves cooldown sleep occurred
    db.refresh(t1)
    db.refresh(t2)
    # The first task gets rate limited, and the batch MUST break immediately.
    # Therefore, the second task must remain QUEUED!
    assert t1.status == PdfTaskStatus.RATE_LIMITED
    assert t2.status == PdfTaskStatus.QUEUED

def test_stale_downloading_task_is_requeued(db: Session, setup_tasks, monkeypatch):
    t1, t2 = setup_tasks
    # Make t1 DOWNLOADING and stale
    t1.status = PdfTaskStatus.DOWNLOADING
    t1.updated_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=60)
    db.commit()
    
    # Mock worker to do nothing so we just check recovery
    mock_worker = MockPdfWorker(db)
    monkeypatch.setattr("app.scraper.worker.pdf_runner.PdfWorker", lambda *args, **kwargs: mock_worker)
    
    config = PdfRunnerConfig(limit=1, stale_timeout_minutes=30, min_delay_seconds=0)
    runner = PdfProductionRunner(config)
    runner.run(db)
    
    db.refresh(t1)
    # Runner should recover it to QUEUED, then process it and mark PARSED
    assert t1.status == PdfTaskStatus.PARSED

def test_404_is_not_retried_aggressively(db: Session, setup_tasks, monkeypatch):
    t1, t2 = setup_tasks
    
    config = PdfRunnerConfig(limit=1, min_delay_seconds=0)
    runner = PdfProductionRunner(config)
    
    mock_worker = MockPdfWorker(db, throw_error=IGRUnexpectedResponseError("404 Not Found"))
    monkeypatch.setattr("app.scraper.worker.pdf_runner.PdfWorker", lambda *args, **kwargs: mock_worker)
    
    runner.run(db)
    
    db.refresh(t1)
    db.refresh(t2)
    statuses = [t1.status, t2.status]
    assert PdfTaskStatus.FAILED in statuses

def test_network_failure_retries(db: Session, setup_tasks, monkeypatch):
    t1, t2 = setup_tasks
    
    config = PdfRunnerConfig(limit=1, min_delay_seconds=0)
    runner = PdfProductionRunner(config)
    
    mock_worker = MockPdfWorker(db, throw_error=IGRNetworkError("Connection reset"))
    monkeypatch.setattr("app.scraper.worker.pdf_runner.PdfWorker", lambda *args, **kwargs: mock_worker)
    
    runner.run(db)
    
    db.refresh(t1)
    db.refresh(t2)
    # The first task gets network error, fails, and limit is 1 so it stops.
    statuses = [t1.status, t2.status]
    assert PdfTaskStatus.FAILED in statuses
    
    attempts = [t1.attempt_count, t2.attempt_count]
    assert 1 in attempts
