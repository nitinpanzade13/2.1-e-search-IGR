import uuid
import logging
from typing import List, Dict, Any, Callable
from sqlalchemy.orm import Session
from app.models.job import BulkFetchJob, SearchJob
from app.models.enums import ScopeType, BulkFetchJobStatus
from app.models.location import State, District, Taluka, Village

logger = logging.getLogger(__name__)

class BulkFetchPlanner:
    def __init__(self, db: Session):
        self.db = db

    def plan_jobs(self, bulk_job_id: uuid.UUID):
        bulk_job = self.db.query(BulkFetchJob).get(bulk_job_id)
        if not bulk_job:
            return

        if bulk_job.status != BulkFetchJobStatus.PLANNING:
            return

        try:
            years = list(range(bulk_job.requested_year_start, bulk_job.requested_year_end + 1))
            new_jobs_to_add = []
            
            existing_jobs = self.db.query(SearchJob).filter(
                SearchJob.bulk_fetch_job_id == bulk_job.id,
                SearchJob.survey_prefix == " "
            ).all()
            
            existing_signatures = set()
            for j in existing_jobs:
                sig = f"{j.year}_{j.location_params.get('district_id')}_{j.location_params.get('taluka_id')}_{j.location_params.get('village_id')}"
                existing_signatures.add(sig)
                
            def add_location_jobs(loc_params: Dict[str, Any]):
                for y in years:
                    sig = f"{y}_{loc_params.get('district_id')}_{loc_params.get('taluka_id')}_{loc_params.get('village_id')}"
                    if sig not in existing_signatures:
                        new_jobs_to_add.append(
                            SearchJob(
                                bulk_fetch_job_id=bulk_job.id,
                                year=y,
                                location_params=loc_params,
                                survey_prefix=" "
                            )
                        )
                        existing_signatures.add(sig)

            if bulk_job.scope_type == ScopeType.STATE:
                districts = self.db.query(District).filter(District.is_active == True).all()
                if not districts:
                    raise ValueError("No active districts found in location master data.")
                for d in districts:
                    self._expand_district(d, add_location_jobs)

            elif bulk_job.scope_type == ScopeType.DISTRICT:
                district = self.db.query(District).filter(District.id == bulk_job.district_id).first()
                if not district:
                    raise ValueError(f"District {bulk_job.district_id} not found.")
                self._expand_district(district, add_location_jobs)

            elif bulk_job.scope_type == ScopeType.TALUKA:
                taluka = self.db.query(Taluka).filter(Taluka.id == bulk_job.taluka_id).first()
                if not taluka:
                    raise ValueError(f"Taluka {bulk_job.taluka_id} not found.")
                self._expand_taluka(taluka, add_location_jobs)

            elif bulk_job.scope_type == ScopeType.VILLAGE:
                village = self.db.query(Village).filter(Village.id == bulk_job.village_id).first()
                if not village:
                    raise ValueError(f"Village {bulk_job.village_id} not found.")
                taluka = self.db.query(Taluka).filter(Taluka.id == village.taluka_id).first()
                district = self.db.query(District).filter(District.id == taluka.district_id).first()
                add_location_jobs({
                    "district_id": district.source_id, "district_name": district.name_en,
                    "taluka_id": taluka.source_id, "taluka_name": taluka.name_en,
                    "village_id": village.source_id, "village_name": village.name_en
                })

            if new_jobs_to_add:
                self.db.add_all(new_jobs_to_add)

            generated_count = len(existing_jobs) + len(new_jobs_to_add)
            bulk_job.total_units = generated_count
            bulk_job.queued_units = generated_count
            bulk_job.status = BulkFetchJobStatus.RUNNING if generated_count > 0 else BulkFetchJobStatus.COMPLETED
            self.db.commit()
            logger.info(f"BulkFetchJob {bulk_job.id} planned {len(new_jobs_to_add)} new units. Total: {generated_count}")

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to plan BulkFetchJob {bulk_job_id}: {e}")
            bulk_job.status = BulkFetchJobStatus.FAILED
            bulk_job.error_message = f"Planning failed: {str(e)}"
            self.db.commit()

    def _expand_district(self, district: District, add_location_jobs: Callable):
        talukas = self.db.query(Taluka).filter(Taluka.district_id == district.id).all()
        if not talukas:
            add_location_jobs({"district_id": district.source_id, "district_name": district.name_en})
            return
        
        for t in talukas:
            self._expand_taluka(t, add_location_jobs, district)
            
    def _expand_taluka(self, taluka: Taluka, add_location_jobs: Callable, district: District = None):
        if not district:
            district = self.db.query(District).filter(District.id == taluka.district_id).first()
            
        villages = self.db.query(Village).filter(Village.taluka_id == taluka.id).all()
        if not villages:
            add_location_jobs({
                "district_id": district.source_id, "district_name": district.name_en,
                "taluka_id": taluka.source_id, "taluka_name": taluka.name_en
            })
            return
            
        for v in villages:
            add_location_jobs({
                "district_id": district.source_id, "district_name": district.name_en,
                "taluka_id": taluka.source_id, "taluka_name": taluka.name_en,
                "village_id": v.source_id, "village_name": v.name_en
            })
