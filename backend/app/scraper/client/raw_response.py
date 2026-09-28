from dataclasses import dataclass
from typing import Mapping, Optional

@dataclass(frozen=True)
class RawSearchResponse:
    """
    Immutable representation of the transport-level HTTP response
    returned by the IGR portal after a search submission.
    """
    status_code: int
    content_type: Optional[str]
    body: bytes
    headers: Mapping[str, str]
    url: str
