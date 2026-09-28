import uuid
import datetime
import logging
from sqlalchemy.orm import Session
from app.scraper.domain.dtos import SearchRequestDTO, SearchScopeDTO
from app.scraper.domain.exceptions import (
    IGRNetworkError,
    IGRSessionError,
    IGRCaptchaError,
    IGRUnexpectedResponseError,
    IGRValidationError,
    IGRRateLimitError,
    SourceAccessUnavailable,
    IdentityResolutionError
)
from app.models.location import State, District, Taluka, Village
from app.models.ledger import SourceRequestLedger
from app.models.job import SearchJob, PdfTask, BulkFetchJob, SearchJobRegistration
from app.models.artifact import Artifact
from app.models.processing import ParserRun
from app.models.enums import SearchJobStatus, PdfTaskStatus, CoverageStatus, RequestKind, ArtifactType
from app.scraper.access.source_access_manager import SourceAccessManager
from app.scraper.client.igr_client import IgrSearchClient
from app.scraper.client.captcha import CaptchaSolver
from app.scraper.client.response_classifier import ResponseClassifier, ResponseClassification
from app.scraper.storage.artifact_store import ArtifactStore
from app.scraper.parser.html_parser import PureHtmlParser
from app.scraper.identity.resolver import IdentityResolver
from app.scraper.identity.persistence import RegistrationPersistenceService
from app.scraper.identity.models import ResolutionOutcome

logger = logging.getLogger(__name__)

