from bs4 import BeautifulSoup

from session import create_session


BASE_URL = "https://pay2igr.igrmaharashtra.gov.in"
PROPERTY_URL = BASE_URL + "/eDisplay/Propertydetails/index"


def main():

    session = create_session()

    print("Opening Property Details page...")
    response = session.get(
        PROPERTY_URL,
        timeout=60
    )

    print("Status:", response.status_code)
    print("URL:", response.url)
    print("Response size:", len(response.content), "bytes")

    response.raise_for_status()

    html = response.text

    # Save a local copy for inspection
    with open("property_page.html", "w", encoding="utf-8") as f:
        f.write(html)

    soup = BeautifulSoup(html, "html.parser")

    print("\n========== FORMS ==========")

    for form in soup.find_all("form"):
        print(
            "ACTION:",
            form.get("action"),
            "| METHOD:",
            form.get("method")
        )

    print("\n========== IMPORTANT INPUTS ==========")

    wanted = [
        "free_text",
        "captcha",
        "_csrfToken",
        "yearsel",
        "district_id",
        "taluka_id",
        "village_id",
        "article_id",
    ]

    for name in wanted:

        elements = soup.find_all(
            lambda tag: tag.name == "input"
            and tag.get("name") == name
        )

        for element in elements:
            print(
                "INPUT:",
                name,
                "| type:",
                element.get("type"),
                "| value:",
                element.get("value", "")
            )

    print("\n========== SELECTS ==========")

    for select in soup.find_all("select"):

        name = select.get("name")
        element_id = select.get("id")

        if (
            name in [
                "years",
                "district_id",
                "taluka_id",
                "village_id",
                "article_id",
            ]
            or element_id in [
                "years",
                "district_id",
                "taluka_id",
                "village_id",
                "article_id",
            ]
        ):
            print(
                "SELECT:",
                name,
                "| id:",
                element_id,
                "| options:",
                len(select.find_all("option"))
            )

    print("\nSaved as property_page.html")


if __name__ == "__main__":
    main()