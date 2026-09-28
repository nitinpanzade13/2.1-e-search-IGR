from pydantic import BaseModel
from typing import Optional

class ScrapeResult(BaseModel):
    year: int
    survey_query: int
    sr_no: str
    doc_no: str
    doc_type: str
    office: str
    date: str
    seller: str
    buyer: str
    other_info: str
    indexii_url: str
