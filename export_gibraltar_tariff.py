#!/usr/bin/env python3
import csv
import re
import time
import argparse
from typing import List, Dict

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.hmcustoms.gov.gi/portal/services/tariff/print.jsf?c={chapter}"

# Match codes like:
# 0101210000-00-00
# 0511993*00-3*-00
CODE_PATTERN = re.compile(
    r"\\b\\d{2}[0-9*]{2}[0-9*]{4}-[0-9*]{2}-[0-9*]{2}\\b"
)


def fetch_chapter_text(chapter: int) -> str:
    """Fetch raw text for a chapter from the Gibraltar HM Customs tariff."""
    chapter_str = f"{chapter:02d}"  # 1 -> "01", 10 -> "10"
    url = BASE_URL.format(chapter=chapter_str)
    resp = requests.get(url, headers={"User-Agent": "tariff-scraper/1.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    text = soup.get_text("\\n", strip=True)
    return text


def extract_codes_from_text(text: str, chapter: int) -> List[Dict[str, str]]:
    """Extract (chapter, code, description) from the chapter text."""
    records = []
    seen = set()  # dedupe by (chapter, code, description)

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        # Find all code-like tokens in the line
        for match in CODE_PATTERN.finditer(line):
            code = match.group(0)

            # Description: everything AFTER the code occurrence
            desc = line[match.end():].strip()
            # Strip leading punctuation/space
            desc = desc.lstrip(" -–—:")

            key = (chapter, code, desc)
            if key in seen:
                continue
            seen.add(key)
            records.append(
                {
                    "chapter": f"{chapter:02d}",
                    "code": code,
                    "description": desc,
                }
            )

    return records


def main():
    parser = argparse.ArgumentParser(description="Export Gibraltar harmonised tariff codes to CSV.")
    parser.add_argument(
        "--outfile",
        default="gibraltar_harmonised_codes.csv",
        help="Output CSV file path (default: gibraltar_harmonised_codes.csv)",
    )
    args = parser.parse_args()

    all_records: List[Dict[str, str]] = []

    for chapter in range(1, 100):  # 01..99 inclusive
        print(f"Fetching chapter {chapter:02d}...")
        try:
            text = fetch_chapter_text(chapter)
        except requests.HTTPError as e:
            print(f"  !! HTTP error for chapter {chapter:02d}: {e}")
            continue
        except requests.RequestException as e:
            print(f"  !! Request error for chapter {chapter:02d}: {e}")
            continue

        chapter_records = extract_codes_from_text(text, chapter)
        print(f"  -> found {len(chapter_records)} codes")
        all_records.extend(chapter_records)

        time.sleep(0.3)

    final_seen = set()
    deduped_records = []
    for rec in all_records:
        key = (rec["chapter"], rec["code"], rec["description"])
        if key in final_seen:
            continue
        final_seen.add(key)
        deduped_records.append(rec)

    print(f"Total codes collected: {len(deduped_records)}")

    out_file = args.outfile
    out_dir = os.path.dirname(out_file)
    if out_dir:
        import os
        os.makedirs(out_dir, exist_ok=True)

    with open(out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["chapter", "code", "description"])
        writer.writeheader()
        writer.writerows(deduped_records)

    print(f"Wrote CSV to {out_file}")


if __name__ == "__main__":
    main()
