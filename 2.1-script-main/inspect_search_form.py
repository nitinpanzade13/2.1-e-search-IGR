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

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    form = soup.find(
        "form",
        action="/eDisplay/Propertydetails/index"
    )

    if not form:
        raise RuntimeError(
            "Property Details form not found"
        )

    print("\n========== SEARCH FORM ==========")

    print("Action:", form.get("action"))
    print("Method:", form.get("method"))

    print("\n========== INPUTS ==========")

    for element in form.find_all("input"):

        print(
            "name:",
            element.get("name"),
            "| type:",
            element.get("type"),
            "| value:",
            element.get("value", "")
        )

    print("\n========== SELECTS ==========")

    for select in form.find_all("select"):

        print(
            "\nSELECT"
            "\n  name:",
            select.get("name"),
            "\n  id:",
            select.get("id")
        )

        options = select.find_all("option")

        print("  options:", len(options))

        # Print first 10 options only
        for option in options[:10]:

            print(
                "    ",
                option.get("value", ""),
                "=>",
                option.get_text(" ", strip=True)
            )

        if len(options) > 10:
            print("    ...")

    print("\n========== BUTTONS ==========")

    for button in form.find_all(
        ["button", "input"]
    ):

        button_type = button.get("type")

        if (
            button.name == "button"
            or button_type in ["submit", "button"]
        ):

            print(
                "name:",
                button.get("name"),
                "| type:",
                button_type,
                "| value:",
                button.get("value", ""),
                "| text:",
                button.get_text(" ", strip=True)
            )


if __name__ == "__main__":
    main()