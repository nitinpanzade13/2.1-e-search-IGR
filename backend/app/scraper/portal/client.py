import requests
from bs4 import BeautifulSoup
import os
from app.scraper.captcha.solver import read_captcha

BASE_URL = "https://pay2igr.igrmaharashtra.gov.in"
SEARCH_URL = f"{BASE_URL}/eDisplay/Propertydetails/index"
CAPTCHA_URL = f"{BASE_URL}/eDisplay/captcha-image"

class PortalClient:
    def __init__(self, api_key: str):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "curl/8.13.0",
            "Accept": "*/*",
        })
        self.api_key = api_key
        self.csrf_token = None
        
    def init_session(self):
        response = self.session.get(SEARCH_URL, timeout=60)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        token = soup.find("input", {"name": "_csrfToken"})
        if not token:
            raise RuntimeError("CSRF token not found")
        self.csrf_token = token.get("value", "")
        
    def solve_captcha(self):
        response = self.session.get(CAPTCHA_URL, timeout=60)
        response.raise_for_status()
        
        captcha_text = read_captcha(response.content, self.api_key)
        return captcha_text
        
    def search(self, year: int, survey_no: int, captcha: str, db_group_year: str, 
               district_id: str, taluka_id: str, village_id: str,
               district_name: str, taluka_name: str, village_name: str):
        
        payload = {
            "_csrfToken": self.csrf_token,
            "years": db_group_year,
            "district_id": district_id,
            "taluka_id": taluka_id,
            "village_id": village_id,
            "article_id": "",
            "free_text": str(survey_no),
            "partyname": "",
            "captcha": captcha,
            "dist_name": district_name,
            "tal_name": taluka_name,
            "article_name": "",
            "village_name": village_name,
            "freetext": "",
            "yearsel": str(year),
        }
        
        response = self.session.post(
            SEARCH_URL,
            data=payload,
            timeout=180,
            headers={"Referer": SEARCH_URL, "Origin": BASE_URL},
        )
        response.raise_for_status()
        return response.text
