import pytest
import uuid
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.models.location import State, District, Taluka, Village
from app.models.village_fetch import VillageFetch, VillageFetchStatus
from app.models.record_detail import RecordDetail
from app.scraper.domain.dtos import SearchResultDTO, SearchScopeDTO, SearchResponseDTO
from app.scraper.domain.enums import ResponseClassification
from app.scraper.client.raw_response import RawSearchResponse
from app.scraper.service.village_fetch_service import VillageFetchService
from app.scraper.repository.record_details_repository import RecordDetailsRepository
from app.scraper.parser.html_parser import PureHtmlParser

client = TestClient(app)

@pytest.fixture
def test_hierarchy(db):
    suffix = str(uuid.uuid4())[:8]
    state = State(source_id=f"S_{suffix}", name_en=f"Maharashtra_{suffix}")
    dist1 = District(state=state, source_id=f"D1_{suffix}", name_en=f"Pune_{suffix}")
    dist2 = District(state=state, source_id=f"D2_{suffix}", name_en=f"Thane_{suffix}")
    
    tal1 = Taluka(district=dist1, source_id=f"T1_{suffix}", name_en=f"Haveli_{suffix}")
    tal2 = Taluka(district=dist2, source_id=f"T2_{suffix}", name_en=f"Kalyan_{suffix}")
    
    vil1 = Village(taluka=tal1, source_id=f"V1_{suffix}", name_en=f"Kharadi_{suffix}")
    vil2 = Village(taluka=tal2, source_id=f"V2_{suffix}", name_en=f"Dombivli_{suffix}")
    
    db.add_all([state, dist1, dist2, tal1, tal2, vil1, vil2])
    db.commit()
    
    return {
        "state": state,
        "dist1": dist1,
        "dist2": dist2,
        "tal1": tal1,
        "tal2": tal2,
        "vil1": vil1,
        "vil2": vil2,
    }

def test_hierarchy_validation_success(db, test_hierarchy):
    service = VillageFetchService(db=db)
    h = test_hierarchy
    d, t, v = service.validate_hierarchy(h["dist1"].id, h["tal1"].id, h["vil1"].id)
    assert d.id == h["dist1"].id
    assert t.id == h["tal1"].id
    assert v.id == h["vil1"].id

def test_hierarchy_validation_mismatched_district(db, test_hierarchy):
    service = VillageFetchService(db=db)
    h = test_hierarchy
    with pytest.raises(ValueError, match="does not belong to District"):
        service.validate_hierarchy(h["dist2"].id, h["tal1"].id, h["vil1"].id)

def test_hierarchy_validation_mismatched_taluka(db, test_hierarchy):
    service = VillageFetchService(db=db)
    h = test_hierarchy
    with pytest.raises(ValueError, match="does not belong to Taluka"):
        service.validate_hierarchy(h["dist2"].id, h["tal2"].id, h["vil1"].id)

def test_village_is_only_fetching_unit(db, test_hierarchy):
    service = VillageFetchService(db=db)
    h = test_hierarchy
    
    fetch = service.create_fetch(
        district_id=h["dist1"].id,
        taluka_id=h["tal1"].id,
        village_id=h["vil1"].id,
        year=2026,
        search_query="1"
    )
    assert fetch.village_id == h["vil1"].id
    assert fetch.year == 2026
    assert fetch.status == VillageFetchStatus.QUEUED.value

    fetches = db.query(VillageFetch).filter_by(village_id=h["vil1"].id).all()
    assert len(fetches) == 1

