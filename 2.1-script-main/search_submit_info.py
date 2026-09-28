from bs4 import BeautifulSoup

with open("property_page.html", "r", encoding="utf-8") as f:
    html = f.read()

soup = BeautifulSoup(html, "html.parser")

print("\n========== SEARCH FORM ==========\n")

form = soup.find("form")

if form:
    print("ACTION :", form.get("action"))
    print("METHOD :", form.get("method"))

    for inp in form.find_all("input"):
        name = inp.get("name")
        if name in [
            "_csrfToken",
            "free_text",
            "partyname",
            "captcha",
            "dist_name",
            "tal_name",
            "article_name",
            "village_name",
            "freetext",
            "yearsel"
        ]:
            print(
                f"{name:15} = {inp.get('value', '')}"
            )

print("\n========== SEARCH JAVASCRIPT ==========\n")

for script in soup.find_all("script"):

    text = script.get_text()

    if (
        "dist_name" in text
        or "tal_name" in text
        or "village_name" in text
        or "article_name" in text
        or "yearsel" in text
    ):

        lines = text.splitlines()

        for i, line in enumerate(lines):

            if any(x in line for x in [
                "dist_name",
                "tal_name",
                "village_name",
                "article_name",
                "yearsel"
            ]):

                start = max(0, i - 2)
                end = min(len(lines), i + 3)

                print("\n".join(lines[start:end]))
                print("-" * 60)