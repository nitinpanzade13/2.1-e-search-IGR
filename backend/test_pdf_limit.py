import requests
import time

url = 'https://pay2igr.igrmaharashtra.gov.in/eDisplay/propertydetails/indexii/MjAyNg%3D%3D/MDAwNjAwMDAwMDAwMTQ5NzcyMDAwMDA5ODc0MjAyNklT'

for i in range(1, 10):
    try:
        resp = requests.get(url, headers={'User-Agent': 'curl/8.13.0', 'Accept': '*/*'}, timeout=60)
        print(f'Request {i}: Status {resp.status_code}, Content-Type: {resp.headers.get("Content-Type")}, Size: {len(resp.content)}')
    except Exception as e:
        print(f'Request {i} failed: {e}')
    time.sleep(1)