def test_record_details_repository_deduplication(db, test_hierarchy):
    repo = RecordDetailsRepository(db)
    h = test_hierarchy
    village_id = h["vil1"].id
    
    dto1 = SearchResultDTO(
        sr_no="1",
        doc_no="1001/2026",
        doc_type="खरेदीखत",
        office="दु. नि. हवेली",
        date="15/01/2026",
        seller="विक्रेता १",
        buyer="खरेदीदार १",
        other_info="फ्लॅट क्र. १०१",
        indexii_url="/Index2View.aspx?id=1001",
        year=2026,
        survey_query="1"
    )
    
    saved_count, dup_count = repo.save_records(village_id, [dto1])
    assert saved_count == 1
    assert dup_count == 0

    rec1 = db.query(RecordDetail).filter_by(village_id=village_id, doc_no="1001/2026").first()
    assert rec1 is not None
    assert rec1.doc_type == "खरेदीखत"
    assert rec1.seller == "विक्रेता १"

    # Save same record again (idempotent / deduplication)
    saved_count2, dup_count2 = repo.save_records(village_id, [dto1])
    assert saved_count2 == 0
    assert dup_count2 == 1
    
    records = db.query(RecordDetail).filter_by(village_id=village_id, doc_no="1001/2026").all()
    assert len(records) == 1

def test_pure_html_parser_tableparty_marathi():
    sample_html = """
    <html>
    <body>
    <table id="tableparty" class="table">
        <thead>
            <tr>
                <th>अनु क्र.</th>
                <th>दस्त क्र.</th>
                <th>दस्त प्रकार</th>
                <th>दु.नि.कार्यालय</th>
                <th>दिनांक</th>
                <th>लिहून देणार</th>
                <th>लिहून घेणार</th>
                <th>इतर माहिती</th>
                <th>सूची क्र. २</th>
            </tr>
        </thead>
        <tbody>
            <tr id="tbdata">
                <td>1</td>
                <td>2450/2026</td>
                <td>विक्रीपत्र</td>
                <td>हवेली २</td>
                <td>01/02/2026</td>
                <td>सुरेश पाटील</td>
                <td>रमेश पवार</td>
                <td>प्लॉट नं ५, खराडी</td>
                <td><a href="/DocView.aspx?id=999">Index II</a></td>
            </tr>
        </tbody>
    </table>
    </body>
    </html>
    """
    parser = PureHtmlParser()
    scope = SearchScopeDTO(district_id="23", taluka_id="1", village_id="43")
    resp = parser.parse(sample_html.encode("utf-8"), 2026, "1", scope)
    assert len(resp.results) == 1
    r = resp.results[0]
    assert r.doc_no == "2450/2026"
    assert r.doc_type == "विक्रीपत्र"
    assert r.office == "हवेली २"
    assert "सुरेश पाटील" in r.seller
    assert r.indexii_url == "/DocView.aspx?id=999"

