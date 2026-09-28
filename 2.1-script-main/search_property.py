import sys

import requests
from bs4 import BeautifulSoup
from pathlib import Path

import captcha_solver  # loads .env via config

# The payload below carries Devanagari place names, and a Windows console
# is cp1252 by default - printing it would otherwise kill the run before
# the search is even sent.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE_URL = "https://pay2igr.igrmaharashtra.gov.in"
PROPERTY_URL = BASE_URL + "/eDisplay/Propertydetails/index"

OUTPUT_DIR = Path("responses")
OUTPUT_DIR.mkdir(exist_ok=True)


def create_session():
    session = requests.Session()

    session.headers.update({
        "User-Agent": "curl/8.13.0",
        "Accept": "*/*",
    })

    return session


def get_property_page(session):
    print(f"\n[GET] {PROPERTY_URL}")
    print(f"  Headers: {session.headers}")

    response = session.get(
        PROPERTY_URL,
        timeout=60
    )

    print(f"  Status: {response.status_code}")
    print(f"  Response cookies: {session.cookies.get_dict()}")

    response.raise_for_status()

    return response.text


def get_csrf_token(html):
    soup = BeautifulSoup(html, "html.parser")

    token = soup.find(
        "input",
        {"name": "_csrfToken"}
    )

    if not token:
        raise RuntimeError(
            "CSRF token not found"
        )

    return token.get("value", "")


def search_property(session, csrf_token, captcha):

    payload = {
        "_csrfToken": csrf_token,

        "years": "3",
        "district_id": "23",
        "taluka_id": "1",
        "village_id": "43",
        "article_id": "",

        "free_text": "1",
        "partyname": "",
        "captcha": captcha,

        "dist_name": "पुणे",
        "tal_name": "हवेली",
        "article_name": "",
        "village_name": "खराडी (पुणे महापालिकेमध्ये समाविष्ट)",

        "freetext": "",
        "yearsel": "2026",
    }

    print(f"\n[POST] {PROPERTY_URL}")
    print("  Payload:")
    for key, value in payload.items():
        shown = value if key != "_csrfToken" else f"{value[:20]}... ({len(value)} chars)"
        print(f"    {key}: {shown}")

    response = session.post(
        PROPERTY_URL,
        data=payload,
        timeout=120,
        headers={
            "Referer": PROPERTY_URL,
            "Origin": BASE_URL,
        }
    )

    print("\n  Status:", response.status_code)
    print("  Response size:", len(response.content), "bytes")
    print("  Response preview:", response.text[:300].replace("\n", " "), "...")

    response.raise_for_status()

    return response


def main():

    print("Creating session...")

    session = create_session()

    print("Opening Property Details page...")

    html = get_property_page(session)

    print(
        "Initial response:",
        len(html),
        "bytes"
    )

    csrf_token = get_csrf_token(html)

    print(
        "CSRF token obtained:",
        len(csrf_token),
        "characters"
    )

    # Fetch and read the CAPTCHA on the SAME session.
    print(f"\n{captcha_solver.banner()}")

    captcha = captcha_solver.solve(session)

    if not captcha:
        raise RuntimeError("No CAPTCHA to submit")

    response = search_property(
        session,
        csrf_token,
        captcha
    )

    output_file = OUTPUT_DIR / "property_1.html"

    output_file.write_bytes(
        response.content
    )

    print(
        "\nResponse saved to:",
        output_file.absolute()
    )


if __name__ == "__main__":
    main()