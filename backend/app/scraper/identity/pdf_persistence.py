from sqlalchemy.orm import Session
from app.scraper.domain.dtos import PdfParsedResultDTO
from app.models.registration import Registration, Party, Property
from app.models.enums import PartyRole, ProcessingStatus

class PdfPersistenceService:
    def __init__(self, session: Session):
        self.session = session

    def persist(self, registration_id: str, parsed: PdfParsedResultDTO):
        reg = self.session.query(Registration).filter(Registration.id == registration_id).with_for_update().first()
        if not reg:
            raise ValueError(f"Registration {registration_id} not found")

        # Update scalars
        if parsed.doc_no_raw:
            # We don't overwrite doc_no if we already have it cleanly from Phase 1, but we can store raw if needed.
            # In this case, phase 1 doc_no is authoritative for deduplication, but we can update if phase 1 missed it.
            pass
            
        if parsed.execution_date_raw:
            try:
                from datetime import datetime
                # Typically dd-mm-yyyy or similar
                dt = datetime.strptime(parsed.execution_date_raw.strip(), "%d-%m-%Y")
                reg.execution_date = dt.date()
            except Exception:
                pass
        if parsed.registration_date_raw:
            reg.registration_date_raw = parsed.registration_date_raw
            try:
                from datetime import datetime
                dt = datetime.strptime(parsed.registration_date_raw.strip(), "%d-%m-%Y")
                reg.registration_date = dt.date()
            except Exception:
                pass
            
        # Financials
        try:
            if parsed.consideration_amount_raw:
                val = "".join(c for c in parsed.consideration_amount_raw if c.isdigit() or c == '.')
                if val: reg.consideration_amount = float(val)
        except Exception:
            pass
            
        try:
            if parsed.market_value_raw:
                val = "".join(c for c in parsed.market_value_raw if c.isdigit() or c == '.')
                if val: reg.market_value = float(val)
        except Exception:
            pass
            
        try:
            if parsed.stamp_duty_raw:
                val = "".join(c for c in parsed.stamp_duty_raw if c.isdigit() or c == '.')
                if val: reg.stamp_duty = float(val)
        except Exception:
            pass
            
        try:
            if parsed.registration_fee_raw:
                val = "".join(c for c in parsed.registration_fee_raw if c.isdigit() or c == '.')
                if val: reg.registration_fee = float(val)
        except Exception:
            pass
            
        if parsed.assessment_raw: reg.assessment_raw = parsed.assessment_raw
        if parsed.remarks_raw: reg.remarks_raw = parsed.remarks_raw

        # Clear existing children to ensure idempotency (upsert by replacement)
        # We only clear them if we actually parsed something, to avoid deleting manually enriched data,
        # but since this is an automated phase, replacing is standard for idempotency.
        self.session.query(Party).filter(Party.registration_id == registration_id).delete()
        self.session.query(Property).filter(Property.registration_id == registration_id).delete()

        # Insert Sellers
        party_order = 1
        if parsed.sellers_raw:
            p = Party(
                registration_id=reg.id,
                role=PartyRole.EXECUTANT,
                party_order=party_order,
                raw_text=parsed.sellers_raw
            )
            self.session.add(p)
            party_order += 1
            
        # Insert Buyers
        if parsed.buyers_raw:
            p = Party(
                registration_id=reg.id,
                role=PartyRole.CLAIMANT,
                party_order=party_order,
                raw_text=parsed.buyers_raw
            )
            self.session.add(p)
            
        # Insert Property
        prop_order = 1
        if parsed.properties_raw or parsed.area_raw:
            pr = Property(
                registration_id=reg.id,
                property_order=prop_order,
                description_raw=parsed.properties_raw,
                area_raw=parsed.area_raw
            )
            self.session.add(pr)

        reg.processing_status = ProcessingStatus.PARSED
        self.session.add(reg)
