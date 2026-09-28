from fastapi import Depends
from sqlalchemy.orm import Session
from typing import Generator

from app.core.database import SessionLocal
from app.core.config import settings

from app.scraper.client.igr_client import IgrSearchClient
from app.scraper.client.ocr_captcha_solver import HybridCaptchaSolver
from app.scraper.client.response_classifier import ResponseClassifier
from app.scraper.parser.html_parser import PureHtmlParser
from app.scraper.repository.record_details_repository import RecordDetailsRepository
from app.scraper.service.village_fetch_service import VillageFetchService
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_village_fetch_service(db: Session = Depends(get_db)) -> VillageFetchService:
    client = IgrSearchClient()
    solver = HybridCaptchaSolver()
    classifier = ResponseClassifier()
    parser = PureHtmlParser()
    repo = RecordDetailsRepository(db)
    return VillageFetchService(
        db=db,
        client=client,
        solver=solver,
        classifier=classifier,
        parser=parser,
        repository=repo
    )
