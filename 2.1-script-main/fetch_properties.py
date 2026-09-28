import requests
from bs4 import BeautifulSoup
from pathlib import Path
import json
import time

BASE_URL = "https://pay2igr.igrmaharashtra.gov.in"
PROPERTY_URL = BASE_URL + "/eDisplay/Propertydetails/index"
CAPTCHA_URL = BASE_URL + "/eDisplay/captcha-image"

OUTPUT_DIR = Path("responses")
OUTPUT_DIR.mkdir(exist_ok=True)

PROGRESS_FILE = Path("progress.json")
BATCH_SIZE = 5


def load_progress():
    """Load progress from file."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    return {"last_property": 0, "completed": []}


def save_progress(progress):
    """Save progress to file."""
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)


def get_existing_properties():
    """Get list of already downloaded property numbers."""
    existing = []
    for file in OUTPUT_DIR.glob("property_*.html"):
        try:
            num = int(file.stem.split('_')[1])
            existing.append(num)
        except:
            pass
    return sorted(existing)


def create_session():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "curl/8.13.0",
        "Accept": "*/*",
    })
    return session


def get_property_page(session):
    response = session.get(PROPERTY_URL, timeout=60)
    response.raise_for_status()
    return response.text


def get_csrf_token(html):
    soup = BeautifulSoup(html, "html.parser")
    token = soup.find("input", {"name": "_csrfToken"})
    if not token:
        raise RuntimeError("CSRF token not found")
    return token.get("value", "")


def download_captcha(session):
    response = session.get(CAPTCHA_URL, timeout=60)
    response.raise_for_status()
    captcha_path = Path("captcha.png")
    captcha_path.write_bytes(response.content)
    return captcha_path


def search_property(session, csrf_token, captcha, property_num):
    payload = {
        "_csrfToken": csrf_token,
        "years": "3",
        "district_id": "23",
        "taluka_id": "1",
        "village_id": "43",
        "article_id": "",
        "free_text": str(property_num),
        "partyname": "",
        "captcha": captcha,
        "dist_name": "पुणे",
        "tal_name": "हवेली",
        "article_name": "",
        "village_name": "खराडी (पुणे महापालिकेमध्ये समाविष्ट)",
        "freetext": "",
        "yearsel": "2026",
    }

    response = session.post(
        PROPERTY_URL,
        data=payload,
        timeout=120,
        headers={
            "Referer": PROPERTY_URL,
            "Origin": BASE_URL,
        }
    )
    response.raise_for_status()
    return response


def check_response_valid(response):
    """Check if response contains property data (not CAPTCHA error)."""
    html = response.text
    if "Invalid CAPTCHA" in html:
        return False, "Invalid CAPTCHA"
    if "message error" in html:
        return False, "Error in response"
    # Check if response has property table with data
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", {"id": "tableparty"})
    if table:
        tbody = table.find("tbody")
        if tbody and tbody.find("tr"):
            return True, "Property data found"
    return False, "No property data found"


def main():
    print("\n" + "=" * 80)
    print("IGR PROPERTY BATCH FETCHER")
    print("=" * 80)
    
    # Load progress
    progress = load_progress()
    existing = get_existing_properties()
    
    print(f"\nProgress:")
    print(f"  Last fetched: Property #{progress['last_property']}")
    print(f"  Total completed: {len(progress['completed'])} properties")
    print(f"  Existing files: {len(existing)} properties")
    
    if existing:
        print(f"  Downloaded: {existing}")
    
    # Determine next batch
    start_num = progress['last_property'] + 1
    
    # Skip already existing properties
    while start_num in existing:
        print(f"  Property #{start_num} already exists, skipping...")
        start_num += 1
    
    end_num = start_num + BATCH_SIZE - 1
    
    print(f"\n{'=' * 80}")
    print(f"BATCH: Fetching properties {start_num} to {end_num}")
    print(f"{'=' * 80}")
    
    batch_results = {
        "success": [],
        "failed": [],
        "skipped": []
    }
    
    current_num = start_num
    fetched_count = 0
    
    while fetched_count < BATCH_SIZE:
        # Skip if already exists
        if current_num in existing:
            print(f"\n[{fetched_count + 1}/{BATCH_SIZE}] Property #{current_num} - SKIPPED (already exists)")
            batch_results["skipped"].append(current_num)
            current_num += 1
            continue
        
        print(f"\n{'=' * 80}")
        print(f"[{fetched_count + 1}/{BATCH_SIZE}] FETCHING PROPERTY #{current_num}")
        print(f"{'=' * 80}")
        
        try:
            # Create fresh session
            session = create_session()
            
            # Get property page
            print("  → Getting property page...")
            html = get_property_page(session)
            
            # Get CSRF token
            csrf_token = get_csrf_token(html)
            print(f"  → CSRF token obtained ({len(csrf_token)} chars)")
            
            # Download CAPTCHA
            print("  → Downloading CAPTCHA...")
            captcha_path = download_captcha(session)
            
            # Manual CAPTCHA entry
            print(f"\n  📷 CAPTCHA saved to: {captcha_path.absolute()}")
            print("  ⚠️  CASE-SENSITIVE! Must be EXACT (6 characters)")
            print("  " + "-" * 76)
            
            captcha = input(f"  Enter CAPTCHA for Property #{current_num}: ").strip()
            
            if not captcha:
                print(f"  ✗ CAPTCHA cannot be empty, skipping property #{current_num}")
                batch_results["failed"].append({"property": current_num, "reason": "Empty CAPTCHA"})
                current_num += 1
                continue
            
            if len(captcha) != 6:
                print(f"  ⚠️  WARNING: CAPTCHA should be 6 characters, got {len(captcha)}")
            
            # Submit search
            print(f"  → Submitting search for property #{current_num}...")
            response = search_property(session, csrf_token, captcha, current_num)
            
            print(f"  → Response received: {response.status_code} ({len(response.content)} bytes)")
            
            # Validate response
            is_valid, message = check_response_valid(response)
            
            if not is_valid:
                print(f"  ✗ FAILED: {message}")
                print(f"  → Likely wrong CAPTCHA, please try again")
                batch_results["failed"].append({"property": current_num, "reason": message})
                
                # Ask to retry
                retry = input(f"  Retry property #{current_num}? (y/n): ").strip().lower()
                if retry == 'y':
                    continue  # Don't increment current_num, retry same property
                else:
                    current_num += 1
                    continue
            
            # Save response
            output_file = OUTPUT_DIR / f"property_{current_num}.html"
            output_file.write_bytes(response.content)
            
            print(f"  ✓ SUCCESS: Saved to {output_file.name}")
            
            batch_results["success"].append(current_num)
            progress["completed"].append(current_num)
            progress["last_property"] = current_num
            
            # Save progress after each success
            save_progress(progress)
            
            fetched_count += 1
            current_num += 1
            
            # Small delay between requests
            if fetched_count < BATCH_SIZE:
                print(f"\n  ⏳ Waiting 2 seconds before next property...")
                time.sleep(2)
        
        except KeyboardInterrupt:
            print(f"\n\n⚠️  Interrupted by user")
            save_progress(progress)
            break
        
        except Exception as e:
            print(f"  ✗ ERROR: {e}")
            batch_results["failed"].append({"property": current_num, "reason": str(e)})
            current_num += 1
            continue
    
    # Final summary
    print(f"\n{'=' * 80}")
    print("BATCH COMPLETE")
    print(f"{'=' * 80}")
    print(f"\n✓ Successfully fetched: {len(batch_results['success'])} properties")
    if batch_results["success"]:
        print(f"   Properties: {batch_results['success']}")
    
    if batch_results["skipped"]:
        print(f"\n⊘ Skipped (already exists): {len(batch_results['skipped'])} properties")
        print(f"   Properties: {batch_results['skipped']}")
    
    if batch_results["failed"]:
        print(f"\n✗ Failed: {len(batch_results['failed'])} properties")
        for fail in batch_results["failed"]:
            print(f"   Property #{fail['property']}: {fail['reason']}")
    
    print(f"\n{'=' * 80}")
    print("📊 OVERALL PROGRESS")
    print(f"{'=' * 80}")
    print(f"Last completed: Property #{progress['last_property']}")
    print(f"Total completed: {len(progress['completed'])} properties")
    print(f"\nNext run will start from: Property #{progress['last_property'] + 1}")
    print(f"{'=' * 80}")
    print("\n✅ DONE")
    print("Run again to fetch next batch (properties {}-{})\n".format(
        progress['last_property'] + 1,
        progress['last_property'] + BATCH_SIZE
    ))


if __name__ == "__main__":
    main()
