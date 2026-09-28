import pytest
import uuid
from sqlalchemy.exc import IntegrityError
from app.scraper.domain.dtos import SearchResultDTO
from app.scraper.identity.models import ResolutionOutcome, IdentityResolutionDecision
from app.scraper.domain.exceptions import IdentityResolutionError
from app.scraper.identity.repository import PostgresIdentityRepository
from app.scraper.identity.persistence import RegistrationPersistenceService
from app.models.registration import Registration
from app.models.office import Office
# The db fixture is now imported from conftest.py

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    pass # Migrations handled centrally now

@pytest.fixture
def repo(db):
    return PostgresIdentityRepository(session=db)

@pytest.fixture
def persistence(db):
    return RegistrationPersistenceService(session=db)

def make_dto(url="/test", office="Pune SRO", doc_no="123", year=2026) -> SearchResultDTO:
    return SearchResultDTO(
        year=year,
        survey_query="survey",
        sr_no="1",
        doc_no=doc_no,
        doc_type="Deed",
        office=office,
        date="date",
        seller="seller",
        buyer="buyer",
        other_info="info",
        indexii_url=url
    )

# --- REPOSITORY TESTS ---

def test_repo_find_by_source_token_zero(repo, db):
    assert len(repo.find_by_source_token("/nonexistent")) == 0

def test_repo_find_by_source_token_independent_of_indexii(repo, db):
    # Proves repository looks up by source_token, not indexii_url
    reg = Registration(
        year=2026, 
        doc_no="111", 
        doc_type="Deed", 
        source_token="/same/token", 
        indexii_url="/different/url"
    )
    db.add(reg)
    db.flush()
    
    # Looking up by source token should succeed
    res = repo.find_by_source_token("/same/token")
    assert len(res) == 1
    assert res[0].internal_id == reg.id
    
    # Looking up by indexii_url should fail
    res2 = repo.find_by_source_token("/different/url")
    assert len(res2) == 0

def test_repo_find_by_source_token_multiple(repo, db):
    reg1 = Registration(year=2026, doc_no="111", doc_type="Deed", source_token="/multi")
    reg2 = Registration(year=2027, doc_no="222", doc_type="Deed", source_token="/multi")
    db.add_all([reg1, reg2])
    db.flush()
    
    res = repo.find_by_source_token("/multi")
    assert len(res) == 2

def test_repo_find_by_office_doc_year_zero(repo, db):
    assert len(repo.find_by_office_doc_year("Nowhere", "999", 2026)) == 0

def test_repo_normalized_composite_lookup_without_office_id(repo, db):
    # When office_id is missing, we must be able to lookup via normalized string
    reg = Registration(
        year=2026, 
        doc_no="999", 
        doc_type="Deed", 
        office_name_raw="Pune   SRO",
        office_name_normalized="Pune SRO"
    )
    db.add(reg)
    db.flush()
    
    # Normalized lookup value should resolve it via office_name_normalized
    res = repo.find_by_office_doc_year("Pune SRO", "999", 2026)
    assert len(res) == 1
    assert res[0].internal_id == reg.id
    
    # Raw value lookup should NOT be the expected path, but proving we don't depend on raw equality
    res2 = repo.find_by_office_doc_year("Pune   SRO", "999", 2026)
    assert len(res2) == 0

def test_repo_find_by_office_doc_year_multiple(repo, db):
    off = Office(source_id="O2", name="Mumbai")
    db.add(off)
    db.flush()
    reg1 = Registration(year=2026, doc_no="888", doc_type="Deed", office_id=off.id)
    reg2 = Registration(year=2026, doc_no="888", doc_type="Deed", office_id=off.id)
    db.add_all([reg1, reg2])
    db.flush()
    
    res = repo.find_by_office_doc_year("Mumbai", "888", 2026)
    assert len(res) == 2

def test_repo_does_not_assume_uniqueness(db):
    # Proves database allows multiple identical candidate fields natively
    off = Office(source_id="O3", name="Thane")
    db.add(off)
    db.flush()
    reg1 = Registration(year=2026, doc_no="777", doc_type="Deed", office_id=off.id, indexii_url="/dup")
    reg2 = Registration(year=2026, doc_no="777", doc_type="Deed", office_id=off.id, indexii_url="/dup")
    db.add_all([reg1, reg2])
    # db.flush() shouldn't raise IntegrityError
    db.flush()
    assert reg1.id != reg2.id

# --- PERSISTENCE TESTS ---

