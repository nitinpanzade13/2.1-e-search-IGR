from pydantic import BaseModel, Field, field_validator, HttpUrl
from typing import List, Optional, Dict, Any
from datetime import datetime

class SearchScopeDTO(BaseModel):
    """Lightweight representation of source search scope parameters."""
    district_id: Optional[str] = None
    taluka_id: Optional[str] = None
    village_id: Optional[str] = None
    district_name: Optional[str] = None
    taluka_name: Optional[str] = None
    village_name: Optional[str] = None
    article_id: Optional[str] = None
    article_name: Optional[str] = None

class SearchRequestDTO(BaseModel):
    """Input parameters to perform one IGR search request."""
    year: int
    survey_query: str = Field(..., min_length=1)
    location: SearchScopeDTO
    article_id: Optional[str] = ""
    article_name: Optional[str] = ""

    @field_validator("article_id", "article_name", mode="before")
    @classmethod
    def default_empty_string(cls, v: Optional[str]) -> str:
        return v if v is not None else ""

    @field_validator("year")
    @classmethod
    def validate_year(cls, v: int) -> int:
        if not ((1985 <= v <= 2002) or (2012 <= v <= 2026)):
            raise ValueError(f"Year {v} is not supported by the IGR source (valid: 1985-2002, 2012-2026)")
        return v

class SearchResultDTO(BaseModel):
    """Immutable representation of one parsed row from the IGR search tableparty."""
    year: int = Field(..., gt=1980, le=2100)
    survey_query: str
    sr_no: str = Field(..., min_length=1)
    doc_no: str = Field(..., min_length=1)
    doc_type: str
    office: str
    date: str
    seller: str
    buyer: str
    other_info: str
    indexii_url: str

    model_config = {"frozen": True}

    @field_validator("sr_no", "doc_no", "doc_type", "office", "date", "seller", "buyer", "other_info")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        """Safely strip outer whitespace without modifying inner text."""
        return v.strip()

    @field_validator("indexii_url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Ensure the URL is somewhat well-formed or a relative path."""
        v = v.strip()
        if not v:
            raise ValueError("indexii_url cannot be empty")
        if not v.startswith("/") and not v.startswith("http"):
            raise ValueError("indexii_url must be an absolute or relative path")
        return v

class SearchResponseDTO(BaseModel):
    """Complete parsed outcome of an IGR search."""
    results: List[SearchResultDTO]
    reported_count: Optional[int] = None
    retrieved_count: int = Field(..., ge=0)
    truncated: bool
    year: int
    survey_query: str
    location: SearchScopeDTO

RecordDetailDTO = SearchResultDTO
