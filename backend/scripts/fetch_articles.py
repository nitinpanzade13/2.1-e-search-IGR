import asyncio
from bs4 import BeautifulSoup
from app.scraper.client.igr_client import IgrSearchClient

def run():
    client = IgrSearchClient()
    try:
        # Just init session to get the search page
        client._init_session()
        print("CSRF Token:", client.csrf_token)
        
        # Now let's fetch the search page again directly to parse it
        resp = client.session.get("https://pay2igr.igrmaharashtra.gov.in/eDisplay/Propertydetails/index")
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        article_select = soup.find('select', {'id': 'article_id'})
        if article_select:
            options = article_select.find_all('option')
            print("Found Article IDs:")
            for opt in options:
                print(f"  Value: '{opt.get('value')}' - Text: '{opt.text.strip().encode('utf-8')}'")
        else:
            print("article_id select not found")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run()
