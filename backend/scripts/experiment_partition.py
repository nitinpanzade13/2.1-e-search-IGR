import asyncio
import datetime
import hashlib
from app.scraper.client.igr_client import IgrSearchClient
from app.scraper.client.openai_captcha_solver import OpenAICaptchaSolver
from app.scraper.domain.dtos import SearchRequestDTO, SearchScopeDTO
from app.scraper.parser.html_parser import PureHtmlParser

def calculate_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()

def normalize_identity(row):
    return (row.source_token, row.doc_no, row.year, row.office)

def execute_search(client, captcha_solver, parser, year, dist, tal, vil, free_text, article_id, partyname=""):
    print(f"\n--- Request: article_id='{article_id}', free_text='{free_text}', party='{partyname}' ---")
    
    # We must patch the client._post_search payload temporarily for this experiment
    original_post_search = client._post_search
    
    def _patched_post_search(request, captcha_text, ledger_callback=None):
        from app.scraper.client.igr_client import db_value_for_year, SEARCH_URL, RawSearchResponse
        payload = {
            "_csrfToken": client.csrf_token,
            "years": db_value_for_year(request.year),
            "district_id": request.location.district_id or "",
            "taluka_id": request.location.taluka_id or "",
            "village_id": request.location.village_id or "",
            "article_id": article_id,
            "free_text": request.survey_query,
            "partyname": partyname,
            "captcha": captcha_text,
            "dist_name": request.location.district_name or "",
            "tal_name": request.location.taluka_name or "",
            "article_name": "",
            "village_name": request.location.village_name or "",
            "freetext": "",
            "yearsel": str(request.year),
        }
        resp = client._request_with_ledger(
            "POST",
            SEARCH_URL,
            "POST_search",
            ledger_callback,
            data=payload,
            timeout=client.timeout,
            headers={"Referer": SEARCH_URL, "Origin": "https://pay2igr.igrmaharashtra.gov.in"}
        )
        resp.raise_for_status()
        raw_response = RawSearchResponse(
            status_code=resp.status_code,
            content_type=resp.headers.get("Content-Type"),
            body=resp.content,
            headers=dict(resp.headers),
            url=resp.url
        )
        if "you have exceeded the limit of daily search results" in resp.text.lower():
            from app.scraper.domain.exceptions import IGRRateLimitError
            raise IGRRateLimitError("Daily search limit exceeded")
        return raw_response

    client._post_search = _patched_post_search
    
    try:
        req = SearchRequestDTO(
            year=year,
            survey_query=free_text,
            location=SearchScopeDTO(district_id=dist, taluka_id=tal, village_id=vil)
        )
        raw_resp = client.search(req, captcha_solver)
        
        parsed = parser.parse(raw_resp.body.decode('utf-8', errors='replace'), req)
        
        identities = set([normalize_identity(r) for r in parsed.results])
        unique_tokens = len(set([r.source_token for r in parsed.results if r.source_token]))
        unique_docs = len(set([r.doc_no for r in parsed.results]))
        
        print(f"HTTP Status: {raw_resp.status_code}")
        print(f"Reported Count: {parsed.reported_count}")
        print(f"Retrieved Count: {parsed.retrieved_count}")
        print(f"Truncated: {parsed.truncated}")
        print(f"Unique Source Tokens: {unique_tokens}")
        print(f"Unique Doc Nos: {unique_docs}")
        print(f"HTML SHA-256: {calculate_sha256(raw_resp.body)}")
        
        # Look for pagination in HTML
        html_lower = raw_resp.body.decode('utf-8', errors='replace').lower()
        has_page = "page" in html_lower
        has_next = "next" in html_lower
        has_offset = "offset" in html_lower
        has_viewstate = "__viewstate" in html_lower
        
        print(f"Pagination hints -> page:{has_page}, next:{has_next}, offset:{has_offset}, __viewstate:{has_viewstate}")
        
        return parsed, identities
    finally:
        client._post_search = original_post_search


def run():
    client = IgrSearchClient()
    captcha = OpenAICaptchaSolver()
    parser = PureHtmlParser()
    
    year = 2026
    dist = "23" # Pune
    tal = "1"   # Haveli
    vil = "43"  # Kharadi
    
    try:
        # A - Baseline
        _, base_ids = execute_search(client, captcha, parser, year, dist, tal, vil, " ", "")
        
        # B - Article ID Partition
        _, a25_ids = execute_search(client, captcha, parser, year, dist, tal, vil, " ", "25")
        _, a157_ids = execute_search(client, captcha, parser, year, dist, tal, vil, " ", "157")
        
        article_union = a25_ids.union(a157_ids)
        print("\n--- Article ID overlap ---")
        print(f"Total from 25+157: {len(article_union)}")
        print(f"Intersection with Baseline: {len(article_union.intersection(base_ids))}")
        
        # C - Free Text Partition
        _, t1_ids = execute_search(client, captcha, parser, year, dist, tal, vil, "1", "")
        _, t2_ids = execute_search(client, captcha, parser, year, dist, tal, vil, "2", "")
        
        text_union = t1_ids.union(t2_ids)
        print("\n--- Free Text overlap ---")
        print(f"Total from '1'+'2': {len(text_union)}")
        print(f"Intersection '1' and '2': {len(t1_ids.intersection(t2_ids))}")
        print(f"Intersection with Baseline: {len(text_union.intersection(base_ids))}")
        
    except Exception as e:
        print(f"Experiment interrupted: {e}")

if __name__ == "__main__":
    run()
