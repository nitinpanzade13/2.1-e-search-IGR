import re

FILE = "property_page.html"

ENDPOINTS = [
    "getTalukaName1985",
    "getTalukaNamehis",
    "getTalukaName2019",
    "getVillageName1985",
    "getVillageNamehis",
    "getVillageName2019",
]


def main():

    with open(FILE, "r", encoding="utf-8") as f:
        html = f.read()

    print("=" * 70)
    print("EXACT AJAX CODE AROUND DEPENDENT DROPDOWN ENDPOINTS")
    print("=" * 70)

    for endpoint in ENDPOINTS:

        print("\n" + "=" * 70)
        print(endpoint)
        print("=" * 70)

        # Find every occurrence
        positions = [
            m.start()
            for m in re.finditer(
                re.escape(endpoint),
                html,
                flags=re.IGNORECASE
            )
        ]

        if not positions:
            print("NOT FOUND")
            continue

        for i, position in enumerate(positions):

            start = max(0, position - 1200)
            end = min(len(html), position + 1800)

            print(f"\n--- occurrence {i + 1} ---\n")
            print(html[start:end])


if __name__ == "__main__":
    main()