import pytest
from unittest.mock import MagicMock, patch
import requests
from app.scraper.domain.dtos import SearchRequestDTO, SearchScopeDTO
from app.scraper.domain.exceptions import (
    IGRNetworkError,
    IGRSessionError,
    IGRCaptchaError,
    IGRRateLimitError,
    IGRUnexpectedResponseError,
    IGRValidationError
)
from app.scraper.client.igr_client import IgrSearchClient, db_value_for_year
from app.scraper.client.captcha import CaptchaSolver

class FakeCaptchaSolver:
    def solve(self, image_bytes: bytes) -> str:
        if image_bytes == b"bad":
            raise Exception("Solver crashed")
        if image_bytes == b"empty":
            return ""
        return "123456"

@pytest.fixture
def mock_session():
    with patch("app.scraper.client.igr_client.requests.Session") as MockSession:
        session_instance = MagicMock()
        MockSession.return_value = session_instance
        yield session_instance

@pytest.fixture
def client(mock_session):
    return IgrSearchClient(timeout=10)

@pytest.fixture
def search_req():
    scope = SearchScopeDTO(district_id="1", taluka_id="2", village_id="3")
    return SearchRequestDTO(year=2026, survey_query="42", location=scope)

def test_db_value_for_year():
    assert db_value_for_year(2026) == "3"
    assert db_value_for_year(2015) == "2"
    assert db_value_for_year(1999) == "1"
    
    with pytest.raises(IGRValidationError):
        db_value_for_year(2005)

def test_successful_flow(client, mock_session, search_req):
    # Mock search page GET
    mock_get_search = MagicMock()
    mock_get_search.text = '<html><input name="_csrfToken" value="fake_token"></html>'
    
    # Mock captcha GET
    mock_get_captcha = MagicMock()
    mock_get_captcha.content = b"fake_image_bytes"
    
    # Configure session.get to return appropriate mocks
    def get_side_effect(url, **kwargs):
        if "captcha-image" in url:
            return mock_get_captcha
        return mock_get_search
        
    mock_session.get.side_effect = get_side_effect
    
    # Mock POST
    mock_post = MagicMock()
    mock_post.status_code = 200
    mock_post.headers = {"Content-Type": "text/html"}
    mock_post.content = b"<html>Success result</html>"
    mock_post.text = "<html>Success result</html>"
    mock_post.url = "http://fake"
    mock_session.post.return_value = mock_post
    
    response = client.search(search_req, FakeCaptchaSolver())
    
    assert response.status_code == 200
    assert response.body == b"<html>Success result</html>"
    
    # Verify request payload includes empty article_id and article_name when not selected
    post_args = mock_session.post.call_args[1]["data"]
    assert post_args["_csrfToken"] == "fake_token"
    assert post_args["captcha"] == "123456"
    assert post_args["years"] == "3"
    assert post_args["yearsel"] == "2026"
    assert post_args["free_text"] == "42"
    assert post_args["article_id"] == ""
    assert post_args["article_name"] == ""

def test_specified_article_selection_payload(client, mock_session):
    mock_get_search = MagicMock()
    mock_get_search.text = '<html><input name="_csrfToken" value="fake_token"></html>'
    mock_get_captcha = MagicMock()
    mock_get_captcha.content = b"fake_image_bytes"
    mock_session.get.side_effect = lambda url, **kwargs: mock_get_captcha if "captcha-image" in url else mock_get_search
    
    mock_post = MagicMock()
    mock_post.status_code = 200
    mock_post.headers = {"Content-Type": "text/html"}
    mock_post.content = b"<html>Success result</html>"
    mock_post.text = "<html>Success result</html>"
    mock_session.post.return_value = mock_post

    req_with_article = SearchRequestDTO(
        year=2026,
        survey_query="42",
        location=SearchScopeDTO(district_id="1", taluka_id="2", village_id="3", article_id="25", article_name="Sale Deed"),
        article_id="25",
        article_name="Sale Deed"
    )
    client.search(req_with_article, FakeCaptchaSolver())
    post_args = mock_session.post.call_args[1]["data"]
    assert post_args["article_id"] == "25"
    assert post_args["article_name"] == "Sale Deed"

def test_network_failure(client, mock_session, search_req):
    mock_session.get.side_effect = requests.ConnectionError("Failed to connect")
    with pytest.raises(IGRNetworkError) as exc:
        client.search(search_req, FakeCaptchaSolver())
    assert "Network failure" in str(exc.value)

def test_timeout(client, mock_session, search_req):
    mock_session.get.side_effect = requests.Timeout("Timed out")
    with pytest.raises(IGRNetworkError) as exc:
        client.search(search_req, FakeCaptchaSolver())
    assert "Network failure" in str(exc.value)

def test_missing_csrf(client, mock_session, search_req):
    mock_get = MagicMock()
    mock_get.text = '<html>No token here</html>'
    mock_session.get.return_value = mock_get
    
    with pytest.raises(IGRSessionError) as exc:
        client.search(search_req, FakeCaptchaSolver())
    assert "CSRF token not found" in str(exc.value)

def test_urllib3_retry_config():
    client_real = IgrSearchClient(timeout=10)
    adapter = client_real.session.adapters["https://"]
    assert adapter.max_retries.total == 3
    assert 500 in adapter.max_retries.status_forcelist
    assert 502 in adapter.max_retries.status_forcelist
    assert 503 in adapter.max_retries.status_forcelist
    assert 504 in adapter.max_retries.status_forcelist
    assert "GET" in adapter.max_retries.allowed_methods
    assert "POST" in adapter.max_retries.allowed_methods

