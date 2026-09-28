from app.core.database import SessionLocal
from app.models.location import State, District, Taluka, Village
from app.models.office import Office
from app.models.registration import Registration, Party, Property
from app.models.job import SearchJob, PdfTask, BulkFetchJob, SearchJobRegistration
from app.models.artifact import Artifact
from app.models.processing import ParserRun
from app.models.office import Office
from sqlalchemy import func
import sys

def check_counts():
    db = SessionLocal()
    try:
        dupe_identity = db.query(Registration.doc_no, Registration.office_id, Registration.year).group_by(Registration.doc_no, Registration.office_id, Registration.year).having(func.count() > 1).all()
        for d in dupe_identity:
            print(f"Duplicate: doc_no={d[0]}, office={d[1]}, year={d[2]}")
            
            regs = db.query(Registration).filter_by(doc_no=d[0], office_id=d[1], year=d[2]).all()
            for r in regs:
                print(f"  ID: {r.id}, created: {r.created_at}")
    finally:
        db.close()

if __name__ == "__main__":
    check_counts()
