import os

from dotenv import load_dotenv

# Loaded here because everything imports config, and the settings below
# are read at import time - load it any later and they miss the file.
#
# override=True on purpose: this .env is the project's own source of
# truth. A stale OPENAI_API_KEY left in the machine's environment would
# otherwise win silently, and the only symptom is the API rejecting a key
# you have already replaced.
load_dotenv(override=True)


# ---------------------------------------------------------------
# .env readers
# ---------------------------------------------------------------
#
# Everything a second person has to change - which village they are
# after, and what their Wi-Fi profiles are called - is read from .env,
# with the values below as fallbacks. .env is gitignored, so a copy of
# this project handed to someone else carries the defaults and their own
# .env quietly replaces them. See .env.example, and run
# `python setup_location.py` to discover the right values.

def _text(name, default):
    value = os.environ.get(name)

    return default if value is None or not value.strip() else value.strip()


def _number(name, default):
    value = os.environ.get(name, "").strip()

    if not value:
        return default

    try:
        return int(value.replace(",", "").replace("_", ""))
    except ValueError:
        raise ValueError(f"{name} in .env must be a whole number, got {value!r}")


def _year_list(name, default):
    value = os.environ.get(name, "").strip()

    if not value:
        return default

    try:
        years = [int(part) for part in value.replace(" ", "").split(",") if part]
    except ValueError:
        raise ValueError(
            f"{name} in .env must be comma-separated years, got {value!r}"
        )

    if not years:
        raise ValueError(f"{name} in .env is empty")

    return years


BASE_URL = "https://pay2igr.igrmaharashtra.gov.in"

SEARCH_URL = f"{BASE_URL}/eDisplay/Propertydetails/index"
PROPERTY_URL = SEARCH_URL
CAPTCHA_URL = f"{BASE_URL}/eDisplay/captcha-image"

# ---------------------------------------------------------------
# Location (default: Kharadi / Haveli / Pune)
# ---------------------------------------------------------------
#
# The names are posted alongside the ids and must match the dropdown
# text exactly, Marathi and all. The ids are what the portal actually
# filters on. `python setup_location.py` prints both, already formatted
# as .env lines - do not hand-edit one without the other.

DISTRICT = _text("IGR_DISTRICT", "पुणे")
TALUKA = _text("IGR_TALUKA", "हवेली")
VILLAGE = _text("IGR_VILLAGE", "खराडी (पुणे महापालिकेमध्ये समाविष्ट)")

DISTRICT_ID = _text("IGR_DISTRICT_ID", "23")
TALUKA_ID = _text("IGR_TALUKA_ID", "1")
VILLAGE_ID = _text("IGR_VILLAGE_ID", "43")

# ---------------------------------------------------------------
# What to search
# ---------------------------------------------------------------

# free_text is searched as Doc No / Property No / CTS No / Gut No /
# Survey No / Reg. Year, so 1..99 walks the survey numbers.
SURVEY_START = _number("IGR_SURVEY_START", 1)
SURVEY_END = _number("IGR_SURVEY_END", 99)

# Newest first: the scraper walks these in order and stops early
# once TARGET_UNIQUE_ROWS is reached.
YEARS = _year_list(
    "IGR_YEARS",
    [2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019],
)

TARGET_UNIQUE_ROWS = _number("IGR_TARGET_UNIQUE_ROWS", 200_000)

# The portal caps a single search at this many rows. A result that
# comes back at exactly this size is truncated, not complete.
SERVER_ROW_CAP = 10000

# The year dropdown does not send the year itself, it sends a
# database-group id. 2003-2011 are absent from the portal.
YEAR_DB_GROUPS = {
    3: range(2019, 2027),
    2: range(2012, 2019),
    1: range(1985, 2003),
}


def db_value_for_year(year):
    """Map a calendar year to the portal's `years` dropdown value."""

    for value, years in YEAR_DB_GROUPS.items():
        if year in years:
            return str(value)

    raise ValueError(
        f"Year {year} is not searchable on the portal "
        f"(valid: 1985-2002, 2012-2018, 2019-2026)"
    )


