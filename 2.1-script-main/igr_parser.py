"""
Parse and classify responses from the IGR Propertydetails search.

Every search returns HTTP 200 with the same form page; what actually
happened is only visible in the CakePHP flash message and whether the
results table has rows.
"""
import re

from bs4 import BeautifulSoup

# Outcomes
OK = "OK"
NO_RECORDS = "NO_RECORDS"
RATE_LIMITED = "RATE_LIMITED"
BAD_CAPTCHA = "BAD_CAPTCHA"
UNKNOWN = "UNKNOWN"

COLUMNS = [
    "year",
    "survey_query",
    "sr_no",
    "doc_no",
    "doc_type",
    "office",
    "date",
    "seller",
    "buyer",
    "other_info",
    "indexii_url",
]

_RECORDS_FOUND = re.compile(r"([\d,]+)\s*Records?\s*found", re.I)


def _flash_message(soup):
    """Return (css_class, text) of the portal's flash message, if any."""

    div = soup.find("div", class_="message")

    if not div:
        return "", ""

    classes = " ".join(div.get("class", []))

    return classes, div.get_text(" ", strip=True)


def classify(html):
    """
    Work out what the portal did with our search.

    Returns a dict with the outcome, the portal's own message, and the
    number of rows it claims to have found.
    """

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
        # Some other refusal we have not seen before.
        outcome = UNKNOWN

    elif not message:
        # Plain form with no feedback at all - usually a dropped session.
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
    """Flatten a cell, turning <br> separators into newlines."""

    for br in td.find_all("br"):
        br.replace_with("\n")

    text = td.get_text()

    # Sub-items are numbered "1) ... 2) ..."; keep them on their own
    # lines but collapse the portal's heavy indentation whitespace.
    lines = [line.strip() for line in text.split("\n")]

    return "\n".join(line for line in lines if line)


def parse_rows(html, year, survey_query, base_url=""):
    """
    Extract result rows as dicts keyed by COLUMNS.

    `year` and `survey_query` are stamped onto every row so the merged
    CSV keeps track of which search each record came from.
    """

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

        rows.append({
            "year": year,
            "survey_query": survey_query,
            "sr_no": _cell_text(cells[0]),
            "doc_no": _cell_text(cells[1]),
            "doc_type": _cell_text(cells[2]),
            "office": _cell_text(cells[3]),
            "date": _cell_text(cells[4]),
            "seller": _cell_text(cells[5]),
            "buyer": _cell_text(cells[6]),
            "other_info": _cell_text(cells[7]),
            "indexii_url": href,
        })

    return rows


def dedup_key(row):
    """
    Stable identity for a document.

    The indexii link carries a base64 token that encodes office, doc
    number and year, so it uniquely identifies a registration. Rows
    without a link fall back to the visible fields.
    """

    url = row.get("indexii_url", "")

    if url:
        return url.rsplit("/", 1)[-1]

    return "|".join([
        str(row.get("year", "")),
        row.get("doc_no", ""),
        row.get("office", ""),
        row.get("date", ""),
    ])
