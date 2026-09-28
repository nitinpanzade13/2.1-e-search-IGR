import requests
import logging
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from typing import Optional, Dict, Any, List
from pydantic import BaseModel

from app.models.location import State, District, Taluka, Village
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)

BASE_URL = "https://pay2igr.igrmaharashtra.gov.in/eDisplay/Propertydetails"
SOURCE_SYSTEM = "IGR_MAHARASHTRA"
STATE_SOURCE_ID = "27"  # Maharashtra state code

class ImportSummary(BaseModel):
    source: str = "Live IGR API"
    states_processed: int = 0
    districts_processed: int = 0
    talukas_processed: int = 0
    villages_processed: int = 0
    
    inserted: int = 0
    updated: int = 0
    unchanged: int = 0
    rejected_malformed: int = 0
    duplicates_detected: int = 0
    conflicts: int = 0
    orphans: int = 0
    
    district_requests: int = 0
    taluka_requests: int = 0
    village_requests: int = 0
    total_http_requests: int = 0

class IgrLocationClient:
    def __init__(self, timeout: int = 60):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "IGR-Location-Master-Importer/1.0",
            "Accept": "application/json",
        })
        self.district_requests = 0
        self.taluka_requests = 0
        self.village_requests = 0

    def get_districts(self) -> List[Dict[str, Any]]:
        self.district_requests += 1
        resp = self.session.get(f"{BASE_URL}/getDistrictName2019", timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get_talukas(self, district_id: str) -> List[Dict[str, Any]]:
        self.taluka_requests += 1
        resp = self.session.get(f"{BASE_URL}/getTalukaName2019", params={"district": district_id}, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def get_villages(self, district_id: str, taluka_id: str) -> List[Dict[str, Any]]:
        self.village_requests += 1
        resp = self.session.get(f"{BASE_URL}/getVillageName2019", params={"district": district_id, "taluka": taluka_id}, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

class LocationImporter:
    def __init__(self, db: Session, dry_run: bool = True):
        self.db = db
        self.dry_run = dry_run
        self.client = IgrLocationClient()
        self.summary = ImportSummary()

    def _upsert_record(self, model: Any, index_elements: List[str], values: Dict[str, Any]) -> Optional[Any]:
        """Idempotent upsert."""
        filters = {k: values[k] for k in index_elements}
        existing = self.db.query(model).filter_by(**filters).first()
        
        has_changes = True
        if existing:
            has_changes = any(getattr(existing, k) != v for k, v in values.items() if k not in index_elements)
            
        if self.dry_run:
            if existing:
                if has_changes:
                    self.summary.updated += 1
                else:
                    self.summary.unchanged += 1
                return existing
            else:
                self.summary.inserted += 1
                dummy = model(**values)
                import uuid
                dummy.id = uuid.uuid4()
                return dummy

        if existing and not has_changes:
            self.summary.unchanged += 1
            return existing

        stmt = insert(model).values(**values)
        update_dict = {c.name: c for c in stmt.excluded if c.name not in index_elements and c.name not in ['id', 'created_at']}
        
        if update_dict:
            stmt = stmt.on_conflict_do_update(
                index_elements=index_elements,
                set_=update_dict
            ).returning(model)
            
            result = self.db.execute(stmt).scalar_one_or_none()
            if result:
                if existing:
                    self.summary.updated += 1
                else:
                    self.summary.inserted += 1
            return result
        else:
            stmt = stmt.on_conflict_do_nothing().returning(model)
            result = self.db.execute(stmt).scalar_one_or_none()
            if result:
                self.summary.inserted += 1
                return result
            else:
                self.summary.unchanged += 1
                return self.db.query(model).filter_by(**filters).first()

    def run(self, target_district_id: Optional[str] = None, target_taluka_id: Optional[str] = None) -> ImportSummary:
        logger.info(f"Starting Location Import (Dry Run: {self.dry_run})")
        
        # 1. State
        self.summary.states_processed += 1
        state_values = {
            "source_system": SOURCE_SYSTEM,
            "source_id": STATE_SOURCE_ID,
            "name_en": "Maharashtra",
            "is_active": True
        }
        state_record = self._upsert_record(State, ["source_system", "source_id"], state_values)
        if not self.dry_run:
            self.db.commit()

        # 2. Districts
        try:
            raw_districts = self.client.get_districts()
        except Exception as e:
            logger.error(f"Failed to fetch districts: {e}")
            return self.summary

        for d in raw_districts:
            d_id = str(d.get("dist_code", "")).strip()
            d_name = d.get("mdist_name", "").strip()
            
            if not d_id or not d_name:
                self.summary.rejected_malformed += 1
                continue
                
            if target_district_id and d_id != target_district_id:
                continue

            self.summary.districts_processed += 1
            d_values = {
                "source_system": SOURCE_SYSTEM,
                "source_id": d_id,
                "state_id": state_record.id,
                "name_en": d_name,
                "is_active": True
            }
            district_record = self._upsert_record(District, ["source_system", "source_id", "state_id"], d_values)
            if not self.dry_run:
                self.db.commit()

            # 3. Talukas
            try:
                raw_talukas = self.client.get_talukas(d_id)
            except Exception as e:
                logger.error(f"Failed to fetch talukas for district {d_id}: {e}")
                continue

            for t in raw_talukas:
                t_id = str(t.get("taluka_code", "")).strip()
                t_name = t.get("mtaluka_name", "").strip()
                
                if not t_id or not t_name:
                    self.summary.rejected_malformed += 1
                    continue
                    
                if target_taluka_id and t_id != target_taluka_id:
                    continue

                self.summary.talukas_processed += 1
                t_values = {
                    "source_system": SOURCE_SYSTEM,
                    "source_id": t_id,
                    "district_id": district_record.id,
                    "name_en": t_name,
                    "is_active": True
                }
                taluka_record = self._upsert_record(Taluka, ["source_system", "source_id", "district_id"], t_values)
                if not self.dry_run:
                    self.db.commit()

                # 4. Villages
                try:
                    raw_villages = self.client.get_villages(d_id, t_id)
                except Exception as e:
                    logger.error(f"Failed to fetch villages for taluka {t_id}: {e}")
                    continue

                for v_index, v in enumerate(raw_villages):
                    v_name = v.get("am_mareaname", "").strip()
                    # The legacy portal API uses index as village ID in the form submission!
                    v_id = str(v_index)

                    if not v_name:
                        self.summary.rejected_malformed += 1
                        continue

                    self.summary.villages_processed += 1
                    v_values = {
                        "source_system": SOURCE_SYSTEM,
                        "source_id": v_id,
                        "taluka_id": taluka_record.id,
                        "name_en": v_name,
                        "is_active": True
                    }
                    self._upsert_record(Village, ["source_system", "source_id", "taluka_id"], v_values)

                if not self.dry_run:
                    self.db.commit()

        self.summary.district_requests = self.client.district_requests
        self.summary.taluka_requests = self.client.taluka_requests
        self.summary.village_requests = self.client.village_requests
        self.summary.total_http_requests = (
            self.client.district_requests + 
            self.client.taluka_requests + 
            self.client.village_requests
        )
        return self.summary

if __name__ == "__main__":
    import sys
    import argparse
    from app.core.database import SessionLocal
    
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Do not save to DB")
    parser.add_argument("--district", type=str, help="Target district source ID")
    parser.add_argument("--taluka", type=str, help="Target taluka source ID")
    args = parser.parse_args()

    # Disable SQLalchemy echo for clean output
    logging.basicConfig(level=logging.INFO)
    logger.setLevel(logging.INFO)

    db = SessionLocal()
    try:
        importer = LocationImporter(db, dry_run=args.dry_run)
        summary = importer.run(target_district_id=args.district, target_taluka_id=args.taluka)
        
        print("\n" + "="*50)
        print("IMPORT SUMMARY")
        print("="*50)
        for key, value in summary.model_dump().items():
            print(f"{key.replace('_', ' ').title():<25}: {value}")
        
        # Verify Kharadi
        if args.district == "23" and args.taluka == "1":
            print("\nVerify specific mapping:")
            for v in importer.client.get_villages("23", "1"):
                if "खराडी" in v.get("am_mareaname", "") or "kharadi" in v.get("am_mareaname", "").lower():
                    # The index logic was used in the importer
                    # Let's just find it in the raw fetch to be 100% sure of the index.
                    pass
            raw = importer.client.get_villages("23", "1")
            for idx, v in enumerate(raw):
                if "खराडी" in v.get("am_mareaname", "") or "kharadi" in v.get("am_mareaname", "").lower():
                    print(f"FOUND: {v.get('am_mareaname')} -> source_id: {idx}")
        print("="*50 + "\n")
    finally:
        db.close()
