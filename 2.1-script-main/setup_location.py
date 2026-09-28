"""
Find the settings that differ from machine to machine, and print them as
.env lines you can paste straight in.

The portal's district / taluka / village dropdowns are filled by AJAX and
keyed by ids that mean nothing on their own, so guessing them is hopeless.
This asks the portal the same questions the dropdowns do.

    python setup_location.py          pick a village, print its .env lines
    python setup_location.py --wifi   list this PC's saved Wi-Fi profiles
    python setup_location.py --all    both

Nothing is written for you - copy the output into your own .env.
"""
import subprocess
import sys

from config import BASE_URL, YEARS, db_value_for_year
from session import create_session

# Marathi place names will not survive a cp1252 console.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


# The portal keeps three separate databases and each has its own set of
# endpoints. Which one you land in depends on the year you are after, so
# the ids below are only valid for that era's group.
ENDPOINTS = {
    "1": ("getDistrictName1985", "getTalukaName1985", "getVillageName1985"),
    "2": ("getDistrictNamehis", "getTalukaNamehis", "getVillageNamehis"),
    "3": ("getDistrictName2019", "getTalukaName2019", "getVillageName2019"),
}


# ---------------------------------------------------------------
# Romanisation
# ---------------------------------------------------------------
#
# Every name the portal returns is Marathi, and a taluka can hold several
# hundred villages. Without this you would have to paste Devanagari to
# search the list, so each name is also matched and shown in a rough
# Latin form: "kharadi" finds खराडी. It is deliberately loose - it exists
# to filter a list, not to be correct transliteration.

CONSONANTS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n",
    "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "n",
    "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n",
    "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m",
    "य": "y", "र": "r", "ल": "l", "व": "v", "ळ": "l",
    "श": "sh", "ष": "sh", "स": "s", "ह": "h",
}

MATRAS = {
    "ा": "a", "ि": "i", "ी": "i", "ु": "u", "ू": "u", "ृ": "ri",
    "े": "e", "ै": "ai", "ो": "o", "ौ": "au",
    "ं": "n", "ँ": "n", "ः": "h",
}

VOWELS = {
    "अ": "a", "आ": "a", "इ": "i", "ई": "i", "उ": "u", "ऊ": "u",
    "ऋ": "ri", "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au",
}

HALANT = "्"


def romanise(text):
    """A searchable Latin approximation of a Devanagari name."""

    out = []
    characters = list(text)

    for position, character in enumerate(characters):

        if character in CONSONANTS:
            out.append(CONSONANTS[character])

            # A consonant carries an inherent "a" unless a vowel sign or
            # a halant follows it - without this every name collapses to
            # a run of consonants.
            following = characters[position + 1] if position + 1 < len(characters) else ""

            if following not in MATRAS and following != HALANT:
                out.append("a")

        elif character in MATRAS:
            out.append(MATRAS[character])

        elif character in VOWELS:
            out.append(VOWELS[character])

        elif character == HALANT:
            continue

        elif character.isascii() and character.isalnum():
            out.append(character.lower())

        else:
            out.append(" ")

    return " ".join("".join(out).split())


def matches(needle, name):
    """True if the typed text appears in the name, Marathi or romanised."""

    needle = needle.strip().lower()

    return needle in name.lower() or needle in romanise(name)


def fetch(session, endpoint, **params):
    response = session.get(
        f"{BASE_URL}/eDisplay/Propertydetails/{endpoint}",
        params=params,
        timeout=60,
    )

    response.raise_for_status()

    return response.json()


def choose(items, label):
    """
    Show a numbered list and return the chosen item.

    Typing text filters instead of selecting - a district has hundreds of
    villages and scrolling past them all is worse than searching.
    """

    shown = items

    while True:

        print(f"\n  {len(shown)} {label}(s):")

        for index, (name, _) in enumerate(shown, start=1):
            print(f"    {index:4d}. {name}   [{romanise(name)}]")

        answer = input(
            f"\n  Pick a {label} by number, or type part of the name to filter "
            f"(e.g. kharadi): "
        ).strip()

        if not answer:
            continue

        if answer.isdigit():
            position = int(answer)

            if 1 <= position <= len(shown):
                return shown[position - 1]

            print("  ! out of range")
            continue

        found = [pair for pair in items if matches(answer, pair[0])]

        if not found:
            print(f"  ! nothing matched {answer!r} - showing the full list again")
            shown = items
            continue

        shown = found


