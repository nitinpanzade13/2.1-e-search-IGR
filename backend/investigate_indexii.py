import requests
import urllib.parse
from bs4 import BeautifulSoup
import os

url = 'https://pay2igr.igrmaharashtra.gov.in/eDisplay/propertydetails/indexii/MjAyNg%3D%3D/MDAwNjAwMDAwMDAwMTQ5NzcyMDAwMDA5ODc0MjAyNklT'

session = requests.Session()
session.headers.update({
    'User-Agent': 'curl/8.13.0',
    'Accept': '*/*'
})

print(f'Fetching {url}')
response = session.get(url, timeout=60, allow_redirects=True)

print(f'Status: {response.status_code}')
print(f'Content-Type: {response.headers.get("Content-Type")}')
print(f'Cookies: {session.cookies.get_dict()}')

if 'application/pdf' in response.headers.get('Content-Type', '').lower():
    print('Response is a PDF!')
    print(f'Size: {len(response.content)} bytes')
    print(f'Magic bytes: {response.content[:4]}')
else:
    print('Response is HTML or text. Saving to storage/raw/indexii_response.html')
    os.makedirs('storage/raw', exist_ok=True)
    with open('storage/raw/indexii_response.html', 'w', encoding='utf-8') as f:
        f.write(response.text)
    
    soup = BeautifulSoup(response.text, 'html.parser')
    print('Looking for PDF links, iframes, forms, embeds...')
    
    for iframe in soup.find_all('iframe'):
        print(f'Iframe found: src={iframe.get("src")}')
    
    for embed in soup.find_all('embed'):
        print(f'Embed found: src={embed.get("src")} type={embed.get("type")}')
        
    for object_tag in soup.find_all('object'):
        print(f'Object found: data={object_tag.get("data")} type={object_tag.get("type")}')
        
    for a in soup.find_all('a'):
        href = a.get('href', '')
        if 'pdf' in href.lower() or 'download' in href.lower() or 'print' in href.lower():
            print(f'Link found: text="{a.text.strip()}" href={href}')
