from bs4 import BeautifulSoup
from app.scraper.domain.enums import ResponseClassification
from app.scraper.client.raw_response import RawSearchResponse

class ResponseClassifier:
    """
    Pure component to classify raw HTTP responses from the IGR portal.
    It inspects HTTP status codes and HTML structure/flash messages to determine
    the semantic outcome, without parsing domain records or managing network state.
    """

    def classify(self, response: RawSearchResponse) -> ResponseClassification:
        if not response.body:
            return ResponseClassification.UNEXPECTED_RESPONSE
            
        html = response.body.decode('utf-8', errors='replace')
        
        # 1. RATE_LIMITED check: The exact daily limit message
        # We normalize whitespace to be tolerant of HTML formatting but keep the wording exact.
        normalized_html = " ".join(html.split()).lower()
        exact_rate_limit_msg = "you have exceeded the limit of daily search results"
        if exact_rate_limit_msg in normalized_html.replace(".", ""):
            return ResponseClassification.RATE_LIMITED

        # 2. Non-200 HTTP codes (without known semantic bodies like rate limits) are unexpected
        if response.status_code != 200:
            return ResponseClassification.UNEXPECTED_RESPONSE

        # Extract the flash message where the portal communicates form errors
        soup = BeautifulSoup(html, "html.parser")
        msg_div = soup.find("div", class_="message")
        flash_message = msg_div.get_text(" ", strip=True).lower() if msg_div else ""

        # 3. CAPTCHA_FAILED check: Legacy implementation relied on "captcha" in the flash message
        if "captcha" in flash_message:
            return ResponseClassification.CAPTCHA_FAILED
            
        # Note: The legacy implementation did not provide explicit strings for 
        # VALIDATION_ERROR or AUTH_SESSION_ERROR (it treated a blank form as a dropped session).
        # To remain conservative and avoid inventing unsupported behavior, we do not guess these.
            
        # 4. SUCCESS check: A valid search result contains the tableparty table
        table = soup.find("table", id="tableparty")
        if table is not None:
            return ResponseClassification.SUCCESS
            
        # 5. UNEXPECTED_RESPONSE fallback for unrecognized HTML formats
        return ResponseClassification.UNEXPECTED_RESPONSE
