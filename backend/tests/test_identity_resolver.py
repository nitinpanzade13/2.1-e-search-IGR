import pytest
import uuid
from typing import List
from app.scraper.domain.dtos import SearchResultDTO
from app.scraper.domain.exceptions import IdentityResolutionError
from app.scraper.identity.models import ResolutionOutcome, IdentityCandidateRecord
from app.scraper.identity.resolver import IdentityResolver, IdentityCandidateRepository

class FakeRepository:
    def __init__(self):
        self.records = []

    def find_by_source_token(self, normalized_url: str) -> List[IdentityCandidateRecord]:
        return [r for r in self.records if r.indexii_url == normalized_url]

    def find_by_office_doc_year(self, office: str, doc_no: str, year: int) -> List[IdentityCandidateRecord]:
        return [r for r in self.records if r.office == office and r.doc_no == doc_no and r.year == year]

@pytest.fixture
def repo():
    return FakeRepository()

@pytest.fixture
def resolver(repo):
    return IdentityResolver(repository=repo)

def make_dto(url="/test", office="Pune", doc_no="123", year=2026, sr_no="1") -> SearchResultDTO:
    return SearchResultDTO(
        year=year,
        survey_query="survey",
        sr_no=sr_no,
        doc_no=doc_no,
        doc_type="type",
        office=office,
        date="date",
        seller="seller",
        buyer="buyer",
        other_info="info",
        indexii_url=url
    )

def test_extracts_and_normalizes(resolver, repo):
    repo.records.append(IdentityCandidateRecord(
        internal_id=uuid.uuid4(), year=2026, doc_no="123", office="Pune SRO", indexii_url="/clean/url"
    ))
    dto = make_dto(url="/clean/url", office="Pune   SRO", doc_no="123")
    decision = resolver.resolve(dto)
    assert decision.outcome == ResolutionOutcome.EXISTING_CONFIRMED
    # DTO is untouched by the resolver (inner whitespace preserved in DTO, but resolver normalized it to find the record)
    assert dto.office == "Pune   SRO"

def test_new_registration(resolver):
    # Repo is empty
    decision = resolver.resolve(make_dto())
    assert decision.outcome == ResolutionOutcome.NEW_REGISTRATION
    assert not decision.candidate_ids

def test_url_match_existing_confirmed(resolver, repo):
    uid = uuid.uuid4()
    repo.records.append(IdentityCandidateRecord(
        internal_id=uid, year=2026, doc_no="123", office="Pune", indexii_url="/test"
    ))
    decision = resolver.resolve(make_dto())
    assert decision.outcome == ResolutionOutcome.EXISTING_CONFIRMED
    assert decision.candidate_ids == [uid]

def test_url_match_multiple_ambiguous(resolver, repo):
    repo.records.extend([
        IdentityCandidateRecord(internal_id=uuid.uuid4(), year=2026, doc_no="123", office="Pune", indexii_url="/test"),
        IdentityCandidateRecord(internal_id=uuid.uuid4(), year=2026, doc_no="123", office="Pune", indexii_url="/test"),
    ])
    decision = resolver.resolve(make_dto())
    assert decision.outcome == ResolutionOutcome.AMBIGUOUS
    assert len(decision.candidate_ids) == 2

def test_composite_match_existing_confirmed(resolver, repo):
    uid = uuid.uuid4()
    # URL differs, but composite matches
    repo.records.append(IdentityCandidateRecord(
        internal_id=uid, year=2026, doc_no="123", office="Pune", indexii_url="/diff"
    ))
    decision = resolver.resolve(make_dto(url="/test"))
    assert decision.outcome == ResolutionOutcome.EXISTING_CONFIRMED
    assert decision.candidate_ids == [uid]

def test_composite_match_multiple_ambiguous(resolver, repo):
    repo.records.extend([
        IdentityCandidateRecord(internal_id=uuid.uuid4(), year=2026, doc_no="123", office="Pune", indexii_url="/diff1"),
        IdentityCandidateRecord(internal_id=uuid.uuid4(), year=2026, doc_no="123", office="Pune", indexii_url="/diff2"),
    ])
    decision = resolver.resolve(make_dto(url="/test"))
    assert decision.outcome == ResolutionOutcome.AMBIGUOUS
    assert len(decision.candidate_ids) == 2

def test_conflicting_evidence_ambiguous(resolver, repo):
    uid1 = uuid.uuid4()
    uid2 = uuid.uuid4()
    # Record A matches URL only
    repo.records.append(IdentityCandidateRecord(
        internal_id=uid1, year=2025, doc_no="999", office="Mumbai", indexii_url="/test"
    ))
    # Record B matches composite only
    repo.records.append(IdentityCandidateRecord(
        internal_id=uid2, year=2026, doc_no="123", office="Pune", indexii_url="/diff"
    ))
    decision = resolver.resolve(make_dto(url="/test", office="Pune", doc_no="123", year=2026))
    
    assert decision.outcome == ResolutionOutcome.AMBIGUOUS
    assert set(decision.candidate_ids) == {uid1, uid2}
    assert "Conflict" in decision.reason

def test_same_sr_no_different_registration(resolver, repo):
    uid = uuid.uuid4()
    # Record has same sr_no (sr_no is not used in resolution), but different URL/Composite
    repo.records.append(IdentityCandidateRecord(
        internal_id=uid, year=2020, doc_no="999", office="Mumbai", indexii_url="/diff", sr_no="1"
    ))
    decision = resolver.resolve(make_dto(url="/test", office="Pune", doc_no="123", year=2026, sr_no="1"))
    assert decision.outcome == ResolutionOutcome.NEW_REGISTRATION

def test_same_doc_year_different_office(resolver, repo):
    uid = uuid.uuid4()
    # Same doc_no and year, but office differs
    repo.records.append(IdentityCandidateRecord(
        internal_id=uid, year=2026, doc_no="123", office="Mumbai", indexii_url="/diff"
    ))
    decision = resolver.resolve(make_dto(url="/test", office="Pune", doc_no="123", year=2026))
    # Office differs, so composite doesn't match
    assert decision.outcome == ResolutionOutcome.NEW_REGISTRATION

def test_resolver_purity(resolver, repo):
    from unittest import mock
    with mock.patch("requests.Session.get") as mock_get, \
         mock.patch("builtins.open") as mock_open:
         
         resolver.resolve(make_dto())
         mock_get.assert_not_called()
         mock_open.assert_not_called()
def test_repository_receives_normalized_args(resolver, repo):
    from unittest import mock
    
    dto = make_dto(url="  /test/url  ", office="Pune   SRO", doc_no=" 123 ", year=2026)
    
    with mock.patch.object(repo, 'find_by_source_token', return_value=[]) as mock_token, \
         mock.patch.object(repo, 'find_by_office_doc_year', return_value=[]) as mock_composite:
         
         resolver.resolve(dto)
         
         mock_token.assert_called_once_with("/test/url")
         mock_composite.assert_called_once_with("Pune SRO", "123", 2026)
