"""
IGR Maharashtra bulk property search.

Walks survey numbers across a list of years for one village, saving the
raw HTML of every search and appending deduplicated rows to one CSV per
registration year as it goes.

CAPTCHAs are read by an OpenAI vision model, so the run needs no one at
the keyboard. Everything else - resuming, retrying a rejected CAPTCHA,
rotating the IP when the daily quota trips - was already automatic.

    python scrape.py                  resume (or start) the full job
    python scrape.py --yes            ... without the confirmation prompt
    python scrape.py --status         show progress without searching
    python scrape.py --reset          forget progress and start over

    CAPTCHA_MODE=manual python scrape.py    type the CAPTCHAs yourself
"""
import csv
import json
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

import captcha_solver
import igr_parser
import netswitch
from config import (
    BASE_URL,
    SEARCH_URL,
    DISTRICT,
    TALUKA,
    VILLAGE,
    DISTRICT_ID,
    TALUKA_ID,
    VILLAGE_ID,
    SURVEY_START,
    SURVEY_END,
    YEARS,
    TARGET_UNIQUE_ROWS,
    SERVER_ROW_CAP,
    db_value_for_year,
    DELAY_BETWEEN_SEARCHES,
    DELAY_AFTER_ROTATION,
    MAX_CAPTCHA_RETRIES,
    OUTPUT_DIR,
    STATE_DIR,
    CSV_DIR,
    CSV_PREFIX,
    csv_path_for_year,
)

# The portal's messages come back in Marathi as often as English, and a
# Windows console is cp1252 by default. An unattended run should not die
# hours in because it tried to print a word it could not encode.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

RESPONSE_DIR = Path(OUTPUT_DIR)
STATE_PATH = Path(STATE_DIR) / "progress.json"
SEEN_PATH = Path(STATE_DIR) / "seen_keys.txt"

for directory in (RESPONSE_DIR, Path(STATE_DIR), Path(CSV_DIR)):
    directory.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------
# State
# ---------------------------------------------------------------

def load_state():
    state = {"done": [], "truncated": [], "empty": []}

    if STATE_PATH.exists():
        # Merge rather than replace, so a state file written by an older
        # version does not blow up on a missing key.
        state.update(json.loads(STATE_PATH.read_text(encoding="utf-8")))

    for key in ("done", "truncated", "empty"):
        state.setdefault(key, [])

    return state


