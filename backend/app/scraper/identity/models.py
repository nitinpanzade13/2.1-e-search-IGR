import enum
import uuid
from typing import List, Optional
from pydantic import BaseModel

class ResolutionOutcome(enum.Enum):
    EXISTING_CONFIRMED = "EXISTING_CONFIRMED"
    NEW_REGISTRATION = "NEW_REGISTRATION"
    POSSIBLE_DUPLICATE = "POSSIBLE_DUPLICATE"
    AMBIGUOUS = "AMBIGUOUS"

class IdentityCandidateRecord(BaseModel):
    """
    Represents an existing registration record retrieved from the read-only repository.
    Only contains the fields necessary for candidate comparison.
    """
    internal_id: uuid.UUID
    year: int
    doc_no: str
    office: str
    indexii_url: str
    
    # Optional fields that could be used for weaker matching (POSSIBLE_DUPLICATE) in the future
    sr_no: Optional[str] = None
    doc_type: Optional[str] = None
    date: Optional[str] = None
    seller: Optional[str] = None
    buyer: Optional[str] = None
    other_info: Optional[str] = None

class IdentityResolutionDecision(BaseModel):
    """
    Explicit decision output from the IdentityResolver indicating what action
    orchestration should take, maintaining explicit uncertainty bounds.
    """
    outcome: ResolutionOutcome
    candidate_ids: List[uuid.UUID]
    reason: str
