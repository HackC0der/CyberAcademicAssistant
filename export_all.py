#!/usr/bin/env python3
"""
Export the entire security-top4-papers dataset as a unified JSON file.

Reads all Paper-Data.txt (enriched with abstracts) and Paper-Link.txt files,
outputs a single security-top4-papers.json with complete metadata.

Usage:
  uv run export_all.py                         # default: security-top4-papers.json
  uv run export_all.py --output dataset.json   # custom output path
  uv run export_all.py --pretty                 # pretty-print JSON
"""

import json
import os
import re
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

VENUE_MAP = {
    "NDSS": "Network and Distributed System Security Symposium",
    "SP": "IEEE Symposium on Security and Privacy",
    "CCS": "ACM Conference on Computer and Communications Security",
    "USENIXSEC": "USENIX Security Symposium",
}


def split_line(line):
    """Split a data line into [title, url, abstract?], handling both tab and comma separators.

    The original crawlers used \t, but some data files use comma.
    If no tab is found, split on the last comma preceding 'https://'.
    """
    if "\t" in line:
        parts = line.split("\t")
        title = parts[0]
        url = parts[1] if len(parts) >= 2 else ""
        abstract = parts[2] if len(parts) >= 3 else ""
        return title, url, abstract
    # Comma-separated: find the last comma before https://
    idx = line.rfind(",https://")
    if idx >= 0:
        title = line[:idx]
        url = line[idx + 1:]
        return title, url, ""
    idx = line.rfind(",http://")
    if idx >= 0:
        title = line[:idx]
        url = line[idx + 1:]
        return title, url, ""
    return line.strip(), "", ""


def parse_data_file(filepath):
    """Parse a Paper-Data.txt or Paper-Link.txt file into a list of paper dicts.

    The file format is:
      line 1: count
      subsequent lines: title\turl[\tabstract]

    Returns (venue, year, label, papers)
    """
    fname = os.path.basename(filepath)
    # Extract venue, year, and optional label
    match = re.match(r"(NDSS|SP|CCS|USENIXSEC)(\d{4})(?:-([a-z0-9]+))?-Paper", fname, re.IGNORECASE)
    if not match:
        return None, None, None, []

    venue = match.group(1).upper()
    year = int(match.group(2))
    label = match.group(3) or ""

    # Map normalized venue
    if venue == "USENIXSEC":
        venue_full = "USENIX"
    else:
        venue_full = venue

    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.read().strip().split("\n")

    if len(lines) < 2:
        return venue_full, year, label, []

    papers = []
    for line in lines[1:]:
        if not line.strip():
            continue
        title, url, abstract = split_line(line)
        papers.append({
            "venue": venue_full,
            "venue_full_name": VENUE_MAP.get(venue_full, ""),
            "year": year,
            "label": label,
            "title": title,
            "pdf_url": url,
            "abstract": abstract,
        })

    return venue_full, year, label, papers


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Export security-top4-papers as unified JSON")
    parser.add_argument("--output", "-o", default="security-top4-papers.json", help="Output JSON path")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON")
    args = parser.parse_args()

    all_papers = []
    stats = {}
    # index by (venue, year, label) to know which groups already have data
    data_groups = set()

    for fname in sorted(os.listdir(PROJECT_DIR)):
        fpath = os.path.join(PROJECT_DIR, fname)
        if not os.path.isfile(fpath):
            continue
        if not (fname.endswith("-Paper-Data.txt") or fname.endswith("-Paper-Link.txt")):
            continue

        venue, year, label, papers = parse_data_file(fpath)
        if not papers:
            continue

        group_key = (venue, year, label)
        is_data = fname.endswith("-Paper-Data.txt")

        # Skip Paper-Link.txt if Paper-Data.txt already processed for this group
        if not is_data and group_key in data_groups:
            continue

        if is_data:
            data_groups.add(group_key)

        all_papers.extend(papers)

        # Count stats
        key = venue or "UNKNOWN"
        if key not in stats:
            stats[key] = {}
        if year not in stats[key]:
            stats[key][year] = {"total": 0, "with_abstract": 0, "with_url": 0}
        for p in papers:
            stats[key][year]["total"] += 1
            if p.get("abstract"):
                stats[key][year]["with_abstract"] += 1
            if p.get("pdf_url"):
                stats[key][year]["with_url"] += 1

    # Sort papers by venue, year, title
    all_papers.sort(key=lambda p: (p["venue"], p["year"], p["title"]))

    # Build output
    output = {
        "meta": {
            "version": "2.0",
            "generated": __import__("datetime").datetime.now().strftime("%Y-%m-%d"),
            "total_papers": len(all_papers),
            "description": "Security top-4 conference papers dataset (NDSS, IEEE S&P, ACM CCS, USENIX Security)",
        },
        "stats": stats,
        "papers": all_papers,
    }

    indent = 2 if args.pretty else None
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=indent)

    print(f"Exported {len(all_papers)} papers -> {args.output}")
    print(f"\nCoverage:")
    for venue in sorted(stats.keys()):
        for year in sorted(stats[venue].keys()):
            s = stats[venue][year]
            abs_pct = s["with_abstract"] / s["total"] * 100 if s["total"] else 0
            url_pct = s["with_url"] / s["total"] * 100 if s["total"] else 0
            print(f"  {venue} {year}: {s['total']} papers, "
                  f"abstracts: {s['with_abstract']}/{s['total']} ({abs_pct:.0f}%), "
                  f"urls: {s['with_url']}/{s['total']} ({url_pct:.0f}%)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
