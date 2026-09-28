import uuid
import datetime
import logging
from sqlalchemy.orm import Session
from app.models.job import PdfTask
from app.models.processing import ParserRun
from app.models.enums import PdfTaskStatus, ProcessingStatus
from app.scraper.client.igr_client import IgrSearchClient
from app.scraper.storage.artifact_store import ArtifactStore
from app.scraper.parser.pdf_parser import PdfParser
from app.scraper.identity.pdf_persistence import PdfPersistenceService
from app.models.artifact import Artifact
from app.models.enums import ArtifactType, RequestKind
from app.models.ledger import SourceRequestLedger

logger = logging.getLogger(__name__)
from app.scraper.access.source_access_manager import SourceAccessManager
from app.scraper.domain.exceptions import SourceAccessUnavailable

class PdfWorker:
    def __init__(
        self,
        db_session: Session,
        access_manager: SourceAccessManager,
        client: IgrSearchClient,
        artifact_store: ArtifactStore,
        persistence_service: PdfPersistenceService
    ):
        self.db = db_session
        self.access = access_manager
        self.client = client
        self.artifact_store = artifact_store
        self.persistence = persistence_service

    def execute(self, pdf_task_id: uuid.UUID):
        task = self.db.query(PdfTask).get(pdf_task_id)
        if not task:
            return

        # 1. State Transition
        if task.status != PdfTaskStatus.DOWNLOADING:
            task.status = PdfTaskStatus.DOWNLOADING
            task.started_at = datetime.datetime.now(datetime.timezone.utc)
            task.attempt_count = (task.attempt_count or 0) + 1
            task.last_attempt_at = task.started_at
            self.db.commit()

        try:
            self.access.acquire()
        except SourceAccessUnavailable as e:
            task.status = PdfTaskStatus.QUEUED
            task.last_error = f"Access unavailable: {e}"
            task.last_error_category = "ACCESS_UNAVAILABLE"
            self.db.commit()
            return

        try:
            # 2. Check Idempotency (Skip download if artifact exists)
            pdf_bytes = None
            if task.artifact_id:
                try:
                    pdf_bytes = self.artifact_store.get(str(task.artifact_id))
                except Exception as e:
                    logger.warning(f"Could not retrieve existing artifact {task.artifact_id}: {e}")
            
            # 3. Download PDF if needed
            if not pdf_bytes:
                def ledger_callback(endpoint_name, start_time, duration_ms, status_code, size_bytes, error_cat, error_msg):
                    try:
                        ledger = SourceRequestLedger(
                            request_kind=RequestKind.PDF,
                            job_id=task.id,
                            endpoint=endpoint_name,
                            started_at=start_time,
                            completed_at=start_time + datetime.timedelta(milliseconds=duration_ms),
                            duration_ms=duration_ms,
                            http_status=status_code,
                            response_size_bytes=size_bytes,
                            failure_category=error_cat,
                            error_message=error_msg,
                            attempt_number=task.attempt_count
                        )
                        self.db.add(ledger)
                        self.db.commit()
                    except Exception as e:
                        print(f"FAILED LEDGER: {e}")
                        logger.error(f"Failed to write ledger: {e}")

                pdf_bytes = self.client.fetch_pdf(task.indexii_url, ledger_callback=ledger_callback)
                
                # Store Artifact
                artifact_id_str = self.artifact_store.save(
                    body=pdf_bytes,
                    content_type="application/pdf"
                )
                
                artifact_uuid = uuid.UUID(artifact_id_str)
                
                # Create Artifact DB record to satisfy foreign key constraints
                db_artifact = Artifact(
                    id=artifact_uuid,
                    artifact_type=ArtifactType.PDF_INDEXII,
                    storage_provider="LOCAL",
                    storage_path=f"storage/raw/{artifact_id_str}.pdf",
                    size_bytes=len(pdf_bytes),
                    content_type="application/pdf"
                )
                self.db.add(db_artifact)
                
                task.artifact_id = artifact_uuid
                self.db.commit()

                # Update the ledger with the new artifact_id
                last_ledger = self.db.query(SourceRequestLedger).filter(
                    SourceRequestLedger.job_id == task.id
                ).order_by(SourceRequestLedger.started_at.desc()).first()
                if last_ledger:
                    last_ledger.artifact_id = artifact_uuid
                    self.db.commit()
                
            # 4. Parsing
            parser_run = ParserRun(
                artifact_id=task.artifact_id,
                parser_name="PdfParser",
                parser_version="1.0"
            )
            self.db.add(parser_run)
            
            parsed_result = PdfParser.parse(pdf_bytes)
            
            parser_run.is_success = True
            self.db.commit()
            
            # 5. Persistence
            self.persistence.persist(str(task.registration_id), parsed_result)
            
            # 6. Completion
            task.status = PdfTaskStatus.PARSED
            task.completed_at = datetime.datetime.now(datetime.timezone.utc)
            self.db.commit()
            
        except Exception as e:
            self.db.rollback()
            # Re-fetch task to update status after rollback
            task = self.db.query(PdfTask).get(pdf_task_id)
            if not task:
                raise
                
            error_category = e.__class__.__name__
            task.last_error = str(e)[:500]
            task.last_error_category = error_category
            
            from app.scraper.domain.exceptions import IGRRateLimitError, IGRNetworkError, IGRUnexpectedResponseError
            
            if isinstance(e, IGRRateLimitError):
                self.access.report_rate_limited()
                self.access.recover()
                last_ledger = self.db.query(SourceRequestLedger).filter(
                    SourceRequestLedger.job_id == task.id
                ).order_by(SourceRequestLedger.started_at.desc()).first()
                if last_ledger:
                    last_ledger.rate_limited = True
                    
                from app.scraper.access.source_access_manager import AccessState
                if self.access.state == AccessState.AVAILABLE:
                    max_retries = 3
                    if (task.attempt_count or 1) <= max_retries:
                        task.status = PdfTaskStatus.QUEUED
                        task.last_error = f"Recovered from {e}. Requeuing."
                        task.last_error_category = "RATE_LIMITED_RECOVERED"
                    else:
                        task.status = PdfTaskStatus.FAILED
                        task.last_error = f"Recovered from {e} but max retries ({max_retries}) exceeded."
                        task.last_error_category = "RATE_LIMITED"
                else:
                    task.status = PdfTaskStatus.FAILED
                    task.last_error = f"Failed to recover from {e}. Failover unsuccessful."
                    task.last_error_category = "RATE_LIMITED"
                self.db.commit()
                
            elif isinstance(e, IGRNetworkError):
                self.access.report_network_error()
                self.access.recover()
                from app.scraper.access.source_access_manager import AccessState
                if self.access.state == AccessState.AVAILABLE:
                    max_retries = 3
                    if (task.attempt_count or 1) <= max_retries:
                        task.status = PdfTaskStatus.QUEUED
                        task.last_error = f"Recovered from {e}. Requeuing."
                        task.last_error_category = "NETWORK_RECOVERED"
                    else:
                        task.status = PdfTaskStatus.FAILED
                        task.last_error = f"Recovered from {e} but max retries ({max_retries}) exceeded."
                        task.last_error_category = "NETWORK_ERROR"
                else:
                    task.status = PdfTaskStatus.FAILED
                    task.last_error = f"Failed to recover from {e}. Failover unsuccessful."
                    task.last_error_category = "NETWORK_ERROR"
                self.db.commit()
                
            elif isinstance(e, IGRUnexpectedResponseError):
                if "404" in str(e):
                    task.status = PdfTaskStatus.FAILED # Permanent
                elif "Invalid URL" in str(e):
                    task.status = PdfTaskStatus.FAILED # Permanent
                else:
                    task.status = PdfTaskStatus.INVALID_PDF
                self.db.commit()
                
            else:
                task.status = PdfTaskStatus.FAILED
                import traceback
                traceback.print_exc()
                self.db.commit()
