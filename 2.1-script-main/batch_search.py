"""
Batch Property Search - Fetch multiple properties automatically
"""
import time
from pathlib import Path
from search_property import (
    create_session,
    get_property_page,
    get_csrf_token,
    download_captcha,
    read_captcha,
    search_property,
    OUTPUT_DIR,
    PROPERTY_URL,
    BASE_URL
)

# Configuration
START_PROPERTY = 1
END_PROPERTY = 10  # Fetch properties 1 to 10
DELAY_BETWEEN_REQUESTS = 2  # seconds (to avoid rate limiting)


def batch_search(start_num, end_num, delay=2):
    """
    Fetch multiple property details in sequence.
    
    Args:
        start_num: Starting property number
        end_num: Ending property number (inclusive)
        delay: Delay between requests in seconds
    """
    
    print("=" * 70)
    print(f"BATCH PROPERTY SEARCH: Properties {start_num} to {end_num}")
    print("=" * 70)
    
    results = {
        "success": [],
        "failed": []
    }
    
    for property_num in range(start_num, end_num + 1):
        
        print(f"\n{'=' * 70}")
        print(f"Processing Property #{property_num}")
        print(f"{'=' * 70}")
        
        try:
            # Create new session for each property
            session = create_session()
            
            # Get property page
            html = get_property_page(session)
            
            # Extract CSRF token
            csrf_token = get_csrf_token(html)
            print(f"CSRF token obtained: {len(csrf_token)} characters")
            
            # Download and read CAPTCHA
            captcha_path = download_captcha(session)
            
            try:
                captcha = read_captcha(captcha_path)
                
                if not captcha:
                    raise RuntimeError("CAPTCHA text is empty")
                    
            except Exception as e:
                print(f"\nAutomatic CAPTCHA reading failed: {e}")
                print(f"Skipping property #{property_num}")
                
                results["failed"].append({
                    "property": property_num,
                    "reason": f"CAPTCHA reading failed: {e}"
                })
                
                continue
            
            # Modify payload for current property number
            response = search_property_custom(
                session,
                csrf_token,
                captcha,
                property_num
            )
            
            # Save response
            output_file = OUTPUT_DIR / f"property_{property_num}.html"
            output_file.write_bytes(response.content)
            
            print(f"\n✓ Property #{property_num} saved to: {output_file.name}")
            
            results["success"].append(property_num)
            
            # Delay before next request
            if property_num < end_num:
                print(f"\nWaiting {delay} seconds before next request...")
                time.sleep(delay)
                
        except Exception as e:
            print(f"\n✗ Error processing property #{property_num}: {e}")
            
            results["failed"].append({
                "property": property_num,
                "reason": str(e)
            })
    
    # Summary
    print(f"\n{'=' * 70}")
    print("BATCH SEARCH SUMMARY")
    print(f"{'=' * 70}")
    print(f"✓ Successful: {len(results['success'])} properties")
    print(f"  {results['success']}")
    print(f"\n✗ Failed: {len(results['failed'])} properties")
    
    for failed in results['failed']:
        print(f"  Property #{failed['property']}: {failed['reason']}")
    
    return results


def search_property_custom(session, csrf_token, captcha, property_num):
    """
    Modified search_property to accept custom property number.
    """
    
    payload = {
        "_csrfToken": csrf_token,

        "years": "3",
        "district_id": "23",
        "taluka_id": "1",
        "village_id": "43",
        "article_id": "",

        "free_text": str(property_num),  # Dynamic property number
        "partyname": "",
        "captcha": captcha,

        "dist_name": "पुणे",
        "tal_name": "हवेली",
        "article_name": "",
        "village_name": "खराडी (पुणे महापालिकेमध्ये समाविष्ट)",

        "freetext": "",
        "yearsel": "2026",
    }

    print(f"\nSearching for property #{property_num}...")

    response = session.post(
        PROPERTY_URL,
        data=payload,
        timeout=120,
        headers={
            "Referer": PROPERTY_URL,
            "Origin": BASE_URL,
        }
    )

    print(f"Status: {response.status_code}")
    print(f"Response size: {len(response.content)} bytes")

    response.raise_for_status()

    return response


def main():
    """
    Run batch search for configured property range.
    """
    
    print("\n" + "=" * 70)
    print("IGR MAHARASHTRA - BATCH PROPERTY SEARCH")
    print("=" * 70)
    print(f"\nConfiguration:")
    print(f"  Property Range: {START_PROPERTY} to {END_PROPERTY}")
    print(f"  Delay: {DELAY_BETWEEN_REQUESTS} seconds")
    print(f"  Output: {OUTPUT_DIR.absolute()}")
    print("\n" + "=" * 70)
    
    input("\nPress ENTER to start batch search...")
    
    results = batch_search(
        START_PROPERTY,
        END_PROPERTY,
        DELAY_BETWEEN_REQUESTS
    )
    
    print(f"\n{'=' * 70}")
    print("BATCH SEARCH COMPLETED")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
