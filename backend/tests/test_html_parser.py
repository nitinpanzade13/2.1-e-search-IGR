import pytest
from app.scraper.parser.html_parser import PureHtmlParser
from app.scraper.domain.dtos import SearchScopeDTO
from app.scraper.domain.exceptions import IGRParserError

@pytest.fixture
def parser():
    return PureHtmlParser()

@pytest.fixture
def scope():
    return SearchScopeDTO(district_name="Pune")

def make_html(rows_html: str, msg: str = "") -> bytes:
    return f"""
    <html>
    <body>
        <div class="message">{msg}</div>
        <table id="tableparty">
            <thead>
                <tr>
                    <th>अनु क्र.</th>
                    <th>दस्त क्र.</th>
                    <th>दस्त प्रकार</th>
                    <th>दू. नि. कार्यालय</th>
                    <th>दिनांक</th>
                    <th>लिहून देणार</th>
                    <th>लिहून घेणार</th>
                    <th>इतर माहीती</th>
                    <th>सूची क्र. २</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </body>
    </html>
    """.encode("utf-8")

def test_parse_valid_row(parser, scope):
    row_html = """
    <tr id="tbdata">
        <td>1</td>
        <td>1234</td>
        <td>Sale Deed</td>
        <td>Pune SRO</td>
        <td>01/01/2026</td>
        <td>John Doe<br>Jane Doe</td>
        <td>Acme Corp</td>
        <td>Survey 123</td>
        <td><a href="/indexii/1234">View</a></td>
    </tr>
    """
    html = make_html(row_html, "1 Records found")
    resp = parser.parse(html, 2026, "survey", scope)
    
    assert resp.retrieved_count == 1
    assert resp.reported_count == 1
    assert not resp.truncated
    
    res = resp.results[0]
    assert res.sr_no == "1"
    assert res.doc_no == "1234"
    assert res.seller == "John Doe\nJane Doe"  # Checks <br> replacement
    assert res.indexii_url == "/indexii/1234"
    assert res.year == 2026

def test_missing_tableparty(parser, scope):
    with pytest.raises(IGRParserError) as exc:
        parser.parse(b"<html></html>", 2026, "survey", scope)
    assert "Missing tableparty" in str(exc.value)

def test_missing_required_header(parser, scope):
    html = b"""
    <html>
        <table id="tableparty">
            <thead><tr><th>Wrong</th></tr></thead>
        </table>
    </html>
    """
    with pytest.raises(IGRParserError) as exc:
        parser.parse(html, 2026, "survey", scope)
    assert "Missing required column" in str(exc.value)

def test_insufficient_cells(parser, scope):
    row_html = '<tr id="tbdata"><td>1</td></tr>'
    html = make_html(row_html)
    with pytest.raises(IGRParserError) as exc:
        parser.parse(html, 2026, "survey", scope)
    assert "insufficient cells" in str(exc.value)

def test_missing_indexii_link(parser, scope):
    row_html = """
    <tr id="tbdata">
        <td>1</td><td>1234</td><td>Sale Deed</td><td>Pune SRO</td>
        <td>01/01/2026</td><td>John Doe</td><td>Acme Corp</td>
        <td>Survey 123</td>
        <td>No Link Here</td>
    </tr>
    """
    html = make_html(row_html)
    with pytest.raises(IGRParserError) as exc:
        parser.parse(html, 2026, "survey", scope)
    assert "Missing Index II link in cell" in str(exc.value)

def test_duplicate_rows(parser, scope):
    row_html = """
    <tr id="tbdata">
        <td>1</td><td>1234</td><td>Type</td><td>Office</td>
        <td>Date</td><td>Seller</td><td>Buyer</td><td>Info</td>
        <td><a href="/link1">View</a></td>
    </tr>
    """
    # Duplicate the exact row
    html = make_html(row_html + row_html)
    resp = parser.parse(html, 2026, "survey", scope)
    
    assert resp.retrieved_count == 2
    assert resp.results[0].doc_no == "1234"
    assert resp.results[1].doc_no == "1234"

def test_truncation_marker(parser, scope):
    # If reported is 6000 but retrieved is 1, it's truncated
    row_html = """
    <tr id="tbdata">
        <td>1</td><td>1234</td><td>Type</td><td>Office</td>
        <td>Date</td><td>Seller</td><td>Buyer</td><td>Info</td>
        <td><a href="/link1">View</a></td>
    </tr>
    """
    html = make_html(row_html, "6000 Records found")
    resp = parser.parse(html, 2026, "survey", scope)
    assert resp.truncated is True
    assert resp.reported_count == 6000
    assert resp.retrieved_count == 1
def test_header_exact_matching(parser, scope):
    # '???? ???.' shouldn't match a column named '???????? ???? ???.'
    html = b"""
    <html>
        <table id="tableparty">
            <thead>
                <tr>
                    <th>??? ???.</th>
                    <th>???????? ???? ???.</th>
                    <th>???? ??????</th>
                    <th>??. ??. ????????</th>
                    <th>??????</th>
                    <th>????? ?????</th>
                    <th>????? ?????</th>
                    <th>??? ??????</th>
                    <th>???? ???. ?</th>
                </tr>
            </thead>
            <tbody></tbody>
        </table>
    </html>
    """
    with pytest.raises(IGRParserError) as exc:
        parser.parse(html, 2026, "survey", scope)
    assert "Missing required column" in str(exc.value)
def test_parser_is_pure(parser, scope):
    # Ensure no HTTP requests or filesystem writes occur during parsing
    from unittest import mock
    row_html = """<tr id="tbdata"><td>1</td><td>1234</td><td>Sale Deed</td><td>Pune SRO</td><td>01/01/2026</td><td>John Doe</td><td>Acme Corp</td><td>Survey 123</td><td><a href="/indexii/1234">View</a></td></tr>"""
    html = make_html(row_html)
    
    with mock.patch("requests.Session.get") as mock_get, \
         mock.patch("requests.Session.post") as mock_post, \
         mock.patch("builtins.open") as mock_open:
         
        parser.parse(html, 2026, "survey", scope)
        
        mock_get.assert_not_called()
        mock_post.assert_not_called()
        mock_open.assert_not_called()
