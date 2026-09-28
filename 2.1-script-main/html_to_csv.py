"""
Convert saved IGR search pages to CSV.

The scraper already writes rows as it goes; this is for backfilling HTML
that was captured before it existed, or for re-parsing everything if the
parser changes.

    python html_to_csv.py                       backfill all of responses/ into the per-year CSVs
    python html_to_csv.py responses/x.html      convert one file to x.csv
    python html_to_csv.py --no-dedup            backfill without the dedup filter
"""
import csv
import re
import sys
from pathlib import Path

import igr_parser
from config import BASE_URL, OUTPUT_DIR, STATE_DIR, CSV_DIR, csv_path_for_year

RESPONSE_DIR = Path(OUTPUT_DIR)
SEEN_PATH = Path(STATE_DIR) / "seen_keys.txt"

# "2026_survey007.html" and the older "property_1.html"
STEM_PATTERN = re.compile(r"(?P<year>\d{4})_survey(?P<survey>\d+)", re.I)
LEGACY_PATTERN = re.compile(r"property_(?P<survey>\d+)", re.I)


def infer_source(path):
    """Recover (year, survey) from a filename; fall back to unknowns."""

    match = STEM_PATTERN.search(path.stem)

    if match:
        return int(match.group("year")), int(match.group("survey"))

    match = LEGACY_PATTERN.search(path.stem)

    if match:
        return "", int(match.group("survey"))

    return "", ""


class YearWriters:
    """
    Per-year CSV writers, opened on first use.

    A backfill walks files in filename order, which interleaves years, so
    every target stays open until the run finishes rather than being
    reopened per file.
    """

    def __init__(self):
        self._open = {}

    def writer(self, year):

        if year not in self._open:

            path = Path(csv_path_for_year(year))
            path.parent.mkdir(parents=True, exist_ok=True)

            is_new = not path.exists() or path.stat().st_size == 0
            handle = path.open("a", encoding="utf-8-sig", newline="")

            writer = csv.DictWriter(handle, fieldnames=igr_parser.COLUMNS)

            if is_new:
                writer.writeheader()

            self._open[year] = (handle, writer, path)

        return self._open[year][1]

    def paths(self):
        return sorted(path for _, _, path in self._open.values())

    def close(self):
        for handle, _, _ in self._open.values():
            handle.close()

        self._open.clear()


def convert_one(path, out_path=None):
    """Convert a single HTML file to its own CSV."""

    year, survey = infer_source(path)
    html = path.read_text(encoding="utf-8", errors="replace")

    rows = igr_parser.parse_rows(html, year, survey, base_url=BASE_URL)
    out_path = out_path or path.with_suffix(".csv")

    with out_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=igr_parser.COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"{path.name}: {len(rows)} rows -> {out_path.name}")

    return len(rows)


def backfill(dedup=True):
    """Parse every saved page into the per-year CSVs, skipping duplicates."""

    files = sorted(
        p for p in RESPONSE_DIR.glob("*.html")
        if not p.name.startswith("unknown_")
    )

    if not files:
        print(f"No HTML files in {RESPONSE_DIR.absolute()}")
        return

    seen = set()

    if dedup and SEEN_PATH.exists():
        with SEEN_PATH.open(encoding="utf-8") as handle:
            seen = {line.strip() for line in handle if line.strip()}

    print(f"Backfilling {len(files)} file(s); {len(seen):,} keys already known.\n")

    Path(CSV_DIR).mkdir(parents=True, exist_ok=True)
    SEEN_PATH.parent.mkdir(parents=True, exist_ok=True)

    writers = YearWriters()
    total_new = 0

    try:
        with SEEN_PATH.open("a", encoding="utf-8") as keys_out:

            for path in files:

                year, survey = infer_source(path)
                html = path.read_text(encoding="utf-8", errors="replace")
                rows = igr_parser.parse_rows(html, year, survey, base_url=BASE_URL)

                writer = writers.writer(year)
                fresh = 0

                for row in rows:
                    key = igr_parser.dedup_key(row)

                    if dedup:
                        if key in seen:
                            continue

                        seen.add(key)
                        keys_out.write(key + "\n")

                    writer.writerow(row)
                    fresh += 1

                total_new += fresh

                print(f"  {path.name}: {len(rows)} rows, {fresh} new")

        written = writers.paths()

    finally:
        writers.close()

    print(f"\n{total_new:,} new rows appended across {len(written)} file(s):")

    for path in written:
        print(f"  {path.absolute()}")

    print(f"\n{len(seen):,} unique documents known in total.")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    if args:
        for name in args:
            convert_one(Path(name))
        return

    backfill(dedup="--no-dedup" not in sys.argv)


if __name__ == "__main__":
    main()
