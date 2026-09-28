import time
import argparse
import logging
import signal
import sys
import datetime
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.database import SessionLocal
from app.models.job import SearchJob, BulkFetchJob
from app.models.system import WorkerHealth
from app.models.enums import SearchJobStatus, BulkFetchJobStatus
from app.scraper.worker.search_worker import SearchWorker
from app.scraper.client.igr_client import IgrSearchClient
from app.scraper.client.openai_captcha_solver import OpenAICaptchaSolver
from app.scraper.client.response_classifier import ResponseClassifier
from app.scraper.storage.artifact_store import ArtifactStore
from app.scraper.parser.html_parser import PureHtmlParser
from app.scraper.identity.resolver import IdentityResolver
from app.scraper.identity.persistence import RegistrationPersistenceService

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class SearchRunnerConfig:
    def __init__(self, limit=None, dry_run=False, concurrency=1, min_delay_seconds=2, max_retries=3):
        self.limit = limit
        self.dry_run = dry_run
        self.concurrency = concurrency
        self.min_delay_seconds = min_delay_seconds
        self.max_retries = max_retries

class SearchProductionRunner:
    def __init__(self, config: SearchRunnerConfig):
        self.config = config
        self._stop_requested = False
        
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        
    def _handle_shutdown(self, signum, frame):
        logger.info("Shutdown requested. Will stop after the current task finishes.")
        self._stop_requested = True
        
    def _update_heartbeat(self, db: Session, job_id: str = None, is_online: bool = True):
        try:
            health = db.query(WorkerHealth).filter_by(worker_type="SEARCH").first()
            if not health:
                health = WorkerHealth(worker_type="SEARCH")
                db.add(health)
            health.is_online = is_online
            health.last_heartbeat = datetime.datetime.now(datetime.timezone.utc)
            health.current_job_id = job_id
            db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to update worker heartbeat: {e}")

    def run(self, db_session=None):
        logger.info("Phase 1 Search Production Runner Started")
        db = db_session or SessionLocal()
        
        self._update_heartbeat(db, is_online=True)
        
        try:
            if self.config.dry_run:
                logger.info(f"DRY RUN ENABLED. Would process up to {self.config.limit if self.config.limit else 'ALL'} tasks.")
                return
                
            client = IgrSearchClient()
            captcha_solver = OpenAICaptchaSolver()
                
            classifier = ResponseClassifier()
            artifact_store = ArtifactStore()
            parser = PureHtmlParser()
            from app.scraper.identity.repository import PostgresIdentityRepository
            
            repo = PostgresIdentityRepository(session=db)
            identity_resolver = IdentityResolver(repository=repo)
            persistence = RegistrationPersistenceService(db)
            
            from app.scraper.access.windows_network import WindowsNetworkProvider
            from app.scraper.access.source_access_manager import SourceAccessManager
            network_provider = WindowsNetworkProvider(SessionLocal)
            access_manager = SourceAccessManager(network_provider, session_factory=SessionLocal)
            
            worker = SearchWorker(
                db_session=db,
                access_manager=access_manager,
                client=client,
                captcha_solver=captcha_solver,
                classifier=classifier,
                artifact_store=artifact_store,
                parser=parser,
                identity_resolver=identity_resolver,
                persistence_service=persistence
            )
            
            processed = 0
            
            while not self._stop_requested:
                if self.config.limit and processed >= self.config.limit:
                    logger.info(f"Batch limit of {self.config.limit} reached. Stopping.")
                    break
                    
                try:
                    is_sqlite = db.bind.dialect.name == "sqlite"
                    if is_sqlite:
                        job = db.query(SearchJob).filter(
                            SearchJob.status == SearchJobStatus.QUEUED
                        ).order_by(SearchJob.created_at.asc()).first()
                    else:
                        job = db.query(SearchJob).filter(
                            SearchJob.status == SearchJobStatus.QUEUED
                        ).order_by(SearchJob.created_at.asc()).with_for_update(skip_locked=True).first()
                except Exception as e:
                    db.rollback()
                    logger.error(f"Error fetching job: {e}")
                    time.sleep(self.config.min_delay_seconds)
                    continue
                
                if not job:
                    self._update_heartbeat(db, is_online=True, job_id=None)
                    time.sleep(self.config.min_delay_seconds)
                    continue
                    
                # Ensure parent bulk job is RUNNING
                if job.bulk_fetch_job_id:
                    bulk_job = db.query(BulkFetchJob).get(job.bulk_fetch_job_id)
                    if bulk_job and bulk_job.status != BulkFetchJobStatus.RUNNING:
                        logger.info(f"Skipping SearchJob {job.id} as parent BulkFetchJob {bulk_job.id} is {bulk_job.status}")
                        job.status = SearchJobStatus.PAUSED
                        db.commit()
                        continue
                        
                job_id = job.id
                logger.info(f"Processing SearchJob: {job_id}")
                
                # We do NOT mark the job as RUNNING here because the SearchWorker.execute() function does it,
                # but to be safe with concurrency, we can mark it here first.
                job.status = SearchJobStatus.RUNNING
                db.commit()
                
                self._update_heartbeat(db, is_online=True, job_id=str(job_id))
                
                try:
                    worker.execute(job_id)
                except Exception as e:
                    logger.error(f"Unexpected error executing worker on {job_id}: {e}")
                    
                processed += 1
                
                if not self._stop_requested:
                    time.sleep(self.config.min_delay_seconds)
                    
        finally:
            self._update_heartbeat(db, is_online=False, job_id=None)
            if not db_session:
                db.close()
            logger.info("Phase 1 Runner Stopped.")

def main():
    parser = argparse.ArgumentParser(description="Phase 1 Search Production Runner")
    parser.add_argument("--dry-run", action="store_true", help="Print stats and exit without processing")
    parser.add_argument("--limit", type=int, default=None, help="Maximum number of tasks to process")
    parser.add_argument("--delay", type=int, default=2, help="Minimum delay between requests in seconds")
    parser.add_argument("--retries", type=int, default=3, help="Maximum retries for network failures")
    args = parser.parse_args()
    
    config = SearchRunnerConfig(
        limit=args.limit,
        dry_run=args.dry_run,
        min_delay_seconds=args.delay,
        max_retries=args.retries
    )
    
    runner = SearchProductionRunner(config)
    runner.run()

if __name__ == "__main__":
    main()