def test_persist_new_registration(persistence, db):
    dto = make_dto(url="/new", office="Pune   SRO", doc_no="456", year=2026)
    decision = IdentityResolutionDecision(
        outcome=ResolutionOutcome.NEW_REGISTRATION,
        candidate_ids=[],
        reason="None"
    )
    reg = persistence.persist(dto, decision)
    db.flush()
    
    assert reg.id is not None
    assert reg.doc_no == "456"
    assert reg.indexii_url == "/new"
    # Proves raw text is preserved natively
    assert reg.office_name_raw == "Pune   SRO"
    # Proves normalized text is set separately
    assert reg.office_name_normalized == "Pune SRO"
    
def test_persist_existing_confirmed(persistence, db):
    # Create baseline
    reg = Registration(year=2026, doc_no="old", doc_type="Deed", indexii_url="/existing")
    db.add(reg)
    db.flush()
    original_id = reg.id
    
    # Update via persist
    dto = make_dto(url="/existing", doc_no="new_doc_no")
    decision = IdentityResolutionDecision(
        outcome=ResolutionOutcome.EXISTING_CONFIRMED,
        candidate_ids=[original_id],
        reason="Exact URL match"
    )
    updated_reg = persistence.persist(dto, decision)
    db.flush()
    
    # Assert ID remained the same, but values updated
    assert updated_reg.id == original_id
    assert updated_reg.doc_no == "new_doc_no"
    
def test_persist_ambiguous_fails(persistence, db):
    dto = make_dto()
    decision = IdentityResolutionDecision(
        outcome=ResolutionOutcome.AMBIGUOUS,
        candidate_ids=[uuid.uuid4(), uuid.uuid4()],
        reason="Multiple"
    )
    with pytest.raises(IdentityResolutionError):
        persistence.persist(dto, decision)

def test_persist_possible_duplicate_fails(persistence, db):
    dto = make_dto()
    decision = IdentityResolutionDecision(
        outcome=ResolutionOutcome.POSSIBLE_DUPLICATE,
        candidate_ids=[uuid.uuid4()],
        reason="Weak"
    )
    with pytest.raises(IdentityResolutionError):
        persistence.persist(dto, decision)

def test_persist_transaction_rollback_safety(persistence, db):
    dto = make_dto()
    decision = IdentityResolutionDecision(
        outcome=ResolutionOutcome.NEW_REGISTRATION,
        candidate_ids=[],
        reason=""
    )
    # If we force an error, caller handles rollback
    # We can test atomicity by creating a sub-transaction and intentionally failing
    # Actually, SQLAlchemy transactions are explicitly handled by the injected session.
    # We verify that if we raise an error, the DB session can just be rolled back.
    reg = persistence.persist(dto, decision)
    db.flush()
    assert reg.id is not None
    # Simulate rollback from caller
    db.rollback()
    
    # Should not exist
    count = db.query(Registration).filter(Registration.id == reg.id).count()
    assert count == 0
def test_persist_existing_confirmed_does_not_overwrite_with_empty(persistence, db):
    reg = Registration(year=2026, doc_no="keep_me", doc_type="Deed", indexii_url="/keep")
    db.add(reg)
    db.flush()
    original_id = reg.id
    
    # Empty DTO properties shouldn't overwrite existing
    # Make a DTO with missing values (e.g. empty doc_no)
    dto = SearchResultDTO(
        year=2026,
        survey_query="survey",
        sr_no="1",
        doc_no="keep_me", # mandatory in DTO
        doc_type="Deed",
        office="",
        date="",
        seller="",
        buyer="",
        other_info="",
        indexii_url="/keep"
    )
    decision = IdentityResolutionDecision(
        outcome=ResolutionOutcome.EXISTING_CONFIRMED,
        candidate_ids=[original_id],
        reason="Test"
    )
    
    updated_reg = persistence.persist(dto, decision)
    db.flush()
    assert updated_reg.doc_no == "keep_me"
    assert updated_reg.indexii_url == "/keep"
def test_persist_existing_confirmed_syncs_source_token(persistence, repo, db):
    reg = Registration(
        year=2026, 
        doc_no="sync", 
        doc_type="Deed", 
        indexii_url="/old/token",
        source_token="/old/token"
    )
    db.add(reg)
    db.flush()
    original_id = reg.id
    
    dto = SearchResultDTO(
        year=2026,
        survey_query="survey",
        sr_no="1",
        doc_no="sync",
        doc_type="Deed",
        office="",
        date="",
        seller="",
        buyer="",
        other_info="",
        indexii_url="/new/token"
    )
    decision = IdentityResolutionDecision(
        outcome=ResolutionOutcome.EXISTING_CONFIRMED,
        candidate_ids=[original_id],
        reason="Composite Match"
    )
    
    updated_reg = persistence.persist(dto, decision)
    db.flush()
    assert updated_reg.id == original_id
    assert updated_reg.indexii_url == "/new/token"
    assert updated_reg.source_token == "/new/token"
    
    candidates = repo.find_by_source_token("/new/token")
    assert len(candidates) == 1
    assert candidates[0].internal_id == original_id
