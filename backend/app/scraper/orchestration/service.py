import uuid
import logging
from sqlalchemy.orm import Session
from sqlalchemy import func, Integer
from app.models.job import BulkFetchJob, SearchJob
from app.models.enums import BulkFetchJobStatus, SearchJobStatus, CoverageStatus

logger = logging.getLogger(__name__)

class BulkFetchService:
    def __init__(self, db: Session):
        self.db = db

    def aggregate_progress(self, bulk_job_id: uuid.UUID):
        bulk_job = self.db.query(BulkFetchJob).get(bulk_job_id)
        if not bulk_job:
            return

        if bulk_job.status in (BulkFetchJobStatus.CANCELLED, BulkFetchJobStatus.FAILED):
            return

        stats = self.db.query(
            SearchJob.status,
            SearchJob.coverage_status,
            func.count(SearchJob.id),
            func.coalesce(func.sum(SearchJob.requested_count), 0),
            func.coalesce(func.sum(SearchJob.retrieved_count), 0)
        ).filter(SearchJob.bulk_fetch_job_id == bulk_job.id).group_by(SearchJob.status, SearchJob.coverage_status).all()

        total = 0
        queued = 0
        running = 0
        completed = 0
        failed = 0
        truncated = 0
        rate_limited = 0
        paused = 0

        tot_req = 0
        tot_ret = 0

        for st, cov_st, count, req, ret in stats:
            total += count
            if req: tot_req += req
            if ret: tot_ret += ret
            
            if st == SearchJobStatus.QUEUED:
                queued += count
            elif st == SearchJobStatus.RUNNING:
                running += count
            elif st == SearchJobStatus.COMPLETED:
                completed += count
            elif st == SearchJobStatus.FAILED:
                failed += count
            elif st == SearchJobStatus.RATE_LIMITED:
                rate_limited += count
            elif st == SearchJobStatus.PAUSED:
                paused += count
                
            # Legacy fallback if st == TRUNCATED
            if st == SearchJobStatus.TRUNCATED or cov_st == CoverageStatus.TRUNCATED:
                truncated += count

        bulk_job.total_units = total
        bulk_job.queued_units = queued
        bulk_job.running_units = running
        bulk_job.completed_units = completed
        bulk_job.failed_units = failed
        bulk_job.truncated_units = truncated
        bulk_job.rate_limited_units = rate_limited
        bulk_job.paused_units = paused
        
        bulk_job.total_records_reported = tot_req
        bulk_job.total_records_retrieved = tot_ret

        # Determine Bulk Job Status (Execution Status)
        if bulk_job.status == BulkFetchJobStatus.RUNNING:
            if rate_limited > 0:
                bulk_job.status = BulkFetchJobStatus.RATE_LIMITED
            elif queued == 0 and running == 0:
                if failed > 0:
                    if completed == 0:
                        bulk_job.status = BulkFetchJobStatus.FAILED
                    else:
                        bulk_job.status = BulkFetchJobStatus.PARTIAL
                else:
                    bulk_job.status = BulkFetchJobStatus.COMPLETED

        # Determine Coverage Status
        if queued == 0 and running == 0:
            if truncated > 0:
                bulk_job.coverage_status = CoverageStatus.TRUNCATED
            elif failed > 0 or rate_limited > 0 or total == 0:
                bulk_job.coverage_status = CoverageStatus.PARTIAL
            else:
                bulk_job.coverage_status = CoverageStatus.COMPLETE
        else:
            bulk_job.coverage_status = CoverageStatus.UNKNOWN

        self.db.commit()

    def pause_job(self, bulk_job_id: uuid.UUID):
        bulk_job = self.db.query(BulkFetchJob).get(bulk_job_id)
        if bulk_job and bulk_job.status in (BulkFetchJobStatus.RUNNING, BulkFetchJobStatus.RATE_LIMITED, BulkFetchJobStatus.QUEUED, BulkFetchJobStatus.PLANNING):
            bulk_job.status = BulkFetchJobStatus.PAUSED
            
            self.db.query(SearchJob).filter(
                SearchJob.bulk_fetch_job_id == bulk_job_id,
                SearchJob.status == SearchJobStatus.QUEUED
            ).update({"status": SearchJobStatus.PAUSED}, synchronize_session=False)
            
            self.db.commit()
            return True
        return False

    def resume_job(self, bulk_job_id: uuid.UUID):
        bulk_job = self.db.query(BulkFetchJob).get(bulk_job_id)
        if bulk_job and bulk_job.status in (BulkFetchJobStatus.PAUSED, BulkFetchJobStatus.RATE_LIMITED, BulkFetchJobStatus.PARTIAL, BulkFetchJobStatus.FAILED):
            bulk_job.status = BulkFetchJobStatus.RUNNING
            
            self.db.query(SearchJob).filter(
                SearchJob.bulk_fetch_job_id == bulk_job_id,
                SearchJob.status.in_([SearchJobStatus.PAUSED, SearchJobStatus.RATE_LIMITED])
            ).update({"status": SearchJobStatus.QUEUED, "attempt_count": 0}, synchronize_session=False)

            non_retryable_categories = [
                "VALIDATION_ERROR",
                "UNEXPECTED_RESPONSE_ERROR",
                "UNEXPECTED_CLASSIFICATION",
                "INTERNAL_ERROR",
                "PARSER_ERROR",
                "PERSISTENCE_ERROR"
            ]
            self.db.query(SearchJob).filter(
                SearchJob.bulk_fetch_job_id == bulk_job_id,
                SearchJob.status == SearchJobStatus.FAILED,
                SearchJob.last_error_category.notin_(non_retryable_categories)
            ).update({"status": SearchJobStatus.QUEUED, "attempt_count": 0}, synchronize_session=False)
            
            self.db.commit()
            return True
        return False

    def cancel_job(self, bulk_job_id: uuid.UUID):
        bulk_job = self.db.query(BulkFetchJob).get(bulk_job_id)
        if bulk_job and bulk_job.status not in (BulkFetchJobStatus.COMPLETED, BulkFetchJobStatus.CANCELLED):
            bulk_job.status = BulkFetchJobStatus.CANCELLED
            
            self.db.query(SearchJob).filter(
                SearchJob.bulk_fetch_job_id == bulk_job_id,
                SearchJob.status.in_([SearchJobStatus.QUEUED, SearchJobStatus.PAUSED, SearchJobStatus.RATE_LIMITED])
            ).update({"status": SearchJobStatus.CANCELLED}, synchronize_session=False)
            
            self.db.commit()
            return True
        return False
