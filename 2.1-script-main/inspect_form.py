from bs4 import BeautifulSoup

from session import create_session, open_portal
from portal import IGRPortal


def inspect(html):
    soup = BeautifulSoup(html, "html.parser")

    print("\n========== FORMS ==========")

    for form in soup.find_all("form"):
        print("FORM")
        print(" action:", form.get("action"))
        print(" method:", form.get("method"))

    print("\n========== SELECTS ==========")

    for select in soup.find_all("select"):
        print(
            "SELECT:",
            select.get("id"),
            "| name:",
            select.get("name"),
            "| options:",
            len(select.find_all("option"))
        )

    print("\n========== INPUTS ==========")

    for inp in soup.find_all("input"):
        input_type = inp.get("type", "text")
        name = inp.get("name")
        value = inp.get("value", "")

        if name:
            print(
                "INPUT:",
                name,
                "| type:",
                input_type,
                "| value:",
                value[:80]
            )


portal = IGRPortal()

portal.open()

html = portal.switch_to_rest_of_maharashtra()

inspect(html)