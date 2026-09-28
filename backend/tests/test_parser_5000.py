import pytest
import os
from app.scraper.parser.html_parser import PureHtmlParser
from app.scraper.domain.dtos import SearchScopeDTO

def test_pure_html_parser_5000_cap():
    # 1. REAL PARSER TEST
    fixture_path = os.path.join("storage", "raw", "test_response_2026_1.html")
    assert os.path.exists(fixture_path), f"Fixture not found at {fixture_path}"
    
    with open(fixture_path, "rb") as f:
        html_bytes = f.read()
        
    parser = PureHtmlParser()
    scope = SearchScopeDTO(district_name="Pune", taluka_name="Haveli", village_name="Pune")
    
    # Run the actual PureHtmlParser against the 9MB fixture
    result = parser.parse(
        html_bytes=html_bytes,
        year=2026,
        survey_query="1",
        scope=scope
    )
    
    assert result.retrieved_count == 5000
    assert result.reported_count == 5000
    assert result.truncated is True
    assert len(result.results) == 5000
    
    # Optional: Verify first and last records briefly to ensure parsing succeeded
    assert result.results[0].sr_no == "1"
    assert result.results[-1].sr_no == "5000"