class SearchWorker:
    def __init__(
        self,
        db_session: Session,
        access_manager: SourceAccessManager,
        client: IgrSearchClient,
        captcha_solver: CaptchaSolver,
        classifier: ResponseClassifier,
        artifact_store: ArtifactStore,
        parser: PureHtmlParser,
        identity_resolver: IdentityResolver,
        persistence_service: RegistrationPersistenceService
    ):
        self.db = db_session
        self.access = access_manager
        self.client = client
        self.captcha_solver = captcha_solver
        self.classifier = classifier
        self.artifact_store = artifact_store
        self.parser = parser
        self.identity_resolver = identity_resolver
        self.persistence = persistence_service

    def execute(self, search_job_id: uuid.UUID):
        # 1. Admission
        try:
            self.access.acquire()
        except SourceAccessUnavailable as e:
            # Denied before HTTP attempt
            job = self.db.query(SearchJob).get(search_job_id)
            if job:
                job.status = SearchJobStatus.PAUSED
                job.last_error = str(e)
                job.last_error_category = "SOURCE_ACCESS_UNAVAILABLE"
                self.db.commit()
                self._aggregate_parent(job)
            return
        except Exception as e:
            import traceback
            traceback.print_exc()
            job = self.db.query(SearchJob).get(search_job_id)
            if job:
                job.status = SearchJobStatus.FAILED
                job.last_error = str(e)
                try:
                    job.last_error_category = "SYSTEM_ERROR"
                except Exception:
                    pass
                self.db.commit()
                self._aggregate_parent(job)
            return
            
        job = self.db.query(SearchJob).get(search_job_id)
        if not job:
            return
            
        if job.bulk_fetch_job_id:
            from app.models.job import BulkFetchJob
            from app.models.enums import BulkFetchJobStatus
            bulk_job = self.db.query(BulkFetchJob).get(job.bulk_fetch_job_id)
            if not bulk_job:
                logger.warning(f"Skipping SearchJob {job.id}: parent BulkFetchJob {job.bulk_fetch_job_id} not found")
                return
            if bulk_job.status != BulkFetchJobStatus.RUNNING:
                logger.warning(f"Skipping SearchJob {job.id}: parent BulkFetchJob {bulk_job.id} is {bulk_job.status.name}")
                return
            
        job.status = SearchJobStatus.RUNNING
        job.started_at = datetime.datetime.now(datetime.timezone.utc)
        job.attempt_count = (job.attempt_count or 0) + 1
        self.db.commit()
        
        from app.models.location import State, District, Taluka, Village
        
        dist_id = job.location_params.get("district_id")
        tal_id = job.location_params.get("taluka_id")
        vill_id = job.location_params.get("village_id")
        
        try:
            state = self.db.query(State).filter_by(
                source_system="IGR_MAHARASHTRA", 
                source_id="27"
            ).first()
            
            district = self.db.query(District).filter_by(
                source_system="IGR_MAHARASHTRA",
                state_id=state.id if state else None,
                source_id=dist_id
            ).first()
            taluka = self.db.query(Taluka).filter_by(source_id=tal_id, district_id=district.id if district else None).first()
            village = self.db.query(Village).filter_by(source_id=vill_id, taluka_id=taluka.id if taluka else None).first()
            
            if not district or not taluka or not village:
                raise ValueError(f"Location IDs not found in database: dist={dist_id}, tal={tal_id}, vill={vill_id}")
                
            d_name = (district.name_en or "").strip()
            t_name = (taluka.name_en or "").strip()
            v_name = (village.name_en or "").strip()
            
            if not d_name or not t_name or not v_name:
                raise ValueError(f"Missing required IGR source name (name_en) for location: dist={d_name}, tal={t_name}, vill={v_name}")
                
            request_dto = SearchRequestDTO(
                year=job.year,
                survey_query=job.survey_prefix or "",
                location=SearchScopeDTO(
                    district_id=dist_id,
                    taluka_id=tal_id,
                    village_id=vill_id,
                    district_name=d_name,
                    taluka_name=t_name,
                    village_name=v_name
                )
            )
        except ValueError as e:
            self._handle_terminal_error(job, "VALIDATION_ERROR", str(e), retryable=False)
            return
        
        def ledger_callback(endpoint_name, start_time, duration_ms, status_code, size_bytes, error_cat, error_msg):
            try:
                ledger = SourceRequestLedger(
                    request_kind=RequestKind.SEARCH,
                    job_id=job.id,
                    endpoint=endpoint_name,
                    started_at=start_time,
                    completed_at=start_time + datetime.timedelta(milliseconds=duration_ms),
                    duration_ms=duration_ms,
                    http_status=status_code,
                    response_size_bytes=size_bytes,
                    failure_category=error_cat,
                    error_message=error_msg,
                    network_context={"context_id": self.access.current_context}
                )
                # Ensure we don't throw away ledger history
                self.db.add(ledger)
                self.db.commit()
            except Exception as e:
                self.db.rollback()
                logger.error(f"Failed to write ledger for {endpoint_name}: {e}")
                raise RuntimeError(f"Ledger persistence failed: {e}") from e

        # 2. Search Request
        try:
            raw_resp = self.client.search(request_dto, self.captcha_solver, ledger_callback=ledger_callback)
        except IGRRateLimitError as e:
            self._handle_rate_limit(job, str(e))
            return
        except IGRCaptchaError as e:
            self._handle_terminal_error(job, "CAPTCHA_ERROR", str(e), e.retryable)
            return
        except IGRNetworkError as e:
            self.access.report_network_error()
            self.access.recover()
            self.client.reset_session()
            # Must import AccessState if not already imported
            from app.scraper.access.source_access_manager import AccessState
            if self.access.state == AccessState.AVAILABLE:
                max_retries = 3
                if (job.attempt_count or 1) <= max_retries:
                    self._handle_terminal_error(job, "NETWORK_RECOVERED", f"Recovered from {e}. Requeuing.", True)
                else:
                    self._handle_terminal_error(job, "NETWORK_ERROR", f"Recovered from {e} but max retries ({max_retries}) exceeded.", False)
            else:
                self._handle_terminal_error(job, "NETWORK_ERROR", f"Failed to recover from {e}. Failover unsuccessful.", False)
            return
        except IGRValidationError as e:
            self._handle_terminal_error(job, "VALIDATION_ERROR", str(e), e.retryable)
            return
        except IGRSessionError as e:
            self._handle_terminal_error(job, "SESSION_ERROR", str(e), e.retryable)
            return
        except IGRUnexpectedResponseError as e:
            self._handle_terminal_error(job, "UNEXPECTED_RESPONSE_ERROR", str(e), e.retryable)
            return
        except RuntimeError as e:
            if "Ledger persistence failed" in str(e):
                self._handle_terminal_error(job, "LEDGER_PERSISTENCE_ERROR", str(e), True)
            else:
                self._handle_terminal_error(job, "INTERNAL_ERROR", str(e), False)
            return
        except Exception as e:
            self._handle_terminal_error(job, "INTERNAL_ERROR", str(e), False)
            return
            
        # 4. Raw Artifact Persistence
        try:
            artifact_id_str = self.artifact_store.save(
                body=raw_resp.body,
                content_type=raw_resp.content_type or "text/html"
            )
            artifact_uuid = uuid.UUID(artifact_id_str)
            
            db_artifact = Artifact(
                id=artifact_uuid,
                artifact_type=ArtifactType.HTML_SEARCH,
                storage_provider="LOCAL",
                storage_path=f"storage/raw/{artifact_id_str}.html",
                size_bytes=len(raw_resp.body),
                content_type=raw_resp.content_type or "text/html"
            )
            self.db.add(db_artifact)
            
            # Update the last ledger entry with the artifact ID, since we saved it
            last_ledger = self.db.query(SourceRequestLedger).filter(
                SourceRequestLedger.job_id == job.id
            ).order_by(SourceRequestLedger.started_at.desc()).first()
            if last_ledger:
                last_ledger.artifact_id = artifact_uuid
                self.db.commit()
        except Exception as e:
            self._handle_terminal_error(job, "ARTIFACT_STORAGE_ERROR", str(e), True)
            return
            
        # 3. Response Classification
        classification = self.classifier.classify(raw_resp)
        if classification == ResponseClassification.RATE_LIMITED:
            self._handle_rate_limit(job, "RATE_LIMITED classified")
            return
        elif classification == ResponseClassification.CAPTCHA_FAILED:
            self._handle_terminal_error(job, "CAPTCHA_ERROR", "Captcha classified failure", True)
            return
        elif classification == ResponseClassification.VALIDATION_ERROR:
            self._handle_terminal_error(job, "VALIDATION_ERROR", "Validation classified failure", False)
            return
        elif classification == ResponseClassification.AUTH_SESSION_ERROR:
            self._handle_terminal_error(job, "SESSION_ERROR", "Auth/Session classified failure", True)
            return
        elif classification == ResponseClassification.NETWORK_ERROR:
            self._handle_terminal_error(job, "NETWORK_ERROR", "Network classified failure", True)
            return
        elif classification == ResponseClassification.UNEXPECTED_RESPONSE:
            self._handle_terminal_error(job, "UNEXPECTED_RESPONSE_ERROR", "Unrecognized HTML", False)
            return
        elif classification != ResponseClassification.SUCCESS:
            self._handle_terminal_error(job, "UNEXPECTED_CLASSIFICATION", f"Unknown classification: {classification}", False)
            return
            
        # 5. HTML Parsing (preserve artifact order)
        parser_run = ParserRun(
            artifact_id=artifact_uuid,
            parser_name="PureHtmlParser",
            parser_version="1.0"
        )
        self.db.add(parser_run)
        
        try:
            # 5. Parse HTML to domain entity
            scope = SearchScopeDTO(
                district_name=job.location_params.get("district_id", ""),
                taluka_name=job.location_params.get("taluka_id", ""),
                village_name=job.location_params.get("village_id", "")
            )
            parsed_result = self.parser.parse(raw_resp.body, request_dto.year, request_dto.survey_query, scope)
            parser_run.is_success = True
            self.db.commit()
        except Exception as e:
            parser_run.is_success = False
            parser_run.error_message = str(e)
            self.db.commit()
            
            job.status = SearchJobStatus.FAILED
            job.last_error = f"Parser Error: {str(e)}"
            job.last_error_category = "PARSER_ERROR"
            self.db.commit()
            self._aggregate_parent(job)
            return
            
        # 6. Truncation and Meta handling
        job.retrieved_count = parsed_result.retrieved_count
        job.requested_count = parsed_result.reported_count
        job.truncated = parsed_result.truncated
        self.db.commit()
        
        # 7. Identity + Registration Persistence
        unexpected_persistence_errors = 0
        skipped_ambiguous_count = 0
        skipped_possible_duplicate_count = 0
        
        import time
        start_t = time.time()
        count = 0
        
        for parsed_row in parsed_result.results:
            count += 1
            if count % 100 == 0:
                print(f"Resolving row {count} / {len(parsed_result.results)}")
                
            decision = self.identity_resolver.resolve(parsed_row)
            
            # Observe ambiguous decisions safely
            if decision.outcome == ResolutionOutcome.AMBIGUOUS:
                skipped_ambiguous_count += 1
                logger.warning(f"Row skipped due to AMBIGUOUS identity: {parsed_row.doc_no}")
            elif decision.outcome == ResolutionOutcome.POSSIBLE_DUPLICATE:
                skipped_possible_duplicate_count += 1
                logger.warning(f"Row skipped due to POSSIBLE_DUPLICATE identity: {parsed_row.doc_no}")
                
            try:
                reg = self.persistence.persist(parsed_row, decision)
                self.db.commit() # Individual commit for successful persistence
                
                if reg:
                    # 7b. Create provenance link
                    existing_link = self.db.query(SearchJobRegistration).filter(
                        SearchJobRegistration.search_job_id == job.id,
                        SearchJobRegistration.registration_id == reg.id
                    ).first()
                    if not existing_link:
                        link = SearchJobRegistration(
                            search_job_id=job.id,
                            registration_id=reg.id
                        )
                        self.db.add(link)
                        self.db.commit()

                # 8. PDF TASK CREATION
                if reg and reg.indexii_url:
                    existing_task = self.db.query(PdfTask).filter(
                        PdfTask.registration_id == reg.id,
                        PdfTask.indexii_url == reg.indexii_url
                    ).first()
                    if not existing_task:
                        pdf_task = PdfTask(
                            registration_id=reg.id,
                            indexii_url=reg.indexii_url,
                            source_token=reg.source_token or reg.indexii_url
                        )
                        self.db.add(pdf_task)
                        self.db.commit() # Individual commit for PDF task
            except IdentityResolutionError as e:
                # Deliberate failure raised by persistence (e.g. for ambiguous row)
                self.db.rollback()
                logger.warning(f"Persistence rejected identity for row: {e}")
            except Exception as e:
                # Unexpected persistence failure (e.g. DB error)
                self.db.rollback()
                logger.error(f"Unexpected persistence error: {e}")
                unexpected_persistence_errors += 1
                
        # Final outcome logic
        if unexpected_persistence_errors > 0:
            job.status = SearchJobStatus.FAILED
            job.coverage_status = CoverageStatus.UNKNOWN
            job.last_error = f"{unexpected_persistence_errors} rows failed to persist unexpectedly."
            job.last_error_category = "PERSISTENCE_ERROR"
        else:
            job.status = SearchJobStatus.COMPLETED
            if job.truncated:
                job.coverage_status = CoverageStatus.TRUNCATED
            else:
                job.coverage_status = CoverageStatus.COMPLETE
            
        # Log skipped counts
        if skipped_ambiguous_count > 0 or skipped_possible_duplicate_count > 0:
            logger.info(f"Job {job.id} skipped {skipped_ambiguous_count} AMBIGUOUS and {skipped_possible_duplicate_count} POSSIBLE_DUPLICATE rows.")
            
        job.completed_at = datetime.datetime.now(datetime.timezone.utc)
        self.db.commit()
        self._aggregate_parent(job)


    def _handle_terminal_error(self, job, category, error_msg, retryable):
        max_retries = 3
        if retryable and (job.attempt_count or 1) <= max_retries:
            job.status = SearchJobStatus.QUEUED
        else:
            job.status = SearchJobStatus.FAILED
        job.coverage_status = CoverageStatus.UNKNOWN
        job.last_error = error_msg
        job.last_error_category = category
        self.db.commit()
        self._aggregate_parent(job)
        
    def _handle_rate_limit(self, job, error_msg):
        self.access.report_rate_limited()
        self.access.recover()
        self.client.reset_session()
        
        # update last ledger explicitly marking rate_limited
        last_ledger = self.db.query(SourceRequestLedger).filter(
            SourceRequestLedger.job_id == job.id
        ).order_by(SourceRequestLedger.started_at.desc()).first()
        if last_ledger:
            last_ledger.rate_limited = True
            
        from app.scraper.access.source_access_manager import AccessState
        if self.access.state == AccessState.AVAILABLE:
            max_retries = 3
            if (job.attempt_count or 1) <= max_retries:
                job.status = SearchJobStatus.QUEUED
                job.coverage_status = CoverageStatus.UNKNOWN
                job.last_error = f"Recovered from rate limit. Requeuing."
                job.last_error_category = "RATE_LIMITED_RECOVERED"
            else:
                job.status = SearchJobStatus.RATE_LIMITED
                job.coverage_status = CoverageStatus.PARTIAL
                job.last_error = f"Recovered from rate limit but max retries ({max_retries}) exceeded."
                job.last_error_category = "RATE_LIMITED"
        else:
            job.status = SearchJobStatus.RATE_LIMITED
            job.coverage_status = CoverageStatus.PARTIAL
            job.last_error = f"Failed to recover from rate limit. Failover unsuccessful."
            job.last_error_category = "RATE_LIMITED"
            
        self.db.commit()
        self._aggregate_parent(job)

    def _aggregate_parent(self, job):
        if job.bulk_fetch_job_id:
            from app.scraper.orchestration.service import BulkFetchService
            try:
                BulkFetchService(self.db).aggregate_progress(job.bulk_fetch_job_id)
            except Exception as e:
                logger.error(f"Failed to aggregate parent {job.bulk_fetch_job_id}: {e}")
