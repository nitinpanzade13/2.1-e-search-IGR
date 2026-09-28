import os
import time
from dotenv import load_dotenv
from app.scraper.portal.client import PortalClient
from app.scraper.parser import igr_parser
import json

def get_db_group_for_year(year: int):
    YEAR_DB_GROUPS = {
        3: range(2019, 2027),
        2: range(2012, 2019),
        1: range(1985, 2003),
    }
    for value, years in YEAR_DB_GROUPS.items():
        if year in years:
            return str(value)
    raise ValueError(f"Year {year} not searchable")

def run_test_scrape():
    load_dotenv(override=True)
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("MISSING OPENAI_API_KEY, will use manual CAPTCHA entry.")
        
    year = int(os.environ.get("SCRAPER_YEAR", 2024))
    survey_no = int(os.environ.get("SCRAPER_SEARCH_PARAMETERS", 1))
    district_id = os.environ.get("IGR_DISTRICT_ID", "23")
    taluka_id = os.environ.get("IGR_TALUKA_ID", "1")
    village_id = os.environ.get("IGR_VILLAGE_ID", "43")
    dist_name = os.environ.get("IGR_DISTRICT", "पुणे")
    tal_name = os.environ.get("IGR_TALUKA", "हवेली")
    vill_name = os.environ.get("IGR_VILLAGE", "खराडी (पुणे महापालिकेमध्ये समाविष्ट)")
    
    print(f"Starting test scrape for Year: {year}, Survey: {survey_no}")
    
    client = PortalClient(api_key=api_key)
    
    for attempt in range(1, 4):
        print(f"Attempt {attempt}...")
        client.init_session()
        print("Session initialized. Solving CAPTCHA...")
        captcha = client.solve_captcha()
        
        if not captcha:
            print("Failed to solve CAPTCHA.")
            continue
            
        print(f"CAPTCHA solved: {captcha}. Submitting search...")
        
        html = client.search(
            year=year,
            survey_no=survey_no,
            captcha=captcha,
            db_group_year=get_db_group_for_year(year),
            district_id=district_id,
            taluka_id=taluka_id,
            village_id=village_id,
            district_name=dist_name,
            taluka_name=tal_name,
            village_name=vill_name
        )
        
        verdict = igr_parser.classify(html)
        print(f"Verdict: {verdict}")
        
        if verdict["outcome"] == igr_parser.BAD_CAPTCHA:
            print("Bad CAPTCHA, retrying...")
            continue
            
        if verdict["outcome"] == igr_parser.RATE_LIMITED:
            print("Rate limited.")
            break
            
        # Save raw HTML
        os.makedirs("storage/raw", exist_ok=True)
        raw_path = f"storage/raw/test_response_{year}_{survey_no}.html"
        with open(raw_path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Raw HTML saved to {raw_path}")
            
        if verdict["outcome"] == igr_parser.OK:
            rows = igr_parser.parse_rows(html, year, survey_no, base_url="https://pay2igr.igrmaharashtra.gov.in")
            print(f"Parsed {len(rows)} rows.")
            if rows:
                print("\nSample Record:")
                print(rows[0].model_dump_json(indent=2))
                
                # Save parsed results for inspection
                with open("storage/raw/parsed_records.json", "w", encoding="utf-8") as f:
                    json.dump([r.model_dump() for r in rows], f, indent=2, ensure_ascii=False)
                    
            break
        elif verdict["outcome"] == igr_parser.NO_RECORDS:
            print("No records found.")
            break
        else:
            print("Unknown outcome.")
            break

if __name__ == "__main__":
    run_test_scrape()
