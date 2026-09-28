import uuid
from datetime import datetime, timezone
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.record_detail import RecordDetail
from app.scraper.domain.dtos import SearchResultDTO

class RecordDetailsRepository:
    def __init__(self, db: Session):
        self.db = db

    def save_records(
        self, 
        village_id: uuid.UUID, 
        records: List[SearchResultDTO],
        is_truncated: bool = False,
        reported_count: Optional[int] = None
    ) -> Tuple[int, int]:
        """
        Saves parsed record details into the record_details table with safe deduplication.
        Returns: (saved_count, duplicate_count)
        """
        saved_count = 0
        duplicate_count = 0

        for r in records:
            # Deduplication identity:
            # Primary signal: (village_id, indexii_url) if indexii_url is available
            # Supporting identity: (village_id, year, doc_no, office)
            existing = None
            if r.indexii_url:
                existing = self.db.query(RecordDetail).filter(
                    RecordDetail.village_id == village_id,
                    RecordDetail.indexii_url == r.indexii_url
                ).first()

            if not existing:
                query = self.db.query(RecordDetail).filter(
                    RecordDetail.village_id == village_id,
                    RecordDetail.year == r.year,
                    RecordDetail.doc_no == r.doc_no,
                )
                if r.office:
                    query = query.filter(RecordDetail.office == r.office)
                existing = query.first()

            if existing:
                duplicate_count += 1
                continue

            # Insert new record
            record_entity = RecordDetail(
                id=uuid.uuid4(),
                village_id=village_id,
                year=r.year,
                sr_no=r.sr_no,
                doc_no=r.doc_no,
                doc_type=r.doc_type,
                office=r.office,
                date=r.date,
                seller=r.seller,
                buyer=r.buyer,
                other_info=r.other_info,
                indexii_url=r.indexii_url,
                source_query=r.survey_query,
                is_truncated=is_truncated,
                reported_count=reported_count,
                fetched_at=datetime.now(timezone.utc),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            self.db.add(record_entity)
            try:
                self.db.commit()
                saved_count += 1
            except Exception:
                self.db.rollback()
                duplicate_count += 1

        return saved_count, duplicate_count
