import pytest
from pydantic import ValidationError
from datetime import datetime, timezone
from app.scraper.domain.dtos import (
    SearchScopeDTO,
    SearchRequestDTO,
    SearchResultDTO,
    SearchResponseDTO
)
from app.scraper.domain.exceptions import (
    IGRSourceError,
    IGRNetworkError,
    IGRRateLimitError,
    IGRParserError
)
from app.scraper.domain.enums import ResponseClassification

def test_search_result_dto_valid():
    """Test standard valid search result instantiation with whitespace trimming."""
    result = SearchResultDTO(
        year=2026,
        survey_query="1",
        sr_no="  1 ",
        doc_no=" 1234/2026 ",
        doc_type="Sale Deed ",
        office=" Haveli 6",
        date=" 01/01/2026",
        seller="John Doe",
        buyer="Jane Doe ",
        other_info="  Property Info: Kharadi, Area: 100sqm \n Other text. ",
        indexii_url="/path/to/pdf"
    )
    assert result.sr_no == "1"
    assert result.doc_no == "1234/2026"
    assert result.doc_type == "Sale Deed"
    assert result.office == "Haveli 6"
    assert result.buyer == "Jane Doe"
    # Preserves inner structure like newlines:
    assert " \n Other text." in result.other_info
    assert result.indexii_url == "/path/to/pdf"

def test_search_result_dto_marathi_text():
    """Ensure Marathi text is preserved correctly."""
    result = SearchResultDTO(
        year=2026,
        survey_query="1",
        sr_no="१",
        doc_no="१२३४/२०२६",
        doc_type="खरेदी खत",
        office="दु. नि. कार्यालय",
        date="०१/०१/२०२६",
        seller="राम",
        buyer="श्याम",
        other_info="वर्णन",
        indexii_url="http://example.com/pdf"
    )
    assert result.doc_type == "खरेदी खत"

def test_search_result_dto_invalid_url():
    """Test URL validation rejecting completely malformed URLs."""
    with pytest.raises(ValidationError) as exc:
        SearchResultDTO(
            year=2026,
            survey_query="1",
            sr_no="1",
            doc_no="1234",
            doc_type="Deed",
            office="Office",
            date="Date",
            seller="S",
            buyer="B",
            other_info="O",
            indexii_url="malformed_url"
        )
    assert "indexii_url must be an absolute or relative path" in str(exc.value)

def test_search_result_dto_immutability():
    """Test that DTO is frozen."""
    result = SearchResultDTO(
        year=2026, survey_query="1", sr_no="1", doc_no="1", doc_type="T",
        office="O", date="D", seller="S", buyer="B", other_info="I", indexii_url="/u"
    )
    with pytest.raises(ValidationError):
        result.doc_no = "2"

def test_search_request_dto():
    """Test search request parameters with optional article selection."""
    scope = SearchScopeDTO(district_id="D1", taluka_id="T1", village_id="V1")
    req = SearchRequestDTO(year=2026, survey_query="42", location=scope)
    assert req.year == 2026
    assert req.location.district_id == "D1"
    assert req.article_id == ""
    assert req.article_name == ""

def test_search_request_dto_empty_article_handling():
    """Test explicit None or empty article_id and article_name values."""
    scope = SearchScopeDTO(district_id="D1", taluka_id="T1", village_id="V1", article_id=None, article_name=None)
    req = SearchRequestDTO(year=2026, survey_query="42", location=scope, article_id=None, article_name=None)
    assert req.article_id == ""
    assert req.article_name == ""

def test_search_request_dto_specified_article():
    """Test when article_id and article_name are provided."""
    scope = SearchScopeDTO(district_id="D1", taluka_id="T1", village_id="V1", article_id="25", article_name="Sale Deed")
    req = SearchRequestDTO(year=2026, survey_query="42", location=scope, article_id="25", article_name="Sale Deed")
    assert req.article_id == "25"
    assert req.article_name == "Sale Deed"

def test_search_response_dto():
    """Test search response container."""
    scope = SearchScopeDTO()
    res1 = SearchResultDTO(
        year=2026, survey_query="1", sr_no="1", doc_no="1", doc_type="T",
        office="O", date="D", seller="S", buyer="B", other_info="I", indexii_url="/u1"
    )
    res2 = SearchResultDTO(
        year=2026, survey_query="1", sr_no="2", doc_no="2", doc_type="T",
        office="O", date="D", seller="S", buyer="B", other_info="I", indexii_url="/u2"
    )
    
    resp = SearchResponseDTO(
        results=[res1, res2],
        reported_count=5000,
        retrieved_count=2,
        truncated=True,
        year=2026,
        survey_query="1",
        location=scope
    )
    assert len(resp.results) == 2
    assert resp.truncated is True

def test_domain_exceptions():
    """Test exception hierarchy and properties."""
    ex_net = IGRNetworkError("Timeout")
    assert ex_net.retryable is True
    assert ex_net.failure_category == "NETWORK_ERROR"

    ex_rate = IGRRateLimitError()
    assert ex_rate.retryable is True
    assert ex_rate.failure_category == "RATE_LIMIT_ERROR"

    ex_parse = IGRParserError("Missing table")
    assert ex_parse.retryable is False
    assert ex_parse.failure_category == "PARSER_ERROR"

