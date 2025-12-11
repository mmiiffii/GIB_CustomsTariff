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

# Match full Gibraltar-style codes
CODE_PATTERN = re.compile(
    r"\b[0-9*]{10}-[0-9*]{2}-[0-9*]{2}\b"
)


def fetch_chapter_text(chapter: int) -> str:
    """Fetch raw text for a chapter from the Gibraltar HM Customs tariff."""
    chapter_str = f"{chapter:02d}"
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
    """Extract the chapter title"""
    chapter_str = f"{chapter:02d}"
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("CHAPTER ") and chapter_str in line:
            return line.strip()
    return ""


def extract_hierarchy_from_text(text: str, chapter: int) -> List[Dict[str, str]]:
    """
    Extract complete hierarchy with descriptions for each level:
    chapter → heading (with description) → subheading (with description) → code (with description)
    """
    records = []
    seen = set()
    
    lines = text.splitlines()
    chapter_str = f"{chapter:02d}"
    
    current_heading = ""
    current_heading_desc = ""
    current_subheading = ""
    current_subheading_desc = ""
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        
        if not line:
            i += 1
            continue
        
        # Skip chapter title and headers
        if line.startswith("CHAPTER ") or line in ["Chapter", "Heading", "Article Description"]:
            i += 1
            continue
        
        # Check for 4-digit heading (e.g., "0101")
        if len(line) == 4 and line.isdigit() and not CODE_PATTERN.match(line):
            current_heading = line
            current_subheading = ""
            current_heading_desc = ""
            current_subheading_desc = ""
            
            # Get heading description from next line if available
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and not next_line.isdigit() and not CODE_PATTERN.match(next_line):
                    current_heading_desc = next_line
                    i += 1
            i += 1
            continue
        
        # Check for 5-digit subheading (e.g., "01012")
        if (len(line) == 5 and line.isdigit() and 
            line.startswith(current_heading) and not CODE_PATTERN.match(line)):
            current_subheading = line
            current_subheading_desc = ""
            
            # Get subheading description from next line if available
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and not next_line.isdigit() and not CODE_PATTERN.match(next_line):
                    current_subheading_desc = next_line
                    i += 1
            i += 1
            continue
        
        # Check for tariff codes
        for match in CODE_PATTERN.finditer(line):
            code = match.group(0)
            
            # Get description from rest of current line or next line
            desc = line[match.end():].strip()
            desc = desc.lstrip(" -–—:")
            
            if not desc and i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if next_line and not CODE_PATTERN.match(next_line):
                    desc = next_line
            
            key = (chapter_str, current_heading, current_heading_desc, 
                   current_subheading, current_subheading_desc, code, desc)
            if key in seen:
                continue
            seen.add(key)
            
            records.append({
                "chapter": chapter_str,
                "heading": current_heading,
                "heading_description": current_heading_desc,
                "subheading": current_subheading,
                "subheading_description": current_subheading_desc,
                "code": code,
                "description": desc,
            })
        
        i += 1
    
    return records


def main():
    parser = argparse.ArgumentParser(
        description="Export complete Gibraltar harmonised tariff structure to CSV."
    )
    parser.add_argument(
        "--hierarchy-outfile",
        default="gibraltar_tariff_hierarchy.csv",
        help="Output CSV file path for complete hierarchy "
             "(default: gibraltar_tariff_hierarchy.csv)",
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

        # Extract chapter name
        chapter_name = extract_chapter_name(text, chapter)
        chapter_records.append({
            "chapter": f"{chapter:02d}",
            "chapter_title": chapter_name,
        })

        # Extract complete hierarchy
        hierarchy_records = extract_hierarchy_from_text(text, chapter)
        print(f"  -> found {len(hierarchy_records)} codes")
        all_records.extend(hierarchy_records)

        time.sleep(0.3)

    # Global dedupe
    final_seen = set()
    deduped_records = []
    for rec in all_records:
        key = (rec["chapter"], rec["heading"], rec["heading_description"], 
               rec["subheading"], rec["subheading_description"], 
               rec["code"], rec["description"])
        if key in final_seen:
            continue
        final_seen.add(key)
        deduped_records.append(rec)

    print(f"Total codes collected: {len(deduped_records)}")

    # Ensure output directories exist
    for path in (args.hierarchy_outfile, args.chapters_outfile):
        out_dir = os.path.dirname(path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

    # Write hierarchy CSV
    with open(args.hierarchy_outfile, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, 
            fieldnames=[
                "chapter", 
                "heading", 
                "heading_description",
                "subheading", 
                "subheading_description",
                "code", 
                "description"
            ]
        )
        writer.writeheader()
        writer.writerows(deduped_records)

    print(f"Wrote hierarchy CSV to {args.hierarchy_outfile}")

    # Write chapters CSV
    with open(args.chapters_outfile, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["chapter", "chapter_title"])
        writer.writeheader()
        writer.writerows(chapter_records)

    print(f"Wrote chapters CSV to {args.chapters_outfile}")


if __name__ == "__main__":
    main()
