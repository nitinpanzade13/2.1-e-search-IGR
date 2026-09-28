import uuid
from typing import List
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.scraper.identity.models import IdentityCandidateRecord
from app.scraper.identity.resolver import IdentityCandidateRepository
from app.models.registration import Registration
from app.models.office import Office

class PostgresIdentityRepository(IdentityCandidateRepository):
    """
    Concrete PostgreSQL repository for IdentityCandidate lookups.
    
    IMPORTANT NORMALIZATION CONTRACT:
    The methods here expect all string arguments to be ALREADY NORMALIZED 
    by the caller (IdentityResolver). This repository executes the queries 
    as-is without silently redefining normalization semantics.
    """
    def __init__(self, session: Session):
        self.session = session

    def find_by_source_token(self, normalized_url: str) -> List[IdentityCandidateRecord]:
        """Looks up existing candidates matching the exactly normalized source URL."""
        if not normalized_url:
            return []
            
        rows = (
            self.session.query(Registration, Office)
            .outerjoin(Office, Registration.office_id == Office.id)
            .filter(Registration.source_token == normalized_url)
            .all()
        )
        
        return [self._map_to_candidate(reg, office) for reg, office in rows]

    def find_by_office_doc_year(self, normalized_office: str, normalized_doc_no: str, year: int) -> List[IdentityCandidateRecord]:
        """Looks up existing candidates matching the normalized composite evidence."""
        if not normalized_office or not normalized_doc_no:
            return []
            
        rows = (
            self.session.query(Registration, Office)
            .outerjoin(Office, Registration.office_id == Office.id)
            .filter(
                Registration.doc_no == normalized_doc_no,
                Registration.year == year,
                or_(
                    Office.name == normalized_office,
                    Office.name_mr == normalized_office,
                    Registration.office_name_normalized == normalized_office
                )
            )
            .all()
        )
        
        return [self._map_to_candidate(reg, office) for reg, office in rows]

    def _map_to_candidate(self, reg: Registration, office: Office) -> IdentityCandidateRecord:
        office_str = reg.office_name_raw or ""
        if office:
            office_str = office.name_mr or office.name or office_str
            
        return IdentityCandidateRecord(
            internal_id=reg.id,
            year=reg.year,
            doc_no=reg.doc_no,
            office=office_str,
            indexii_url=reg.indexii_url or "",
            doc_type=reg.doc_type
        )
