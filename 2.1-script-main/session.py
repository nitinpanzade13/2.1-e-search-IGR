import requests

from config import BASE_URL


def create_session():
    session = requests.Session()

    session.headers.update({
        "User-Agent": "curl/8.13.0",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    })

    return session


def open_portal(session):
    url = BASE_URL + "/eDisplay/"

    response = session.get(
        url,
        timeout=60
    )

    response.raise_for_status()

    print("Portal opened successfully")
    print("Status:", response.status_code)
    print("Cookies:", session.cookies.get_dict())
    print("Response size:", len(response.content), "bytes")

    return response.text