def pick_location():

    session = create_session()

    # The newest group covers 2019 onward, which is what almost everyone
    # wants; the others exist for older registrations.
    group = db_value_for_year(YEARS[0])

    district_ep, taluka_ep, village_ep = ENDPOINTS[group]

    print("=" * 70)
    print("IGR LOCATION SETUP")
    print("=" * 70)
    print(f"  Year group : {group} (from IGR_YEARS, newest year {YEARS[0]})")
    print("  Asking the portal for its dropdown lists...")

    districts = [
        (item["mdist_name"].strip(), str(item["dist_code"]).strip())
        for item in fetch(session, district_ep)
    ]

    district_name, district_id = choose(districts, "district")

    talukas = [
        (item["mtaluka_name"].strip(), str(item["taluka_code"]).strip())
        for item in fetch(session, taluka_ep, district=district_id)
    ]

    taluka_name, taluka_id = choose(talukas, "taluka")

    # The village dropdown posts the option's position in this list, not
    # any id in the payload - so the index IS the value.
    villages = [
        (item["am_mareaname"].strip(), str(index))
        for index, item in enumerate(
            fetch(session, village_ep, taluka=taluka_id, district=district_id)
        )
    ]

    village_name, village_id = choose(villages, "village")

    print("\n" + "=" * 70)
    print("Add these lines to your .env (they replace the defaults):")
    print("=" * 70 + "\n")

    print(f"IGR_DISTRICT={district_name}")
    print(f"IGR_TALUKA={taluka_name}")
    print(f"IGR_VILLAGE={village_name}")
    print()
    print(f"IGR_DISTRICT_ID={district_id}")
    print(f"IGR_TALUKA_ID={taluka_id}")
    print(f"IGR_VILLAGE_ID={village_id}")
    print()
    print(f"IGR_CSV_PREFIX={slug(village_name, taluka_name, district_name)}")

    print("\n  (Copy all of them together - the names and ids have to match.)")


def slug(*parts):
    """A filename-safe prefix built from the place names."""

    pieces = []

    for part in parts:
        # Only the first word: village names often trail a long
        # "(included in the municipal corporation)" clause.
        words = romanise(part).split()

        if words:
            pieces.append(words[0])

    return "_".join(pieces) or "igr_export"


def show_wifi():
    """List the Wi-Fi profiles and interfaces Windows has saved."""

    print("\n" + "=" * 70)
    print("SAVED WI-FI PROFILES ON THIS PC")
    print("=" * 70)

    try:
        result = subprocess.run(
            ["netsh", "wlan", "show", "profiles"],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=60,
        )
    except FileNotFoundError:
        print("  netsh not found - Wi-Fi rotation only works on Windows.")
        return

    profiles = []

    for line in (result.stdout or "").splitlines():
        if ":" in line and "profile" in line.lower():
            name = line.split(":", 1)[1].strip()

            if name:
                profiles.append(name)

    if not profiles:
        print("  None found. Connect to the networks once so Windows saves them.")
        print(result.stdout)
    else:
        for name in profiles:
            print(f"    {name}")

    interfaces = subprocess.run(
        ["netsh", "wlan", "show", "interfaces"],
        capture_output=True,
        text=True,
        errors="replace",
        timeout=60,
    )

    for line in (interfaces.stdout or "").splitlines():
        stripped = line.strip()

        if stripped.lower().startswith("name"):
            print(f"\n  Wi-Fi interface name: {stripped.split(':', 1)[1].strip()}")
            break

    print("\n  Put your two networks in .env like this:\n")
    print("IGR_HOTSPOT_PROFILE=<your phone's hotspot, exactly as listed above>")
    print("IGR_PARKING_PROFILE=<any other saved network>")
    print("IGR_WIFI_INTERFACE=Wi-Fi")
    print("\n  The hotspot is the one that gets a fresh IP when it reconnects.")
    print("  The parking network is only somewhere to sit for a few seconds")
    print("  in between, so the disconnect is real.")


def main():

    wifi = "--wifi" in sys.argv
    everything = "--all" in sys.argv

    if wifi or everything:
        show_wifi()

    if not wifi or everything:
        if everything:
            print()

        pick_location()


if __name__ == "__main__":
    main()
