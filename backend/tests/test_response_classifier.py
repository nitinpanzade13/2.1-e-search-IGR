import pytest
from app.scraper.domain.enums import ResponseClassification
from app.scraper.client.raw_response import RawSearchResponse
from app.scraper.client.response_classifier import ResponseClassifier

@pytest.fixture
def classifier():
    return ResponseClassifier()

def make_response(body: str, status: int = 200) -> RawSearchResponse:
    return RawSearchResponse(
        status_code=status,
        content_type="text/html",
        body=body.encode("utf-8"),
        headers={},
        url="http://fake"
    )

def test_success_tableparty(classifier):
    html = "<html><body><table id='tableparty'><tbody><tr><td>Result</td></tr></tbody></table></body></html>"
    resp = make_response(html)
    assert classifier.classify(resp) == ResponseClassification.SUCCESS

def test_exact_daily_limit(classifier):
    html = "<html><body>You have exceeded the limit of daily search results.</body></html>"
    resp = make_response(html)
    assert classifier.classify(resp) == ResponseClassification.RATE_LIMITED

def test_case_whitespace_daily_limit(classifier):
    html = "<html><body>   YOU HAVE   exceeded the LIMIT \n of daily search results   </body></html>"
    resp = make_response(html)
    assert classifier.classify(resp) == ResponseClassification.RATE_LIMITED

def test_generic_limit_word_ignored(classifier):
    html = "<html><body>Your search limit is high.</body></html>"
    resp = make_response(html)
    # Since it lacks tableparty and lacks the exact rate limit, it falls back to unexpected
    assert classifier.classify(resp) == ResponseClassification.UNEXPECTED_RESPONSE

def test_captcha_failed(classifier):
    html = "<html><body><div class='message'>Invalid Captcha entered.</div></body></html>"
    resp = make_response(html)
    assert classifier.classify(resp) == ResponseClassification.CAPTCHA_FAILED

def test_known_validation_error_unsupported_fallback(classifier):
    # The legacy code has no reliable validation error marker.
    # Therefore, a page with a generic validation error should fallback conservatively to UNEXPECTED.
    html = "<html><body><div class='message'>Invalid District ID.</div></body></html>"
    resp = make_response(html)
    assert classifier.classify(resp) == ResponseClassification.UNEXPECTED_RESPONSE

def test_known_session_error_unsupported_fallback(classifier):
    # Legacy code treated blank forms without messages as dropped sessions.
    # To remain conservative without inventing source behavior, we classify this as UNEXPECTED.
    html = "<html><body><form id='searchForm'></form></body></html>"
    resp = make_response(html)
    assert classifier.classify(resp) == ResponseClassification.UNEXPECTED_RESPONSE

def test_unknown_html_response(classifier):
    html = "<html><body><h1>Welcome to Portal</h1></body></html>"
    resp = make_response(html)
    assert classifier.classify(resp) == ResponseClassification.UNEXPECTED_RESPONSE

def test_http_403_without_semantic_marker(classifier):
    resp = make_response("Forbidden", status=403)
    assert classifier.classify(resp) == ResponseClassification.UNEXPECTED_RESPONSE

def test_http_500_without_semantic_marker(classifier):
    resp = make_response("Internal Server Error", status=500)
    assert classifier.classify(resp) == ResponseClassification.UNEXPECTED_RESPONSE

def test_empty_response(classifier):
    resp = make_response("")
    assert classifier.classify(resp) == ResponseClassification.UNEXPECTED_RESPONSE

def test_non_html_content(classifier):
    resp = RawSearchResponse(
        status_code=200,
        content_type="application/json",
        body=b'{"status": "ok"}',
        headers={},
        url="http://fake"
    )
    # It has no tableparty or known messages, so UNEXPECTED_RESPONSE
    assert classifier.classify(resp) == ResponseClassification.UNEXPECTED_RESPONSE
def test_daily_limit_non_200_status(classifier):
    html = (
        "<html><body>"
        "You have exceeded the limit of daily search results."
        "</body></html>"
    )
    resp = make_response(html, status=429)

    assert classifier.classify(resp) == ResponseClassification.RATE_LIMITED
