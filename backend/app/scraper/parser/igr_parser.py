import re
from bs4 import BeautifulSoup
from app.scraper.models.scrape_result import ScrapeResult

# Outcomes
OK = "OK"
NO_RECORDS = "NO_RECORDS"
RATE_LIMITED = "RATE_LIMITED"
BAD_CAPTCHA = "BAD_CAPTCHA"
UNKNOWN = "UNKNOWN"

_RECORDS_FOUND = re.compile(r"([\d,]+)\s*Records?\s*found", re.I)

def _flash_message(soup):
    div = soup.find("div", class_="message")
    if not div:
        return "", ""
    classes = " ".join(div.get("class", []))
    return classes, div.get_text(" ", strip=True)

def classify(html):
    soup = BeautifulSoup(html, "html.parser")
    classes, message = _flash_message(soup)
    lowered = message.lower()

    table = soup.find("table", id="tableparty")
    body = table.find("tbody") if table else None
    row_count = len(body.find_all("tr", id="tbdata")) if body else 0

    reported = None
    found = _RECORDS_FOUND.search(message)
    if found:
        reported = int(found.group(1).replace(",", ""))

    if "exceeded the limit" in lowered or "daily search" in lowered:
        outcome = RATE_LIMITED
    elif "captcha" in lowered:
        outcome = BAD_CAPTCHA
    elif row_count > 0:
        outcome = OK
    elif "no record" in lowered or "not found" in lowered:
        outcome = NO_RECORDS
    elif "warning" in classes or "error" in classes:
        outcome = UNKNOWN
    elif not message:
        outcome = UNKNOWN
    else:
        outcome = NO_RECORDS

    return {
        "outcome": outcome,
        "message": message,
        "row_count": row_count,
        "reported_count": reported,
    }

def _cell_text(td):
    for br in td.find_all("br"):
        br.replace_with("\n")
    text = td.get_text()
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)

def parse_rows(html, year, survey_query, base_url=""):
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", id="tableparty")

    if not table or not table.find("tbody"):
        return []

    rows = []
    for tr in table.find("tbody").find_all("tr", id="tbdata"):
        cells = tr.find_all("td")
        if len(cells) < 9:
            continue

        link = cells[8].find("a")
        href = link.get("href", "") if link else ""

        if href and base_url and href.startswith("/"):
            href = base_url + href

        rows.append(ScrapeResult(
            year=year,
            survey_query=survey_query,
            sr_no=_cell_text(cells[0]),
            doc_no=_cell_text(cells[1]),
            doc_type=_cell_text(cells[2]),
            office=_cell_text(cells[3]),
            date=_cell_text(cells[4]),
            seller=_cell_text(cells[5]),
            buyer=_cell_text(cells[6]),
            other_info=_cell_text(cells[7]),
            indexii_url=href,
        ))

    return rows

def dedup_key(row: ScrapeResult):
    url = row.indexii_url
    if url:
        return url.rsplit("/", 1)[-1]
    return "|".join([
        str(row.year),
        row.doc_no,
        row.office,
        row.date,
    ])
