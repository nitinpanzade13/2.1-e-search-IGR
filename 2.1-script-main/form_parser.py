from bs4 import BeautifulSoup


# ASP.NET fields that must travel with the postback
HIDDEN_FIELDS = [
    "__VIEWSTATE",
    "__VIEWSTATEGENERATOR",
    "__EVENTVALIDATION",
]


def get_hidden_fields(html):
    soup = BeautifulSoup(html, "html.parser")

    fields = {}

    for name in HIDDEN_FIELDS:
        element = soup.find("input", {"name": name})

        if element:
            fields[name] = element.get("value", "")
        else:
            fields[name] = ""

    return fields


def get_select_options(html, select_id):
    """
    Return:
        [
            {"value": "...", "text": "..."},
            ...
        ]
    """

    soup = BeautifulSoup(html, "html.parser")

    select = soup.find("select", {"id": select_id})

    if not select:
        return []

    options = []

    for option in select.find_all("option"):
        options.append({
            "value": option.get("value", ""),
            "text": option.get_text(strip=True),
        })

    return options


def find_option_by_text(options, wanted):
    """
    Find a dropdown option using its visible text.
    """

    wanted = wanted.strip().lower()

    # Exact match first
    for option in options:
        text = option["text"].strip().lower()

        if text == wanted:
            return option

    # Partial match as fallback
    for option in options:
        text = option["text"].strip().lower()

        if wanted in text:
            return option

    return None