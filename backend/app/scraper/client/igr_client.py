import requests
from bs4 import BeautifulSoup
from app.scraper.domain.dtos import SearchRequestDTO
from app.scraper.domain.exceptions import (
    IGRNetworkError,
    IGRSessionError,
    IGRCaptchaError,
    IGRUnexpectedResponseError,
    IGRValidationError,
    IGRRateLimitError
)
from app.scraper.client.captcha import CaptchaSolver
from app.scraper.client.raw_response import RawSearchResponse
from app.core.config import settings

BASE_URL = "https://pay2igr.igrmaharashtra.gov.in"
SEARCH_URL = f"{BASE_URL}/eDisplay/Propertydetails/index"
CAPTCHA_URL = f"{BASE_URL}/eDisplay/captcha-image"

def db_value_for_year(year: int) -> str:
    """Map a calendar year to the portal's `years` dropdown value."""
    if 2019 <= year <= 2026:
        return "3"
    elif 2012 <= year <= 2018:
        return "2"
    elif 1985 <= year <= 2002:
        return "1"
    raise IGRValidationError(
        f"Year {year} is not searchable on the portal (valid: 1985-2002, 2012-2026)", 
        retryable=False
    )

class IgrSearchClient:
    def __init__(self, timeout: int = getattr(settings, 'IGR_HTTP_TIMEOUT', 60)):
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        self.timeout = timeout
        self.session = requests.Session()
        
        retry_strategy = Retry(
            total=3,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            backoff_factor=1
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        self.session.headers.update({
            "User-Agent": getattr(settings, 'IGR_USER_AGENT', "IGR-eSearch-Client/1.0"),
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
        })
        self.csrf_token = None

    def reset_session(self):
        """Wipe cookies and connections after a network switch to prevent session corruption."""
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        
        self.session.close()
        self.session = requests.Session()
        
        retry_strategy = Retry(
            total=3,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            backoff_factor=1
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        self.session.headers.update({
            "User-Agent": getattr(settings, 'IGR_USER_AGENT', "IGR-eSearch-Client/1.0"),
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
        })
        self.csrf_token = None

    def search(self, request: SearchRequestDTO, captcha_solver: CaptchaSolver, ledger_callback=None) -> RawSearchResponse:
        """
        Executes a complete single-search flow:
        1. GET search page to establish session/CSRF
        2. GET captcha image
        3. Solve captcha via external provider
        4. POST search form
        """
        try:
            self._init_session(ledger_callback)
            captcha_text = self._get_and_solve_captcha(captcha_solver, ledger_callback)
            return self._post_search(request, captcha_text, ledger_callback)
        except (requests.Timeout, requests.ConnectionError) as e:
            raise IGRNetworkError(f"Network failure: {str(e)}") from e
        except requests.RequestException as e:
            if e.response is not None:
                raise IGRUnexpectedResponseError(f"HTTP Error {e.response.status_code}") from e
            raise IGRNetworkError(f"Request exception: {str(e)}") from e

    def _request_with_ledger(self, method: str, url: str, endpoint_name: str, ledger_callback, **kwargs):
        import datetime
        start = datetime.datetime.now(datetime.timezone.utc)
        try:
            req_func = getattr(self.session, method.lower())
            resp = req_func(url, **kwargs)
            duration = int((datetime.datetime.now(datetime.timezone.utc) - start).total_seconds() * 1000)
            if ledger_callback:
                size = len(resp.content) if isinstance(resp.content, (bytes, str)) else 0
                ledger_callback(endpoint_name, start, duration, resp.status_code, size, None, None)
            return resp
        except requests.RequestException as e:
            duration = int((datetime.datetime.now(datetime.timezone.utc) - start).total_seconds() * 1000)
            status = e.response.status_code if e.response is not None else None
            if ledger_callback:
                ledger_callback(endpoint_name, start, duration, status, 0, "HTTP_ERROR", str(e))
            raise

    def _init_session(self, ledger_callback=None):
        try:
            resp = self._request_with_ledger("GET", SEARCH_URL, "GET_search_page", ledger_callback, timeout=self.timeout)
            resp.raise_for_status()
        except (requests.Timeout, requests.ConnectionError):
            raise
        except requests.RequestException as e:
            raise IGRSessionError(f"Failed to load search page: {str(e)}") from e

        soup = BeautifulSoup(resp.text, "html.parser")
        token_input = soup.find("input", {"name": "_csrfToken"})
        if not token_input:
            raise IGRSessionError("CSRF token not found in the search page HTML")
            
        self.csrf_token = token_input.get("value", "")
        if not self.csrf_token:
            raise IGRSessionError("CSRF token was empty")

    def _get_and_solve_captcha(self, solver: CaptchaSolver, ledger_callback=None) -> str:
        try:
            resp = self._request_with_ledger("GET", CAPTCHA_URL, "GET_captcha", ledger_callback, timeout=self.timeout)
            resp.raise_for_status()
        except (requests.Timeout, requests.ConnectionError):
            raise
        except requests.RequestException as e:
            raise IGRCaptchaError(f"Failed to fetch CAPTCHA image: {str(e)}") from e
            
        if not resp.content:
            raise IGRCaptchaError("CAPTCHA image response was empty")
            
        try:
            answer = solver.solve(resp.content)
            if not answer:
                raise IGRCaptchaError("Captcha solver returned an empty string")
            return answer
        except Exception as e:
            if isinstance(e, IGRCaptchaError):
                raise
            raise IGRCaptchaError(f"Captcha solver failed: {str(e)}") from e

    def _post_search(self, request: SearchRequestDTO, captcha_text: str, ledger_callback=None) -> RawSearchResponse:
        art_id = getattr(request, "article_id", None) or (request.location and getattr(request.location, "article_id", None)) or ""
        art_name = getattr(request, "article_name", None) or (request.location and getattr(request.location, "article_name", None)) or ""

        payload = {
            "_csrfToken": self.csrf_token,
            "years": db_value_for_year(request.year),
            "district_id": request.location.district_id or "",
            "taluka_id": request.location.taluka_id or "",
            "village_id": request.location.village_id or "",
            "article_id": art_id,
            "free_text": request.survey_query,
            "partyname": "",
            "captcha": captcha_text,
            "dist_name": request.location.district_name or "",
            "tal_name": request.location.taluka_name or "",
            "article_name": art_name,
            "village_name": request.location.village_name or "",
            "freetext": "",
            "yearsel": str(request.year),
        }

        # The outer try...except catches network errors and general request errors.
        resp = self._request_with_ledger(
            "POST",
            SEARCH_URL,
            "POST_search",
            ledger_callback,
            data=payload,
            timeout=self.timeout,
            headers={"Referer": SEARCH_URL, "Origin": BASE_URL}
        )

        
        raw_response = RawSearchResponse(
            status_code=resp.status_code,
            content_type=resp.headers.get("Content-Type"),
            body=resp.content,
            headers=dict(resp.headers),
            url=resp.url
        )

        if "you have exceeded the limit of daily search results" in resp.text.lower():
            raise IGRRateLimitError("Daily search limit exceeded detected in HTML body")
            
        return raw_response
