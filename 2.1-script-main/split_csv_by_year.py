"""
Split the combined CSV into one file per registration year.

The scraper writes per-year files now; this migrates a CSV that was
written before it did. The source file is read, never modified - move it
aside yourself once you are happy with the output.

    python split_csv_by_year.py                    split output/kharadi_haveli_pune.csv
    python split_csv_by_year.py other.csv          split some other file
    python split_csv_by_year.py --force            overwrite existing per-year files
"""
import csv
import sys
from pathlib import Path

import igr_parser
from config import CSV_DIR, LEGACY_CSV_PATH, csv_path_for_year

# Seller and buyer cells carry every party to a registration, and a
# crowded one runs well past the 128k default.
csv.field_size_limit(1 << 30)


def split(source, force=False):

    source = Path(source)

    if not source.exists():
        print(f"No such file: {source.absolute()}")
        return 1

    Path(CSV_DIR).mkdir(parents=True, exist_ok=True)

    # Read the years first. Opening every target up front would truncate
    # files before we know whether the source is even readable, and the
    # scan is cheap next to the write.
    print(f"Scanning {source.absolute()} ...")

    with source.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)

        if reader.fieldnames != igr_parser.COLUMNS:
            print("\n! Column mismatch - this does not look like a scraper CSV.")
            print(f"  expected: {igr_parser.COLUMNS}")
            print(f"  found   : {reader.fieldnames}")
            return 1

        years = sorted({(row["year"] or "").strip() for row in reader})

    targets = {year: Path(csv_path_for_year(year)) for year in years}
    clashes = [p for p in targets.values() if p.exists() and p.stat().st_size]

    if clashes and not force:
        print("\n! These already exist; appending would duplicate rows.")

        for path in clashes:
            print(f"    {path}")

        print("\n  Move them aside, or re-run with --force to overwrite.")
        return 1

    print(f"Found {len(years)} year(s): {', '.join(years) or '(none)'}\n")

    handles, writers, counts = {}, {}, {}

    try:
        for year, path in targets.items():

            handles[year] = path.open("w", encoding="utf-8-sig", newline="")
            writers[year] = csv.DictWriter(handles[year], fieldnames=igr_parser.COLUMNS)
            writers[year].writeheader()
            counts[year] = 0

        with source.open(encoding="utf-8-sig", newline="") as handle:

            for row in csv.DictReader(handle):
                year = (row["year"] or "").strip()

                writers[year].writerow(row)
                counts[year] += 1

    finally:
        for handle in handles.values():
            handle.close()

    total = sum(counts.values())

    for year in years:
        path = targets[year]
        print(f"  {path.name:34s} {counts[year]:>8,} rows  "
              f"{path.stat().st_size / 1e6:7.1f} MB")

    print(f"\n{total:,} rows written. The source file is untouched:")
    print(f"  {source.absolute()}")

    return 0


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    source = args[0] if args else LEGACY_CSV_PATH

    return split(source, force="--force" in sys.argv)


if __name__ == "__main__":
    sys.exit(main())
