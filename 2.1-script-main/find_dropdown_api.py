import re


FILE = "property_page.html"


def main():

    with open(FILE, "r", encoding="utf-8") as f:
        html = f.read()

    print("Searching for dropdown-related API endpoints...\n")

    patterns = [
        r"""['"]([^'"]*(?:taluka|village|district)[^'"]*)['"]""",
        r"""url\s*:\s*['"]([^'"]+)['"]""",
        r"""ajax\s*\([^)]*""",
        r"""fetch\s*\([^)]*""",
    ]

    found = set()

    for pattern in patterns:

        matches = re.findall(
            pattern,
            html,
            flags=re.IGNORECASE
        )

        for match in matches:

            if isinstance(match, tuple):
                match = match[0]

            if match not in found:
                found.add(match)
                print(match)

    print("\nTotal unique matches:", len(found))


if __name__ == "__main__":
    main()