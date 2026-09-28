from typing import Protocol, List
from app.scraper.domain.dtos import SearchResultDTO
from app.scraper.identity.models import ResolutionOutcome, IdentityCandidateRecord, IdentityResolutionDecision
from app.scraper.domain.exceptions import IdentityResolutionError

class IdentityCandidateRepository(Protocol):
    """
    Read-only abstraction boundary for identity lookups.
    Concrete implementations (e.g., PostgreSQL) belong in a later stage.
    """
    def find_by_source_token(self, normalized_url: str) -> List[IdentityCandidateRecord]:
        """Looks up existing candidates matching the exactly normalized source URL."""
        ...
        
    def find_by_office_doc_year(self, normalized_office: str, normalized_doc_no: str, year: int) -> List[IdentityCandidateRecord]:
        """Looks up existing candidates matching the normalized composite evidence."""
        ...

def _normalize_string(val: str) -> str:
    """
    Deterministically normalizes strings for identity comparison without destroying meaning.
    Strips leading/trailing and repeated whitespace. Preserves Unicode and digits.
    """
    if not val:
        return ""
    return " ".join(val.split())

class IdentityResolver:
    """
    Deterministic, conservative component to evaluate candidate identity matches 
    without applying destructive deduplication.
    """
    def __init__(self, repository: IdentityCandidateRepository):
        self.repository = repository

    def resolve(self, result: SearchResultDTO) -> IdentityResolutionDecision:
        if not result.indexii_url:
            raise IdentityResolutionError("SearchResultDTO missing indexii_url, cannot resolve identity")

        norm_url = _normalize_string(result.indexii_url)
        norm_office = _normalize_string(result.office)
        norm_doc = _normalize_string(result.doc_no)
        year = result.year

        # Candidate A: Exact source URL match
        url_candidates = self.repository.find_by_source_token(norm_url)
        
        # Candidate B: Composite office + doc_no + year match
        composite_candidates = []
        if norm_office and norm_doc:
            composite_candidates = self.repository.find_by_office_doc_year(norm_office, norm_doc, year)

        url_ids = {c.internal_id for c in url_candidates}
        comp_ids = {c.internal_id for c in composite_candidates}

        def sorted_ids(ids: set):
            return sorted(list(ids), key=str)

        # Rule C: No candidate matches
        if not url_ids and not comp_ids:
            return IdentityResolutionDecision(
                outcome=ResolutionOutcome.NEW_REGISTRATION,
                candidate_ids=[],
                reason="No matching candidates found"
            )

        # Rule A: Exact source URL/token match processing
        if url_ids:
            if len(url_ids) == 1:
                uid = list(url_ids)[0]
                # Rule D: Conflicting evidence (URL points to A, office/doc/year points to B)
                if comp_ids and uid not in comp_ids:
                    return IdentityResolutionDecision(
                        outcome=ResolutionOutcome.AMBIGUOUS,
                        candidate_ids=sorted_ids(url_ids | comp_ids),
                        reason="Conflict: URL matches one registration but composite evidence matches another"
                    )
                # Strong exact evidence
                return IdentityResolutionDecision(
                    outcome=ResolutionOutcome.EXISTING_CONFIRMED,
                    candidate_ids=[uid],
                    reason="Exact source URL match"
                )
            else:
                return IdentityResolutionDecision(
                    outcome=ResolutionOutcome.AMBIGUOUS,
                    candidate_ids=sorted_ids(url_ids),
                    reason="Multiple registrations share the same source URL"
                )

        # Rule B: Exact office + doc_no + year match processing
        if comp_ids:
            if len(comp_ids) == 1:
                return IdentityResolutionDecision(
                    outcome=ResolutionOutcome.EXISTING_CONFIRMED,
                    candidate_ids=sorted_ids(comp_ids),
                    reason="Exact office + doc_no + year match"
                )
            else:
                return IdentityResolutionDecision(
                    outcome=ResolutionOutcome.AMBIGUOUS,
                    candidate_ids=sorted_ids(comp_ids),
                    reason="Multiple registrations share the same office + doc_no + year"
                )

        # Unreachable fallback
        raise IdentityResolutionError("Unreachable identity state")
