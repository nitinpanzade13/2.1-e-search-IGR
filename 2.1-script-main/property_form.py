from bs4 import BeautifulSoup

from config import BASE_URL, DISTRICT, TALUKA, VILLAGE, YEAR


PROPERTY_URL = BASE_URL + "/eDisplay/Propertydetails/index"


def get_property_page(session):
    response = session.get(
        PROPERTY_URL,
        timeout=60
    )

    response.raise_for_status()

    return response.text


def get_select_options(soup, select_id):

    select = soup.find("select", {"id": select_id})

    if not select:
        raise RuntimeError(
            f"Could not find select element: {select_id}"
        )

    options = []

    for option in select.find_all("option"):

        options.append({
            "value": option.get("value", ""),
            "text": option.get_text(" ", strip=True)
        })

    return options


def find_option(options, wanted):

    wanted = wanted.strip().lower()

    # Exact match
    for option in options:

        if option["text"].strip().lower() == wanted:
            return option

    # Partial match
    for option in options:

        if wanted in option["text"].strip().lower():
            return option

    return None


def inspect_property_form(html):

    soup = BeautifulSoup(html, "html.parser")

    # -------------------------
    # YEAR
    # -------------------------

    years = get_select_options(soup, "dbselect")

    year_option = find_option(years, YEAR)

    if not year_option:
        raise RuntimeError(
            f"Year '{YEAR}' not found"
        )

    # -------------------------
    # DISTRICT
    # -------------------------

    districts = get_select_options(
        soup,
        "district_id"
    )

    district_option = find_option(
        districts,
        DISTRICT
    )

    if not district_option:
        raise RuntimeError(
            f"District '{DISTRICT}' not found"
        )

    # -------------------------
    # TALUKA
    # -------------------------

    talukas = get_select_options(
        soup,
        "taluka_id"
    )

    # At this stage the portal may have only
    # the default option because taluka is
    # loaded dynamically after district selection.

    # -------------------------
    # VILLAGE
    # -------------------------

    villages = get_select_options(
        soup,
        "village_id"
    )

    # -------------------------
    # ARTICLE
    # -------------------------

    articles = get_select_options(
        soup,
        "article_id"
    )

    print("\n========== PROPERTY FORM ==========")

    print(
        "YEAR:",
        year_option["text"],
        "=>",
        year_option["value"]
    )

    print(
        "DISTRICT:",
        district_option["text"],
        "=>",
        district_option["value"]
    )

    print(
        "TALUKA OPTIONS:",
        len(talukas)
    )

    print(
        "VILLAGE OPTIONS:",
        len(villages)
    )

    print(
        "ARTICLE OPTIONS:",
        len(articles)
    )

    return {
        "year": year_option,
        "district": district_option,
        "talukas": talukas,
        "villages": villages,
        "articles": articles,
    }


if __name__ == "__main__":

    import requests

    session = requests.Session()

    session.headers.update({
        "User-Agent": "curl/8.13.0",
        "Accept": "*/*",
    })

    print("Opening Property Details...")

    html = get_property_page(session)

    result = inspect_property_form(html)

    print("\nProperty form inspection completed.")