# ---------------------------------------------------------------
# Network rotation
# ---------------------------------------------------------------

# The portal enforces a daily search quota per IP. Reconnecting the
# phone hotspot pulls a fresh carrier IP; the second profile is only
# somewhere to park while that happens.
#
# The profile names are per-machine - they are the SSIDs Windows has
# saved. `python setup_location.py --wifi` lists the ones on this PC.
WIFI_INTERFACE = _text("IGR_WIFI_INTERFACE", "Wi-Fi")
HOTSPOT_PROFILE = _text("IGR_HOTSPOT_PROFILE", "Galaxy M51DFA7")
PARKING_PROFILE = _text("IGR_PARKING_PROFILE", "Airtel_Prathmesh")

# Seconds to let each association settle before testing connectivity.
SWITCH_SETTLE_SECONDS = 12
CONNECTIVITY_TIMEOUT = 90

# Give up after this many rotations without the IP actually changing.
MAX_ROTATION_ATTEMPTS = 6

# ---------------------------------------------------------------
# Pacing
# ---------------------------------------------------------------

DELAY_BETWEEN_SEARCHES = 4
DELAY_AFTER_ROTATION = 5
MAX_CAPTCHA_RETRIES = 4

# ---------------------------------------------------------------
# CAPTCHA solving
# ---------------------------------------------------------------

# "auto" reads the CAPTCHA with an OpenAI vision model; "manual" asks
# you to type every one. Auto falls back to manual on its own if the key
# is missing or the model starts failing consistently.
CAPTCHA_MODE = os.environ.get("CAPTCHA_MODE", "auto").strip().lower()

# gpt-4o reads these noisy glyphs markedly better than gpt-4o-mini, and
# at a fraction of a cent per search the difference is not worth saving.
OPENAI_MODEL = os.environ.get("OPENAI_CAPTCHA_MODEL", "gpt-4o")

# "high" makes the API tile the image instead of squashing it to a
# thumbnail - the difference between reading the letters and guessing.
OPENAI_IMAGE_DETAIL = "high"
OPENAI_TIMEOUT = 60

CAPTCHA_LENGTH = 6

# The image is uploaded once and answered several times, so extra votes
# are cheap. Majority voting catches the reads the model is unsure of,
# which is worth more than the tokens: every wrong answer costs a search
# against the portal's daily quota.
CAPTCHA_VOTES = 3
CAPTCHA_TEMPERATURE = 0.7

# Retries for network/API trouble only. A bad read is not retried here -
# the scraper fetches a whole new CAPTCHA instead.
CAPTCHA_API_RETRIES = 3

# Enlarge before denoising, so the median filter erases the background
# specks without eating into the strokes. 0 disables the filter.
CAPTCHA_PREPROCESS = True
CAPTCHA_UPSCALE = 3
CAPTCHA_DENOISE = 3

# Consecutive portal rejections before automatic solving gives up and
# hands the keyboard back, rather than spending the quota on guesses.
CAPTCHA_AUTO_FAIL_STREAK = 8

# ---------------------------------------------------------------
# Paths
# ---------------------------------------------------------------

OUTPUT_DIR = "responses"
STATE_DIR = "state"
CAPTCHA_PATH = "captcha.png"
FAILED_CAPTCHA_DIR = "state/failed_captchas"

# Rows are written one CSV per registration year. A single combined file
# passes what Excel will open somewhere north of 80k rows, and the year
# is the natural seam - nothing downstream reads across years.
CSV_DIR = "output"

# Rename this along with the location, or a second village's rows land
# in files named after the first one.
CSV_PREFIX = _text("IGR_CSV_PREFIX", "kharadi_haveli_pune")

# The pre-split master file. Nothing writes here any more; it is only
# the default source for split_csv_by_year.py.
LEGACY_CSV_PATH = f"{CSV_DIR}/{CSV_PREFIX}.csv"


def csv_path_for_year(year):
    """Path of the CSV holding one year's rows."""

    return f"{CSV_DIR}/{CSV_PREFIX}_{year or 'unknown'}.csv"
