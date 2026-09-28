import re

FILE = "property_page.html"


KEYWORDS = [
    "dist_name",
    "tal_name",
    "article_name",
    "village_name",
    "freetext",
    "yearsel",
    "free_text",
    "captcha",
]


def main():

    with open(FILE, "r", encoding="utf-8") as f:
        html = f.read()

    print("=" * 80)
    print("SEARCH JAVASCRIPT")
    print("=" * 80)

    found = set()

    for keyword in KEYWORDS:

        print("\n" + "=" * 80)
        print("KEYWORD:", keyword)
        print("=" * 80)

        positions = [
            m.start()
            for m in re.finditer(
                re.escape(keyword),
                html,
                flags=re.IGNORECASE
            )
        ]

        for position in positions:

            start = max(0, position - 800)
            end = min(len(html), position + 1200)

            block = html[start:end]

            # Avoid printing exactly the same block repeatedly
            key = (keyword, block)

            if key not in found:
                found.add(key)
                print(block)
                print("\n" + "-" * 80)


if __name__ == "__main__":
    main()