def test_captcha_retrieval_failure(client, mock_session, search_req):
    mock_get_search = MagicMock()
    mock_get_search.text = '<html><input name="_csrfToken" value="token"></html>'
    
    def get_side_effect(url, **kwargs):
        if "captcha-image" in url:
            raise requests.RequestException("Captcha 404")
        return mock_get_search
        
    mock_session.get.side_effect = get_side_effect
    
    with pytest.raises(IGRCaptchaError) as exc:
        client.search(search_req, FakeCaptchaSolver())
    assert "Failed to fetch CAPTCHA image" in str(exc.value)

def test_captcha_solver_failure(client, mock_session, search_req):
    mock_get_search = MagicMock()
    mock_get_search.text = '<html><input name="_csrfToken" value="token"></html>'
    
    mock_get_captcha = MagicMock()
    mock_get_captcha.content = b"bad"
    
    def get_side_effect(url, **kwargs):
        if "captcha-image" in url:
            return mock_get_captcha
        return mock_get_search
        
    mock_session.get.side_effect = get_side_effect
    
    with pytest.raises(IGRCaptchaError) as exc:
        client.search(search_req, FakeCaptchaSolver())
    assert "Captcha solver failed" in str(exc.value)

def test_rate_limit_response(client, mock_session, search_req):
    mock_get_search = MagicMock()
    mock_get_search.text = '<html><input name="_csrfToken" value="token"></html>'
    
    mock_get_captcha = MagicMock()
    mock_get_captcha.content = b"fake"
    
    def get_side_effect(url, **kwargs):
        if "captcha-image" in url:
            return mock_get_captcha
        return mock_get_search
        
    mock_session.get.side_effect = get_side_effect
    
    mock_post = MagicMock()
    mock_post.status_code = 200
    mock_post.text = "you have exceeded the limit of daily search results."
    mock_post.headers = {}
    mock_post.content = b""
    mock_session.post.return_value = mock_post
    
    with pytest.raises(IGRRateLimitError) as exc:
        client.search(search_req, FakeCaptchaSolver())
    assert "Daily search limit exceeded" in str(exc.value)

def test_unexpected_http_response(client, mock_session, search_req):
    mock_get_search = MagicMock()
    mock_get_search.text = '<html><input name="_csrfToken" value="token"></html>'
    
    mock_get_captcha = MagicMock()
    mock_get_captcha.content = b"fake"
    
    def get_side_effect(url, **kwargs):
        if "captcha-image" in url:
            return mock_get_captcha
        return mock_get_search
        
    mock_session.get.side_effect = get_side_effect
    
    # POST returns a response but raise_for_status() raises
    mock_post = MagicMock()
    mock_post.status_code = 500
    
    e = requests.HTTPError("500 Error")
    e.response = mock_post
    mock_post.raise_for_status.side_effect = e
    mock_session.post.return_value = mock_post
    
    resp = client.search(search_req, FakeCaptchaSolver())
    assert resp.status_code == 500
def test_captcha_timeout(client, mock_session, search_req):
    mock_get_search = MagicMock()
    mock_get_search.text = '<html><input name="_csrfToken" value="token"></html>'
    
    def get_side_effect(url, **kwargs):
        if "captcha-image" in url:
            raise requests.Timeout("Captcha Timeout")
        return mock_get_search
        
    mock_session.get.side_effect = get_side_effect
    
    with pytest.raises(IGRNetworkError) as exc:
        client.search(search_req, FakeCaptchaSolver())
    assert "Network failure" in str(exc.value)

def test_captcha_connection_failure(client, mock_session, search_req):
    mock_get_search = MagicMock()
    mock_get_search.text = '<html><input name="_csrfToken" value="token"></html>'
    
    def get_side_effect(url, **kwargs):
        if "captcha-image" in url:
            raise requests.ConnectionError("Captcha ConnErr")
        return mock_get_search
        
    mock_session.get.side_effect = get_side_effect
    
    with pytest.raises(IGRNetworkError) as exc:
        client.search(search_req, FakeCaptchaSolver())
    assert "Network failure" in str(exc.value)

def test_captcha_empty_body(client, mock_session, search_req):
    mock_get_search = MagicMock()
    mock_get_search.text = '<html><input name="_csrfToken" value="token"></html>'
    
    mock_get_captcha = MagicMock()
    mock_get_captcha.content = b""
    
    def get_side_effect(url, **kwargs):
        if "captcha-image" in url:
            return mock_get_captcha
        return mock_get_search
        
    mock_session.get.side_effect = get_side_effect
    
    with pytest.raises(IGRCaptchaError) as exc:
        client.search(search_req, FakeCaptchaSolver())
    assert "CAPTCHA image response was empty" in str(exc.value)

def test_unexpected_http_response_403(client, mock_session, search_req):
    mock_get_search = MagicMock()
    mock_get_search.text = '<html><input name="_csrfToken" value="token"></html>'
    mock_get_captcha = MagicMock()
    mock_get_captcha.content = b"fake"
    
    def get_side_effect(url, **kwargs):
        if "captcha-image" in url: return mock_get_captcha
        return mock_get_search
    mock_session.get.side_effect = get_side_effect
    
    mock_post = MagicMock()
    mock_post.status_code = 403
    
    e = requests.HTTPError("403 Forbidden")
    e.response = mock_post
    mock_post.raise_for_status.side_effect = e
    mock_session.post.return_value = mock_post
    
    resp = client.search(search_req, FakeCaptchaSolver())
    assert resp.status_code == 403
