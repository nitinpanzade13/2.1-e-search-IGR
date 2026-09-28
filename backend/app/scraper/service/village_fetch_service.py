import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple
import logging
import time
from sqlalchemy.orm import Session

from app.models.location import State, District, Taluka, Village
from app.models.village_fetch import VillageFetch, VillageFetchStatus
from app.scraper.client.igr_client import IgrSearchClient
from app.scraper.client.openai_captcha_solver import OpenAICaptchaSolver
from app.scraper.client.response_classifier import ResponseClassifier, ResponseClassification
from app.scraper.parser.html_parser import PureHtmlParser
from app.scraper.repository.record_details_repository import RecordDetailsRepository
from app.scraper.domain.dtos import SearchRequestDTO, SearchScopeDTO
from app.scraper.domain.exceptions import (
    IGRRateLimitError, IGRCaptchaError, IGRNetworkError, IGRValidationError, IGRSessionError
)
from app.scraper.access.simple_network import SimpleNetworkProvider

logger = logging.getLogger(__name__)

class VillageFetchService:
    def __init__(
        self,
        db: Session,
        client: Optional[IgrSearchClient] = None,
        solver: Optional[OpenAICaptchaSolver] = None,
        classifier: Optional[ResponseClassifier] = None,
        parser: Optional[PureHtmlParser] = None,
        repository: Optional[RecordDetailsRepository] = None,
    ):
        self.db = db
        self.client = client or IgrSearchClient()
        self.solver = solver or OpenAICaptchaSolver()
        self.classifier = classifier or ResponseClassifier()
        self.parser = parser or PureHtmlParser()
        self.repository = repository or RecordDetailsRepository(db)

    def validate_hierarchy(self, district_id: uuid.UUID, taluka_id: uuid.UUID, village_id: uuid.UUID) -> Tuple[District, Taluka, Village]:
        """
        Validates the strict geographic hierarchy:
        Village.taluka_id == supplied taluka_id AND Taluka.district_id == supplied district_id.
        Raises ValueError if invalid.
        """
        district = self.db.query(District).filter_by(id=district_id).first()
        if not district:
            raise ValueError(f"District {district_id} not found.")

        taluka = self.db.query(Taluka).filter_by(id=taluka_id).first()
        if not taluka:
            raise ValueError(f"Taluka {taluka_id} not found.")

        village = self.db.query(Village).filter_by(id=village_id).first()
        if not village:
            raise ValueError(f"Village {village_id} not found.")

        if taluka.district_id != district.id:
            raise ValueError(f"Taluka {taluka.name_en} does not belong to District {district.name_en}.")

        if village.taluka_id != taluka.id:
            raise ValueError(f"Village {village.name_en} does not belong to Taluka {taluka.name_en}.")

        return district, taluka, village

    def create_fetch(
        self,
        district_id: uuid.UUID,
        taluka_id: uuid.UUID,
        village_id: uuid.UUID,
        year: int,
        search_query: Optional[str] = None,
        survey_range_start: int = 1,
        survey_range_end: int = 100
    ) -> VillageFetch:
        # 1. Enforce hierarchy validation
        self.validate_hierarchy(district_id, taluka_id, village_id)

        # 2. Create minimal execution tracking record
        initial_search_val = (search_query or "").strip() or str(survey_range_start)
        fetch_run = VillageFetch(
            id=uuid.uuid4(),
            village_id=village_id,
            year=year,
            status=VillageFetchStatus.QUEUED.value,
            survey_range_start=survey_range_start,
            survey_range_end=survey_range_end,
            current_search_value=initial_search_val,
            processed_search_count=0,
            records_found=0,
            unique_records_saved=0,
            duplicates_skipped=0,
            truncated_searches_count=0,
            errors_count=0,
            created_at=datetime.now(timezone.utc)
        )
        self.db.add(fetch_run)
        self.db.commit()
        self.db.refresh(fetch_run)
        return fetch_run

    def execute_fetch(self, fetch_id: uuid.UUID, search_values: Optional[List[str]] = None) -> VillageFetch:
        logger.info(f"[VillageFetchService] Starting execute_fetch for fetch_id: {fetch_id}")
        
        fetch_run = self.db.query(VillageFetch).filter_by(id=fetch_id).first()
        if not fetch_run:
            logger.error(f"[VillageFetchService] VillageFetch {fetch_id} not found.")
            raise ValueError(f"VillageFetch {fetch_id} not found.")

        logger.info(f"[VillageFetchService] Found fetch_run: {fetch_run.id}, status: {fetch_run.status}, village_id: {fetch_run.village_id}")

        village = self.db.query(Village).filter_by(id=fetch_run.village_id).first()
        if not village:
            logger.error(f"[VillageFetchService] Village {fetch_run.village_id} not found for fetch {fetch_id}")
            fetch_run.status = VillageFetchStatus.FAILED.value
            fetch_run.last_error = f"Village {fetch_run.village_id} not found."
            self.db.commit()
            return fetch_run

        taluka = self.db.query(Taluka).filter_by(id=village.taluka_id).first()
        district = self.db.query(District).filter_by(id=taluka.district_id).first() if taluka else None
        if not taluka or not district:
            logger.error(f"[VillageFetchService] Location hierarchy could not be resolved for village {village.id}, taluka: {taluka}, district: {district}")
            fetch_run.status = VillageFetchStatus.FAILED.value
            fetch_run.last_error = "Location hierarchy could not be resolved from database."
            self.db.commit()
            return fetch_run

        logger.info(f"[VillageFetchService] Resolved hierarchy: District={district.name_en}, Taluka={taluka.name_en}, Village={village.name_en}")

        # Transition to RUNNING
        fetch_run.status = VillageFetchStatus.RUNNING.value
        fetch_run.started_at = datetime.now(timezone.utc)
        self.db.commit()
        logger.info(f"[VillageFetchService] Fetch marked as RUNNING, started_at: {fetch_run.started_at}")

        # Build search values list (default 1 to 100 sequentially)
        if not search_values:
            start_num = fetch_run.survey_range_start or 1
            end_num = fetch_run.survey_range_end or 100
            search_values = [str(i) for i in range(start_num, end_num + 1)]
            logger.info(f"[VillageFetchService] Generated survey range: {start_num} to {end_num} ({len(search_values)} surveys)")
        else:
            logger.info(f"[VillageFetchService] Using provided search_values list: {len(search_values)} items")

        # Scope DTO using source IDs for IGR integration boundary
        scope_dto = SearchScopeDTO(
            district_id=district.source_id,
            taluka_id=taluka.source_id,
            village_id=village.source_id,
            district_name=district.name_en or "",
            taluka_name=taluka.name_en or "",
            village_name=village.name_en or "",
            article_id="",
            article_name=""
        )
        logger.debug(f"[VillageFetchService] Created scope_dto: district_id={scope_dto.district_id}, taluka_id={scope_dto.taluka_id}, village_id={scope_dto.village_id}")

        total_surveys = len(search_values)
        logger.info(f"[VillageFetchService] Starting processing of {total_surveys} surveys")

        for idx, val in enumerate(search_values, 1):
            # Check lifecycle states (pause/cancel)
            self.db.refresh(fetch_run)
            if fetch_run.status in (VillageFetchStatus.PAUSED.value, VillageFetchStatus.CANCELLED.value):
                logger.info(f"[VillageFetchService] VillageFetch {fetch_id} interrupted by state {fetch_run.status}")
                return fetch_run

            fetch_run.current_search_value = str(val)
            self.db.commit()
            
            logger.info(f"[VillageFetchService] Processing survey {idx}/{total_surveys}: {val}")

            req_dto = SearchRequestDTO(
                year=fetch_run.year,
                survey_query=str(val),
                location=scope_dto,
                article_id="",
                article_name=""
            )
            logger.debug(f"[VillageFetchService] Created SearchRequestDTO: year={req_dto.year}, survey_query={req_dto.survey_query}")

            try:
                # Execute IGR search with retries for captcha failure
                max_captcha_retries = 3
                raw_resp = None
                logger.debug(f"[VillageFetchService] Starting IGR search for survey {val}")
                
                for attempt in range(max_captcha_retries):
                    try:
                        raw_resp = self.client.search(req_dto, self.solver)
                        classification = self.classifier.classify(raw_resp)
                        logger.debug(f"[VillageFetchService] Survey {val} attempt {attempt+1}: classification={classification}")
                        
                        if classification == ResponseClassification.CAPTCHA_FAILED:
                            if attempt < max_captcha_retries - 1:
                                logger.warning(f"[VillageFetchService] Survey {val} CAPTCHA failed, retrying ({attempt+1}/{max_captcha_retries})")
                                continue
                            else:
                                logger.error(f"[VillageFetchService] Survey {val} max CAPTCHA retries ({max_captcha_retries}) exceeded")
                                raise IGRCaptchaError("Max CAPTCHA retries exceeded")
                        elif classification == ResponseClassification.RATE_LIMITED:
                            logger.warning(f"[VillageFetchService] Survey {val} rate limited detected")
                            
                            # Try network switching before giving up
                            try:
                                network_provider = SimpleNetworkProvider()
                                logger.info(f"[VillageFetchService] Attempting network switch for survey {val} due to rate limit...")
                                
                                if network_provider.change_context():
                                    logger.info(f"[VillageFetchService] Network switched successfully for survey {val}. Resetting session and retrying...")
                                    # Reset client session after network switch
                                    self.client.reset_session()
                                    # Continue to next iteration to retry with new network
                                    continue
                                else:
                                    logger.error(f"[VillageFetchService] Network switch failed for survey {val}")
                                    raise IGRRateLimitError("Daily search limit exceeded and network switch failed")
                            except Exception as switch_error:
                                logger.error(f"[VillageFetchService] Network switching error for survey {val}: {switch_error}")
                                raise IGRRateLimitError("Daily search limit exceeded")
                        break
                        break
                    except IGRCaptchaError as e:
                        if attempt < max_captcha_retries - 1:
                            logger.warning(f"[VillageFetchService] Survey {val} CAPTCHA error, retrying: {e}")
                            continue
                        raise

                if not raw_resp:
                    logger.error(f"[VillageFetchService] No response received from IGR client for survey {val}")
                    raise RuntimeError("No response received from IGR client")

                logger.debug(f"[VillageFetchService] Received response for survey {val}, parsing HTML")

                # Parse Record Details HTML table
                parsed_resp = self.parser.parse(
                    html_bytes=raw_resp.body,
                    year=req_dto.year,
                    survey_query=req_dto.survey_query,
                    scope=scope_dto
                )

                logger.debug(f"[VillageFetchService] Parsed response: retrieved_count={parsed_resp.retrieved_count}, reported_count={parsed_resp.reported_count}")

                # Check if this search hit 5,000 truncation cap
                is_truncated = bool(
                    parsed_resp.truncated or 
                    (parsed_resp.reported_count and parsed_resp.reported_count >= 5000) or
                    parsed_resp.retrieved_count >= 5000
                )
                if is_truncated:
                    fetch_run.truncated_searches_count += 1
                    logger.warning(f"[VillageFetchService] Survey {val} returned {parsed_resp.retrieved_count} rows and is TRUNCATED (capped at 5000). Continuing workflow.")

                logger.info(f"[VillageFetchService] Saving {parsed_resp.retrieved_count} records for survey {val}")
                
                # Persist ALL returned rows into record_details with deduplication across all queries
                saved, dups = self.repository.save_records(
                    village_id=fetch_run.village_id,
                    records=parsed_resp.results,
                    is_truncated=is_truncated,
                    reported_count=parsed_resp.reported_count
                )

                fetch_run.processed_search_count += 1
                fetch_run.records_found += parsed_resp.retrieved_count
                fetch_run.unique_records_saved += saved
                fetch_run.duplicates_skipped += dups
                self.db.commit()

                logger.info(f"[VillageFetchService] Survey {val} completed. Progress: {fetch_run.processed_search_count}/{total_surveys} surveys processed. Records: saved={saved}, duplicates={dups}, total_found={fetch_run.records_found}, unique_saved={fetch_run.unique_records_saved}")

            except IGRRateLimitError as rate_limit_error:
                logger.warning(f"[VillageFetchService] Survey {val} rate limited: {rate_limit_error}")
                
                # Try network switching before marking as error
                try:
                    network_provider = SimpleNetworkProvider()
                    logger.info(f"[VillageFetchService] Attempting network switch for survey {val} due to rate limit...")
                    
                    if network_provider.change_context():
                        logger.info(f"[VillageFetchService] Network switched successfully for survey {val}. Resetting session...")
                        # Reset client session after network switch
                        self.client.reset_session()
                        logger.info(f"[VillageFetchService] Session reset. Will continue with next survey.")
                        
                        # Don't mark this as an error since we switched network
                        # Just log and continue to next survey
                        fetch_run.processed_search_count += 1
                        self.db.commit()
                        logger.info(f"[VillageFetchService] Survey {val} skipped after network switch. Will try next survey with new IP.")
                    else:
                        logger.error(f"[VillageFetchService] Network switch failed for survey {val}")
                        fetch_run.errors_count += 1
                        fetch_run.last_error = str(rate_limit_error)
                        fetch_run.processed_search_count += 1
                        self.db.commit()
                        logger.warning(f"[VillageFetchService] Survey {val} marked as error (network switch failed). Errors count: {fetch_run.errors_count}")
                        
                except Exception as switch_error:
                    logger.error(f"[VillageFetchService] Network switching error for survey {val}: {switch_error}")
                    fetch_run.errors_count += 1
                    fetch_run.last_error = f"{rate_limit_error} [Network switch failed: {switch_error}]"
                    fetch_run.processed_search_count += 1
                    self.db.commit()
                    logger.warning(f"[VillageFetchService] Survey {val} marked as error. Errors count: {fetch_run.errors_count}")
                    
            except Exception as e:
                logger.error(f"[VillageFetchService] Error during survey {val} ({idx}/{total_surveys}) in VillageFetch {fetch_id}: {str(e)}", exc_info=True)
                fetch_run.errors_count += 1
                fetch_run.last_error = str(e)
                fetch_run.processed_search_count += 1
                self.db.commit()
                logger.warning(f"[VillageFetchService] Survey {val} marked as error. Errors count: {fetch_run.errors_count}")

        # Finished sequence: mark completed or partial according to actual results
        self.db.refresh(fetch_run)
        logger.info(f"[VillageFetchService] All surveys processed. Final status check: status={fetch_run.status}, processed={fetch_run.processed_search_count}, errors={fetch_run.errors_count}, truncated={fetch_run.truncated_searches_count}")
        
        if fetch_run.status == VillageFetchStatus.RUNNING.value:
            if fetch_run.truncated_searches_count > 0 or fetch_run.errors_count > 0:
                fetch_run.status = VillageFetchStatus.PARTIAL.value
                logger.info(f"[VillageFetchService] Marking as PARTIAL due to truncations={fetch_run.truncated_searches_count} or errors={fetch_run.errors_count}")
            else:
                fetch_run.status = VillageFetchStatus.COMPLETED.value
                logger.info(f"[VillageFetchService] Marking as COMPLETED")
            fetch_run.completed_at = datetime.now(timezone.utc)
            self.db.commit()

        logger.info(f"[VillageFetchService] Fetch {fetch_id} finished with status: {fetch_run.status}")
        return fetch_run

    def pause_fetch(self, fetch_id: uuid.UUID) -> bool:
        fetch_run = self.db.query(VillageFetch).filter_by(id=fetch_id).first()
        if fetch_run and fetch_run.status == VillageFetchStatus.RUNNING.value:
            fetch_run.status = VillageFetchStatus.PAUSED.value
            self.db.commit()
            return True
        return False

    def resume_fetch(self, fetch_id: uuid.UUID) -> bool:
        fetch_run = self.db.query(VillageFetch).filter_by(id=fetch_id).first()
        if fetch_run and fetch_run.status == VillageFetchStatus.PAUSED.value:
            fetch_run.status = VillageFetchStatus.QUEUED.value
            self.db.commit()
            return True
        return False

    def cancel_fetch(self, fetch_id: uuid.UUID) -> bool:
        fetch_run = self.db.query(VillageFetch).filter_by(id=fetch_id).first()
        if fetch_run and fetch_run.status in (VillageFetchStatus.QUEUED.value, VillageFetchStatus.RUNNING.value, VillageFetchStatus.PAUSED.value):
            fetch_run.status = VillageFetchStatus.CANCELLED.value
            self.db.commit()
            return True
        return False
