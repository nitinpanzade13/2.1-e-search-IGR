import uuid
from typing import Optional
from sqlalchemy.orm import Session

from app.scraper.domain.dtos import SearchResultDTO
from app.scraper.identity.models import IdentityResolutionDecision, ResolutionOutcome
from app.scraper.domain.exceptions import IdentityResolutionError
from app.models.registration import Registration
from app.models.office import Office
from app.scraper.identity.resolver import _normalize_string
from app.scraper.parser.candidate_parser import CandidatePropertyParser

class RegistrationPersistenceService:
    """
    Safely persists registrations into the database based entirely on the 
    explicit outcome of the IdentityResolutionDecision.
    """
    def __init__(self, session: Session):
        self.session = session

    def persist(self, result: SearchResultDTO, decision: IdentityResolutionDecision) -> Optional[Registration]:
        if decision.outcome in (ResolutionOutcome.AMBIGUOUS, ResolutionOutcome.POSSIBLE_DUPLICATE):
            # As per strict constraints, we DO NOT persist ambiguous or weak evidence.
            # We explicitly raise an error to let orchestration know this result requires manual review/handling
            raise IdentityResolutionError(f"Cannot persist ambiguous/possible duplicate candidate safely. Reason: {decision.reason}")

        if decision.outcome == ResolutionOutcome.EXISTING_CONFIRMED:
            if not decision.candidate_ids or len(decision.candidate_ids) != 1:
                raise IdentityResolutionError("EXISTING_CONFIRMED must have exactly one candidate ID")
                
            reg_id = decision.candidate_ids[0]
            
            # Using transaction safety from caller, we just query and update
            reg = self.session.query(Registration).filter(Registration.id == reg_id).with_for_update().first()
            if not reg:
                raise IdentityResolutionError(f"Candidate {reg_id} vanished from database during persistence")
                
            # Safely merge search stage fields, preserving existing if incoming is empty/null
            if result.doc_no: reg.doc_no = result.doc_no
            if result.doc_type: reg.doc_type = result.doc_type
            if result.year: reg.year = result.year
            if result.office: 
                reg.office_name_raw = result.office
                reg.office_name_normalized = _normalize_string(result.office)
            if result.indexii_url: 
                reg.indexii_url = result.indexii_url
                reg.source_token = result.indexii_url
            
            # Phase-1 Discovery Fields (Always overwrite/update with latest discovery data)
            if result.seller: reg.seller_names_raw = result.seller
            if result.buyer: reg.buyer_names_raw = result.buyer
            if result.other_info: 
                reg.other_info_raw = result.other_info
                reg.candidate_properties = CandidatePropertyParser.parse(result.other_info)
            if result.date: reg.registration_date_raw = result.date
            
            # Try linking office if we can, but don't overwrite with null
            linked_office = self._find_office(result.office)
            if linked_office:
                reg.office_id = linked_office.id
                
            self.session.add(reg)
            return reg

        if decision.outcome == ResolutionOutcome.NEW_REGISTRATION:
            reg = Registration(
                id=uuid.uuid4(),
                year=result.year,
                doc_no=result.doc_no,
                doc_type=result.doc_type,
                indexii_url=result.indexii_url,
                office_name_raw=result.office,
                office_name_normalized=_normalize_string(result.office) if result.office else None,
                source_token=result.indexii_url, # In stage 1, source_token is indexii_url unless parsed differently
                seller_names_raw=result.seller,
                buyer_names_raw=result.buyer,
                other_info_raw=result.other_info,
                candidate_properties=CandidatePropertyParser.parse(result.other_info) if result.other_info else None,
                registration_date_raw=result.date
            )
            
            linked_office = self._find_office(result.office)
            if linked_office:
                reg.office_id = linked_office.id
                
            self.session.add(reg)
            return reg

        raise IdentityResolutionError(f"Unknown resolution outcome: {decision.outcome}")

    def _find_office(self, raw_office: str) -> Optional[Office]:
        if not raw_office:
            return None
        norm_office = _normalize_string(raw_office)
        # Attempt to map to an existing office to maintain foreign keys where possible
        from sqlalchemy import or_
        return self.session.query(Office).filter(
            or_(Office.name == norm_office, Office.name_mr == norm_office)
        ).first()
