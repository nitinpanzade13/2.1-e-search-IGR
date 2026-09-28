from app.core.database import SessionLocal
from app.models.registration import Registration, Party, Property
from app.models.job import PdfTask, SearchJob, BulkFetchJob, SearchJobRegistration
from app.models.location import State, District, Taluka, Village
from app.models.office import Office
from app.models.artifact import Artifact
import sys

def check_counts():
    db = SessionLocal()
    try:
        reg_count = db.query(Registration).count()
        pdf_count = db.query(PdfTask).count()
        art_count = db.query(Artifact).count()
        pty_count = db.query(Party).count()
        prop_count = db.query(Property).count()
        sj_count = db.query(SearchJob).count()
        bf_count = db.query(BulkFetchJob).count()
        sjr_count = db.query(SearchJobRegistration).count()
        
        # Verify zero orphans
        orphan_sjr = db.query(SearchJobRegistration).filter(SearchJobRegistration.search_job_id == None).count()
        
        # Verify duplicate authoritative identity
        from sqlalchemy import func
        dupe_identity = db.query(Registration.doc_no, Registration.office_id, Registration.year).group_by(Registration.doc_no, Registration.office_id, Registration.year).having(func.count() > 1).count()
        
        # Verify duplicate search job registration
        dupe_sjr = db.query(SearchJobRegistration.search_job_id, SearchJobRegistration.registration_id).group_by(SearchJobRegistration.search_job_id, SearchJobRegistration.registration_id).having(func.count() > 1).count()

        print(f"Registrations: {reg_count}")
        print(f"PdfTasks: {pdf_count}")
        print(f"Artifacts: {art_count}")
        print(f"Parties: {pty_count}")
        print(f"Properties: {prop_count}")
        print(f"SearchJobs: {sj_count}")
        print(f"BulkFetchJobs: {bf_count}")
        print(f"SearchJobRegistrations: {sjr_count}")
        print(f"Orphan SJRs: {orphan_sjr}")
        print(f"Duplicate Identities: {dupe_identity}")
        print(f"Duplicate SJRs: {dupe_sjr}")
    finally:
        db.close()

if __name__ == "__main__":
    check_counts()
