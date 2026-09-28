import time
import argparse
import logging
import signal
import sys
import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import SessionLocal
from app.models.job import PdfTask, SearchJob, BulkFetchJob
from app.models.artifact import Artifact
from app.models.registration import Registration, Party, Property
from app.models.office import Office
from app.models.location import Village, Taluka, District
from app.models.enums import PdfTaskStatus
from app.scraper.worker.pdf_worker import PdfWorker
from app.scraper.client.igr_client import IgrSearchClient
from app.scraper.storage.artifact_store import ArtifactStore
from app.scraper.identity.pdf_persistence import PdfPersistenceService
from app.scraper.domain.exceptions import IGRRateLimitError, IGRNetworkError

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class PdfRunnerConfig:
    def __init__(self, limit=None, dry_run=False, concurrency=1, min_delay_seconds=2, max_retries=3, stale_timeout_minutes=30, rate_limit_cooldown_seconds=300):
        self.limit = limit
        self.dry_run = dry_run
        self.concurrency = concurrency # We will enforce 1 for now as per instructions
        self.min_delay_seconds = min_delay_seconds
        self.max_retries = max_retries
        self.stale_timeout_minutes = stale_timeout_minutes
        self.rate_limit_cooldown_seconds = rate_limit_cooldown_seconds

class PdfProductionRunner:
    def __init__(self, config: PdfRunnerConfig):
        self.config = config
        self._stop_requested = False
        
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        
    def _handle_shutdown(self, signum, frame):
        logger.info("Shutdown requested. Will stop after the current task finishes.")
        self._stop_requested = True

    def _recover_stale_tasks(self, db: Session):
        if self.config.dry_run:
            return
            
        stale_threshold = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=self.config.stale_timeout_minutes)
        stale_tasks = db.query(PdfTask).filter(
            PdfTask.status == PdfTaskStatus.DOWNLOADING,
            PdfTask.updated_at < stale_threshold
        ).all()
        
        if stale_tasks:
            logger.info(f"Recovering {len(stale_tasks)} stale DOWNLOADING tasks...")
            for t in stale_tasks:
                t.status = PdfTaskStatus.QUEUED
            db.commit()

    def _get_village_info(self, db: Session, registration_id):
        # Optional: join to get village name for reporting
        try:
            reg = db.query(Registration).get(registration_id)
            if not reg: return "Unknown"
            return f"Office: {reg.office_name_raw or 'Unknown'}"
        except Exception:
            return "Unknown"
            
    def _update_heartbeat(self, db: Session, job_id: str = None, is_online: bool = True):
        try:
            from app.models.system import WorkerHealth
            health = db.query(WorkerHealth).filter_by(worker_type="PDF").first()
            if not health:
                health = WorkerHealth(worker_type="PDF")
                db.add(health)
            health.is_online = is_online
            health.last_heartbeat = datetime.datetime.now(datetime.timezone.utc)
            health.current_job_id = job_id
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update worker heartbeat: {e}")

    def run(self, db_session=None):
        logger.info("Phase 2 PDF Production Runner Started")
        
        db = db_session or SessionLocal()
        try:
            # 1. Recover stale tasks
            self._recover_stale_tasks(db)
            
            # 2. Stats
            total_queued = db.query(PdfTask).filter(PdfTask.status == PdfTaskStatus.QUEUED).count()
            total_completed = db.query(PdfTask).filter(PdfTask.status == PdfTaskStatus.PARSED).count()
            total_failed = db.query(PdfTask).filter(PdfTask.status == PdfTaskStatus.FAILED).count()
            total_rate_limited = db.query(PdfTask).filter(PdfTask.status == PdfTaskStatus.RATE_LIMITED).count()
            total_invalid = db.query(PdfTask).filter(PdfTask.status == PdfTaskStatus.INVALID_PDF).count()
            
            logger.info(f"Stats -> queued: {total_queued}, completed: {total_completed}, failed: {total_failed}, rate_limited: {total_rate_limited}, invalid: {total_invalid}")
            
            if self.config.dry_run:
                logger.info(f"DRY RUN ENABLED. Would process up to {self.config.limit if self.config.limit else 'ALL'} tasks.")
                return
                
            client = IgrSearchClient()
            artifact_store = ArtifactStore()
            persistence = PdfPersistenceService(db)
            
            from app.scraper.access.windows_network import WindowsNetworkProvider
            from app.scraper.access.source_access_manager import SourceAccessManager
            from app.core.database import SessionLocal
            network_provider = WindowsNetworkProvider(SessionLocal)
            access_manager = SourceAccessManager(network_provider, session_factory=SessionLocal)
            worker = PdfWorker(db, access_manager, client, artifact_store, persistence)
            
            processed = 0
            
            self._update_heartbeat(db, is_online=True)
            
            while not self._stop_requested:
                if self.config.limit and processed >= self.config.limit:
                    logger.info(f"Batch limit of {self.config.limit} reached. Stopping.")
                    break
                    
                # Claim one task
                from sqlalchemy import or_
                try:
                    is_sqlite = db.bind.dialect.name == "sqlite"
                    if is_sqlite:
                        task = db.query(PdfTask).filter(
                            PdfTask.status == PdfTaskStatus.QUEUED,
                            or_(PdfTask.attempt_count == None, PdfTask.attempt_count < self.config.max_retries)
                        ).order_by(PdfTask.created_at.asc()).first()
                    else:
                        task = db.query(PdfTask).filter(
                            PdfTask.status == PdfTaskStatus.QUEUED,
                            or_(PdfTask.attempt_count == None, PdfTask.attempt_count < self.config.max_retries)
                        ).order_by(PdfTask.created_at.asc()).with_for_update(skip_locked=True).first()
                except Exception as e:
                    db.rollback()
                
                if not task:
                    self._update_heartbeat(db, is_online=True, job_id=None)
                    break
                    
                task_id = task.id
                reg_id = task.registration_id
                
                # Advance status immediately in the runner so other instances don't grab it 
                # (PdfWorker also does this, but doing it here guarantees the claim before db.commit)
                task.status = PdfTaskStatus.DOWNLOADING
                task.started_at = datetime.datetime.now(datetime.timezone.utc)
                task.attempt_count = (task.attempt_count or 0) + 1
                task.last_attempt_at = task.started_at
                db.commit() # Commit the lock/claim so other processes see DOWNLOADING
                
                self._update_heartbeat(db, is_online=True, job_id=str(task_id))
                
                loc_info = self._get_village_info(db, reg_id)
                logger.info(f"Processing Task: {task_id} | Location: {loc_info} | Attempt: {task.attempt_count}")
                
                try:
                    worker.execute(task_id)
                except IGRRateLimitError:
                    logger.warning(f"Rate limit hit! Cooling down for {self.config.rate_limit_cooldown_seconds}s and stopping batch.")
                    time.sleep(self.config.rate_limit_cooldown_seconds)
                    break
                except IGRNetworkError:
                    logger.warning(f"Network error! Retrying later.")
                except Exception as e:
                    logger.error(f"Unexpected error executing worker: {e}")
                    
                processed += 1
                
                if not self._stop_requested:
                    time.sleep(self.config.min_delay_seconds)
                    
        finally:
            self._update_heartbeat(db, is_online=False, job_id=None)
            if not db_session:
                db.close()
            logger.info("Phase 2 Runner Stopped.")

def main():
    parser = argparse.ArgumentParser(description="Phase 2 PDF Production Runner")
    parser.add_argument("--dry-run", action="store_true", help="Print stats and exit without processing")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of tasks to process")
    parser.add_argument("--delay", type=int, default=2, help="Minimum delay between requests in seconds")
    parser.add_argument("--cooldown", type=int, default=300, help="Rate limit cooldown in seconds")
    parser.add_argument("--retries", type=int, default=3, help="Maximum retries for network failures")
    args = parser.parse_args()
    
    config = PdfRunnerConfig(
        limit=args.limit,
        dry_run=args.dry_run,
        min_delay_seconds=args.delay,
        rate_limit_cooldown_seconds=args.cooldown,
        max_retries=args.retries
    )
    
    runner = PdfProductionRunner(config)
    runner.run()

if __name__ == "__main__":
    main()