def save_state(state):
    STATE_PATH.write_text(
        json.dumps(state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def load_seen():
    if not SEEN_PATH.exists():
        return set()

    with SEEN_PATH.open(encoding="utf-8") as handle:
        return {line.strip() for line in handle if line.strip()}


def append_seen(keys):
    with SEEN_PATH.open("a", encoding="utf-8") as handle:
        for key in keys:
            handle.write(key + "\n")


def append_csv(year, rows):
    """Append rows to that year's CSV, writing the header on creation."""

    path = Path(csv_path_for_year(year))

    is_new = not path.exists() or path.stat().st_size == 0

    with path.open("a", encoding="utf-8-sig", newline="") as handle:

        writer = csv.DictWriter(handle, fieldnames=igr_parser.COLUMNS)

        if is_new:
            writer.writeheader()

        writer.writerows(rows)


# ---------------------------------------------------------------
# Portal
# ---------------------------------------------------------------

def create_session():
    session = requests.Session()

    session.headers.update({
        "User-Agent": "curl/8.13.0",
        "Accept": "*/*",
    })

    return session


def get_csrf_token(session):
    """Open the form and pull the CSRF token bound to this session."""

    response = session.get(SEARCH_URL, timeout=60)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    token = soup.find("input", {"name": "_csrfToken"})

    if not token:
        raise RuntimeError("CSRF token not found - portal may have changed")

    return token.get("value", "")


def search(session, csrf_token, captcha, year, survey_no):

    payload = {
        "_csrfToken": csrf_token,

        "years": db_value_for_year(year),
        "district_id": DISTRICT_ID,
        "taluka_id": TALUKA_ID,
        "village_id": VILLAGE_ID,
        "article_id": "",

        "free_text": str(survey_no),
        "partyname": "",
        "captcha": captcha,

        "dist_name": DISTRICT,
        "tal_name": TALUKA,
        "article_name": "",
        "village_name": VILLAGE,

        "freetext": "",
        "yearsel": str(year),
    }

    response = session.post(
        SEARCH_URL,
        data=payload,
        timeout=180,
        headers={"Referer": SEARCH_URL, "Origin": BASE_URL},
    )

    response.raise_for_status()

    return response


# ---------------------------------------------------------------
# One search, with retries
# ---------------------------------------------------------------

def run_task(year, survey_no, state, seen, ip_holder):
    """
    Search one (year, survey) pair.

    Returns the number of new unique rows written, or None if the task
    should be retried later.
    """

    for attempt in range(1, MAX_CAPTCHA_RETRIES + 1):

        session = create_session()

        try:
            csrf_token = get_csrf_token(session)
        except Exception as exc:
            print(f"  ! could not load form: {exc}")
            time.sleep(5)
            continue

        captcha = captcha_solver.solve(session)

        if captcha is None:
            # The model could not make out this image. A fresh one is
            # cheaper than sending a guess the portal will refuse.
            continue

        if not captcha:
            print("  skipped by user")
            return 0

        try:
            response = search(session, csrf_token, captcha, year, survey_no)
        except Exception as exc:
            print(f"  ! search failed: {exc}")
            time.sleep(5)
            continue

        html = response.text
        verdict = igr_parser.classify(html)
        outcome = verdict["outcome"]

        print(f"  -> {outcome}: {verdict['message'][:90] or '(no message)'}")

        # Only OK/NO_RECORDS/BAD_CAPTCHA say anything about the CAPTCHA
        # itself; a quota refusal or an unrecognised page does not, so
        # those are left out of the hit rate rather than guessed at.
        if outcome in (igr_parser.OK, igr_parser.NO_RECORDS):
            captcha_solver.note_result(True)

        elif outcome == igr_parser.BAD_CAPTCHA:
            captcha_solver.note_result(False)

        if outcome == igr_parser.RATE_LIMITED:
            new_ip = netswitch.rotate(previous_ip=ip_holder.get("ip"))
            ip_holder["ip"] = new_ip

            if not new_ip:
                print("\n  Rotation failed. Fix the connection, then press ENTER")
                input("  to retry (or Ctrl+C to stop and resume later): ")
                ip_holder["ip"] = netswitch.public_ip()

            time.sleep(DELAY_AFTER_ROTATION)
            return None  # retry this same task on the new IP

        if outcome == igr_parser.BAD_CAPTCHA:
            print(f"  CAPTCHA rejected (attempt {attempt}/{MAX_CAPTCHA_RETRIES})")
            continue

        if outcome == igr_parser.UNKNOWN:
            path = RESPONSE_DIR / f"unknown_{year}_survey{survey_no:03d}.html"
            path.write_text(html, encoding="utf-8")
            print(f"  ! unrecognised response, saved to {path.name}")
            return 0

        # Save the raw page under a name unique to this search.
        stem = f"{year}_survey{survey_no:03d}"
        (RESPONSE_DIR / f"{stem}.html").write_text(html, encoding="utf-8")

        if outcome == igr_parser.NO_RECORDS:
            state["empty"].append(stem)
            return 0

        rows = igr_parser.parse_rows(html, year, survey_no, base_url=BASE_URL)

        fresh, fresh_keys = [], []

        for row in rows:
            key = igr_parser.dedup_key(row)

            if key in seen:
                continue

            seen.add(key)
            fresh_keys.append(key)
            fresh.append(row)

        if fresh:
            append_csv(year, fresh)
            append_seen(fresh_keys)

        if verdict["row_count"] >= SERVER_ROW_CAP:
            state["truncated"].append(stem)
            print(f"  ! hit the {SERVER_ROW_CAP}-row cap - results are truncated")

        print(f"  saved {len(rows)} rows ({len(fresh)} new, {len(rows) - len(fresh)} dupes)")

        return len(fresh)

    print(f"  giving up on {year}/survey {survey_no} after {MAX_CAPTCHA_RETRIES} tries")

    return 0


# ---------------------------------------------------------------
# Driver
# ---------------------------------------------------------------

def show_status(state, seen):
    print("\n" + "=" * 70)
    print("PROGRESS")
    print("=" * 70)
    print(f"  Searches completed : {len(state['done'])}")
    print(f"  Unique rows in CSV : {len(seen):,} / {TARGET_UNIQUE_ROWS:,}")
    print(f"  Empty results      : {len(state.get('empty', []))}")
    print(f"  Truncated (capped) : {len(state.get('truncated', []))}")
    print(f"  CAPTCHAs           : {captcha_solver.describe()}")

    files = sorted(Path(CSV_DIR).glob(f"{CSV_PREFIX}_*.csv"))

    if files:
        print(f"  CSVs in {Path(CSV_DIR).absolute()}:")

        for path in files:
            print(f"    {path.name:34s} {path.stat().st_size / 1e6:8.1f} MB")

    if state.get("truncated"):
        print("\n  These searches hit the row cap and are incomplete:")
        for stem in state["truncated"][:20]:
            print(f"    {stem}")


def main():

    state = load_state()
    seen = load_seen()

    if "--status" in sys.argv:
        show_status(state, seen)
        return

    if "--reset" in sys.argv:
        confirm = input("Delete progress and dedup state? [y/N]: ").strip().lower()

        if confirm == "y":
            STATE_PATH.unlink(missing_ok=True)
            SEEN_PATH.unlink(missing_ok=True)
            print("State cleared. The CSVs were left alone - move them aside yourself.")

        return

    done = set(state["done"])

    tasks = [
        (year, survey)
        for year in YEARS
        for survey in range(SURVEY_START, SURVEY_END + 1)
        if f"{year}:{survey}" not in done
    ]

    print("=" * 70)
    print(f"IGR BULK SEARCH - {VILLAGE} / {TALUKA} / {DISTRICT}")
    print("=" * 70)
    print(f"  Years          : {YEARS[0]}-{YEARS[-1]} ({len(YEARS)} years)")
    print(f"  Survey numbers : {SURVEY_START}-{SURVEY_END}")
    print(f"  Remaining      : {len(tasks)} searches")
    print(f"  Unique so far  : {len(seen):,} / {TARGET_UNIQUE_ROWS:,}")
    print("=" * 70)
    print(f"\n{captcha_solver.banner()}")
    print("Retries and IP rotation are handled for you.")
    print("Ctrl+C is safe at any point - progress resumes from where it stopped.\n")

    if "--yes" not in sys.argv:
        input("Press ENTER to begin...")

    ip_holder = {"ip": netswitch.public_ip()}
    print(f"\nStarting IP: {ip_holder['ip'] or 'unknown'}")

    try:
        index = 0

        while index < len(tasks):

            year, survey_no = tasks[index]

            if len(seen) >= TARGET_UNIQUE_ROWS:
                print(f"\nReached {TARGET_UNIQUE_ROWS:,} unique rows. Stopping.")
                break

            print(f"\n[{index + 1}/{len(tasks)}] {year} survey {survey_no} "
                  f"| unique {len(seen):,}")

            added = run_task(year, survey_no, state, seen, ip_holder)

            if added is None:
                # Rate limited: same task again, now on a fresh IP.
                continue

            state["done"].append(f"{year}:{survey_no}")
            save_state(state)

            index += 1

            if index < len(tasks):
                time.sleep(DELAY_BETWEEN_SEARCHES)

    except KeyboardInterrupt:
        print("\n\nInterrupted.")

    finally:
        save_state(state)
        show_status(state, seen)


if __name__ == "__main__":
    main()
