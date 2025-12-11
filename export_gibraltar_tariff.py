#!/usr/bin/env python3
import os
import csv
import re
import time
import argparse
from typing import List, Dict

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.hmcustoms.gov.gi/portal/services/tariff/print.jsf?c={chapter}"

# Match full Gibraltar-style codes like:
# 0101210000-00-00
# 0102292*00-2*-00
# 010129**00-**-00
CODE_PATTERN = re.compile(
    r"\b[0-9*]{10}-[0-9*]{2}-[0-9*]{2}\b"
)


def fetch_chapter_text(chapter: int) -> str:
    """Fetch raw text for a chapter from the Gibraltar HM Customs tariff."""
    chapter_str = f"{chapter:02d}"  # 1 -> "01", 10 -> "10"
    url = BASE_URL.format(chapter=chapter_str)

    resp = requests.get(
        url,
        timeout=30,
        headers={"User-Agent": "gib-tariff-scraper/1.0"},
    )
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    text = soup.get_text("\n", strip=True)
    return text


def extract_chapter_name(text: str, chapter: int) -> str:
    """
    Extract the 'chapter name' line, e.g.
    'CHAPTER 01 - LIVE ANIMALS' from a line like:
    '01 CHAPTER 01 - LIVE ANIMALS'
    """
    chapter_str = f"{chapter:02d}"
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        # Look for something like:
        # 01 CHAPTER 01 - LIVE ANIMALS
        m = re.match(rf"^{chapter_str}\s+(CHAPTER\s+.+)$", line)
        if m:
            return m.group(1).strip()

    return ""


def extract_codes_from_text(text: str, chapter: int) -> List[Dict[str, str]]:
    """Extract (chapter, code, description) from the chapter text."""
    records = []
    seen = set()  # dedupe by (chapter, code, description)

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        for match in CODE_PATTERN.finditer(line):
            code = match.group(0)

            # Description: everything AFTER the code occurrence on that line
            desc = line[match.end():].strip()
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
    parser = argparse.ArgumentParser(
        description="Export Gibraltar harmonised tariff codes and chapters to CSV."
    )
    parser.add_argument(
        "--codes-outfile",
        default="gibraltar_harmonised_codes.csv",
        help="Output CSV file path for codes "
             "(default: gibraltar_harmonised_codes.csv)",
    )
    parser.add_argument(
        "--chapters-outfile",
        default="gibraltar_chapters.csv",
        help="Output CSV file path for chapter names "
             "(default: gibraltar_chapters.csv)",
    )
    args = parser.parse_args()

    all_records: List[Dict[str, str]] = []
    chapter_records: List[Dict[str, str]] = []

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

        # Extract chapter name once per chapter
        chapter_name = extract_chapter_name(text, chapter)
        if chapter_name:
            chapter_records.append(
                {
                    "chapter": f"{chapter:02d}",
                    "chapter_title": chapter_name,
                }
            )
        else:
            # Still include it as blank for visibility
            chapter_records.append(
                {
                    "chapter": f"{chapter:02d}",
                    "chapter_title": "",
                }
            )

        # Extract individual codes
        chapter_codes = extract_codes_from_text(text, chapter)
        print(f"  -> found {len(chapter_codes)} codes")
        all_records.extend(chapter_codes)

        # politeness delay
        time.sleep(0.3)

    # Global dedupe for codes
    final_seen = set()
    deduped_records = []
    for rec in all_records:
        key = (rec["chapter"], rec["code"], rec["description"])
        if key in final_seen:
            continue
        final_seen.add(key)
        deduped_records.append(rec)

    print(f"Total codes collected: {len(deduped_records)}")

    # Ensure /data style dirs exist for both outputs
    codes_out_file = args.codes_outfile
    chapters_out_file = args.chapters_outfile

    for path in (codes_out_file, chapters_out_file):
        out_dir = os.path.dirname(path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

    # Write codes CSV
    with open(codes_out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["chapter", "code", "description"])
        writer.writeheader()
        writer.writerows(deduped_records)

    print(f"Wrote codes CSV to {codes_out_file}")

    # Dedupe chapter entries by chapter (if any duplicates)
    chapters_seen = set()
    chapters_clean = []
    for rec in chapter_records:
        if rec["chapter"] in chapters_seen:
            continue
        chapters_seen.add(rec["chapter"])
        chapters_clean.append(rec)

    # Write chapters CSV
    with open(chapters_out_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["chapter", "chapter_title"])
        writer.writeheader()
        writer.writerows(chapters_clean)

    print(f"Wrote chapters CSV to {chapters_out_file}")


if __name__ == "__main__":
    main()