def test_api_create_village_fetch(test_hierarchy):
    h = test_hierarchy
    payload = {
        "district_id": str(h["dist1"].id),
        "taluka_id": str(h["tal1"].id),
        "village_id": str(h["vil1"].id),
        "year": 2026,
        "search_query": "1"
    }
    
    with patch.object(VillageFetchService, "execute_fetch"):
        resp = client.post("/api/v1/village-fetches", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["village_name"] == h["vil1"].name_en
        assert data["district_name"] == h["dist1"].name_en
        assert data["taluka_name"] == h["tal1"].name_en
        assert data["year"] == 2026

def test_api_list_and_get_village_fetch(test_hierarchy, db):
    h = test_hierarchy
    fetch = VillageFetch(
        village_id=h["vil1"].id,
        year=2026,
        current_search_value="1",
        status=VillageFetchStatus.COMPLETED.value,
        records_found=5,
        unique_records_saved=5
    )
    db.add(fetch)
    db.commit()

    list_resp = client.get("/api/v1/village-fetches")
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert any(item["id"] == str(fetch.id) for item in items)

    get_resp = client.get(f"/api/v1/village-fetches/{fetch.id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["unique_records_saved"] == 5

def test_api_pause_resume_cancel(test_hierarchy, db):
    h = test_hierarchy
    fetch = VillageFetch(
        village_id=h["vil1"].id,
        year=2026,
        current_search_value="1",
        status=VillageFetchStatus.RUNNING.value
    )
    db.add(fetch)
    db.commit()

    p_resp = client.post(f"/api/v1/village-fetches/{fetch.id}/pause")
    assert p_resp.status_code == 200
    assert p_resp.json()["status"] == "PAUSED"

    r_resp = client.post(f"/api/v1/village-fetches/{fetch.id}/resume")
    assert r_resp.status_code == 200
    assert r_resp.json()["status"] == "RUNNING"

    c_resp = client.post(f"/api/v1/village-fetches/{fetch.id}/cancel")
    assert c_resp.status_code == 200
    assert c_resp.json()["status"] == "CANCELLED"

def test_api_records_and_stats(test_hierarchy, db):
    h = test_hierarchy
    suffix = str(uuid.uuid4())[:8]
    rec = RecordDetail(
        village_id=h["vil1"].id,
        year=2026,
        doc_no=f"DOC_{suffix}",
        doc_type="विक्रीपत्र",
        seller="सचिन तेंडुलकर",
        buyer="अमोल",
        office="हवेली",
        date="10/03/2026"
    )
    db.add(rec)
    db.commit()

    resp = client.get(f"/api/v1/records?village_id={h['vil1'].id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 1
    assert any(item["doc_no"] == f"DOC_{suffix}" for item in data["items"])

    stats_resp = client.get("/api/v1/records/stats/summary")
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert "total_records" in stats
    assert "total_village_fetches" in stats


def test_sequential_survey_1_to_100_execution(test_hierarchy, db):
    """
    Verifies that execute_fetch queries 1..100 sequentially,
    updates progress on each iteration, records search counts,
    and marks COMPLETED if no truncations or errors occurred.
    """
    h = test_hierarchy
    service = VillageFetchService(db=db)
    fetch = service.create_fetch(
        district_id=h["dist1"].id,
        taluka_id=h["tal1"].id,
        village_id=h["vil1"].id,
        year=2026,
        search_query="1"
    )

    searched_queries = []

    def mock_search(req, solver):
        searched_queries.append(req.survey_query)
        assert req.article_id == ""
        assert req.article_name == ""
        return RawSearchResponse(status_code=200, content_type="text/html", body=b"<html>dummy</html>", headers={}, url="http://test")

    mock_client = MagicMock()
    mock_client.search.side_effect = mock_search

    mock_classifier = MagicMock()
    mock_classifier.classify.return_value = ResponseClassification.SUCCESS

    mock_parser = MagicMock()
    mock_parser.parse.side_effect = lambda html_bytes, year, survey_query, scope: SearchResponseDTO(
        results=[],
        retrieved_count=0,
        reported_count=0,
        truncated=False,
        year=year,
        survey_query=survey_query,
        location=scope
    )

    service.client = mock_client
    service.classifier = mock_classifier
    service.parser = mock_parser

    # Run execution with default 1..100
    completed_fetch = service.execute_fetch(fetch.id)

    assert len(searched_queries) == 100
    assert searched_queries == [str(i) for i in range(1, 101)]
    assert completed_fetch.processed_search_count == 100
    assert completed_fetch.status == VillageFetchStatus.COMPLETED.value
    assert completed_fetch.truncated_searches_count == 0
    assert completed_fetch.errors_count == 0
    assert completed_fetch.current_search_value == "100"


def test_5000_results_truncation_not_stopping(test_hierarchy, db):
    """
    Verifies that when a search query hits 5,000 results (or truncated=True):
    1. It saves/processes ALL returned rows.
    2. Does NOT stop the village fetch (continues remaining queries).
    3. Increments truncated_searches_count.
    4. Marks records with is_truncated=True.
    5. Sets final status to PARTIAL.
    """
    h = test_hierarchy
    village_id = h["vil1"].id
    service = VillageFetchService(db=db)
    fetch = service.create_fetch(
        district_id=h["dist1"].id,
        taluka_id=h["tal1"].id,
        village_id=village_id,
        year=2026,
        search_query="1"
    )

    queries_run = []

    def mock_search(req, solver):
        queries_run.append(req.survey_query)
        return RawSearchResponse(status_code=200, content_type="text/html", body=b"<html>results</html>", headers={}, url="http://test")

    mock_client = MagicMock()
    mock_client.search.side_effect = mock_search

    mock_classifier = MagicMock()
    mock_classifier.classify.return_value = ResponseClassification.SUCCESS

    truncated_dto1 = SearchResultDTO(
        sr_no="1",
        doc_no="DOC_TRUNC_1",
        doc_type="खरेदीखत",
        office="हवेली १",
        date="01/01/2026",
        seller="Seller A",
        buyer="Buyer A",
        other_info="Plot 1",
        year=2026,
        survey_query="1",
        indexii_url="/doc/1"
    )
    truncated_dto2 = SearchResultDTO(
        sr_no="2",
        doc_no="DOC_TRUNC_2",
        doc_type="खरेदीखत",
        office="हवेली १",
        date="01/01/2026",
        seller="Seller B",
        buyer="Buyer B",
        other_info="Plot 2",
        year=2026,
        survey_query="1",
        indexii_url="/doc/2"
    )

    normal_dto3 = SearchResultDTO(
        sr_no="1",
        doc_no="DOC_NORM_3",
        doc_type="खरेदीखत",
        office="हवेली १",
        date="02/01/2026",
        seller="Seller C",
        buyer="Buyer C",
        other_info="Plot 3",
        year=2026,
        survey_query="2",
        indexii_url="/doc/3"
    )

    def mock_parse(html_bytes, year, survey_query, scope):
        if survey_query == "1":
            return SearchResponseDTO(
                results=[truncated_dto1, truncated_dto2],
                retrieved_count=5000,
                reported_count=5000,
                truncated=True,
                year=year,
                survey_query=survey_query,
                location=scope
            )
        elif survey_query == "2":
            return SearchResponseDTO(
                results=[normal_dto3],
                retrieved_count=1,
                reported_count=1,
                truncated=False,
                year=year,
                survey_query=survey_query,
                location=scope
            )
        else:
            return SearchResponseDTO(
                results=[],
                retrieved_count=0,
                reported_count=0,
                truncated=False,
                year=year,
                survey_query=survey_query,
                location=scope
            )

    mock_parser = MagicMock()
    mock_parser.parse.side_effect = mock_parse

    service.client = mock_client
    service.classifier = mock_classifier
    service.parser = mock_parser

    # Execute with search_values = ["1", "2", "3"]
    result_fetch = service.execute_fetch(fetch.id, search_values=["1", "2", "3"])

    # Must NOT have stopped after survey "1"
    assert queries_run == ["1", "2", "3"]
    assert result_fetch.processed_search_count == 3
    assert result_fetch.truncated_searches_count == 1
    # Status must be PARTIAL because of truncation
    assert result_fetch.status == VillageFetchStatus.PARTIAL.value

    # Records saved check
    recs = db.query(RecordDetail).filter_by(village_id=village_id).all()
    assert len(recs) == 3
    rec1 = db.query(RecordDetail).filter_by(village_id=village_id, doc_no="DOC_TRUNC_1").first()
    assert rec1 is not None
    assert rec1.is_truncated is True
    assert rec1.reported_count == 5000

    rec3 = db.query(RecordDetail).filter_by(village_id=village_id, doc_no="DOC_NORM_3").first()
    assert rec3 is not None
    assert rec3.is_truncated is False


def test_deduplication_across_multiple_surveys(test_hierarchy, db):
    """
    Verifies that when multiple survey queries return the same document:
    1. It is saved once into record_details.
    2. duplicates_skipped is incremented.
    3. unique_records_saved counts only the distinct documents.
    """
    h = test_hierarchy
    village_id = h["vil1"].id
    service = VillageFetchService(db=db)
    fetch = service.create_fetch(
        district_id=h["dist1"].id,
        taluka_id=h["tal1"].id,
        village_id=village_id,
        year=2026,
        search_query="1"
    )

    doc_a = SearchResultDTO(
        sr_no="1", doc_no="SHARED_DOC_100", doc_type="खरेदीखत",
        office="हवेली १", date="01/01/2026", seller="A", buyer="B",
        other_info="Plot 100", year=2026, survey_query="1", indexii_url="/doc/100"
    )
    doc_b = SearchResultDTO(
        sr_no="2", doc_no="UNIQUE_DOC_101", doc_type="खरेदीखत",
        office="हवेली १", date="01/01/2026", seller="C", buyer="D",
        other_info="Plot 101", year=2026, survey_query="1", indexii_url="/doc/101"
    )
    # In survey 2, SHARED_DOC_100 appears again alongside UNIQUE_DOC_200
    doc_a_again = SearchResultDTO(
        sr_no="1", doc_no="SHARED_DOC_100", doc_type="खरेदीखत",
        office="हवेली १", date="01/01/2026", seller="A", buyer="B",
        other_info="Plot 100", year=2026, survey_query="2", indexii_url="/doc/100"
    )
    doc_c = SearchResultDTO(
        sr_no="2", doc_no="UNIQUE_DOC_200", doc_type="खरेदीखत",
        office="हवेली १", date="02/01/2026", seller="E", buyer="F",
        other_info="Plot 200", year=2026, survey_query="2", indexii_url="/doc/200"
    )

    def mock_parse(html_bytes, year, survey_query, scope):
        if survey_query == "1":
            return SearchResponseDTO(results=[doc_a, doc_b], retrieved_count=2, reported_count=2, truncated=False, year=year, survey_query=survey_query, location=scope)
        else:
            return SearchResponseDTO(results=[doc_a_again, doc_c], retrieved_count=2, reported_count=2, truncated=False, year=year, survey_query=survey_query, location=scope)

    mock_client = MagicMock()
    mock_client.search.return_value = RawSearchResponse(status_code=200, content_type="text/html", body=b"<html>ok</html>", headers={}, url="http://test")
    mock_classifier = MagicMock()
    mock_classifier.classify.return_value = ResponseClassification.SUCCESS
    mock_parser = MagicMock()
    mock_parser.parse.side_effect = mock_parse

    service.client = mock_client
    service.classifier = mock_classifier
    service.parser = mock_parser

    result = service.execute_fetch(fetch.id, search_values=["1", "2"])

    assert result.records_found == 4  # 2 in survey 1 + 2 in survey 2
    assert result.unique_records_saved == 3  # doc_a, doc_b, doc_c
    assert result.duplicates_skipped == 1  # doc_a on second survey
    assert result.status == VillageFetchStatus.COMPLETED.value


def test_partial_status_on_single_error(test_hierarchy, db):
    """
    Verifies that if one survey query encounters an error:
    1. errors_count is incremented.
    2. Workflow continues to the remaining queries.
    3. Final status is PARTIAL.
    """
    h = test_hierarchy
    service = VillageFetchService(db=db)
    fetch = service.create_fetch(
        district_id=h["dist1"].id,
        taluka_id=h["tal1"].id,
        village_id=h["vil1"].id,
        year=2026,
        search_query="1"
    )

    searched = []

    def mock_search(req, solver):
        searched.append(req.survey_query)
        if req.survey_query == "2":
            raise RuntimeError("Temporary network timeout")
        return RawSearchResponse(status_code=200, content_type="text/html", body=b"<html>ok</html>", headers={}, url="http://test")

    mock_client = MagicMock()
    mock_client.search.side_effect = mock_search
    mock_classifier = MagicMock()
    mock_classifier.classify.return_value = ResponseClassification.SUCCESS
    mock_parser = MagicMock()
    mock_parser.parse.side_effect = lambda html_bytes, year, survey_query, scope: SearchResponseDTO(
        results=[], retrieved_count=0, reported_count=0, truncated=False, year=year, survey_query=survey_query, location=scope
    )

    service.client = mock_client
    service.classifier = mock_classifier
    service.parser = mock_parser

    result = service.execute_fetch(fetch.id, search_values=["1", "2", "3"])

    assert searched == ["1", "2", "3"]
    assert result.processed_search_count == 3
    assert result.errors_count == 1
    assert "Temporary network timeout" in result.last_error
    assert result.status == VillageFetchStatus.PARTIAL.value

