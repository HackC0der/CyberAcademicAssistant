#!/usr/bin/env python3
"""
Verify all PDF links in the security-top4-papers dataset.
Checks each URL returns HTTP 200, reports dead/moved/redirected links.

Usage:
  uv run verify_links.py                    # verify all files
  uv run verify_links.py --venue sp         # single venue
  uv run verify_links.py --timeout 10       # per-request timeout
"""

import os
import sys
import time
import random
import requests
from urllib.parse import urlparse

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
]


def get_data_files(venue_filter=None):
    """Find all Paper-Link.txt and Paper-Data.txt files."""
    files = []
    for fname in sorted(os.listdir(PROJECT_DIR)):
        if not (fname.endswith("-Paper-Link.txt") or fname.endswith("-Paper-Data.txt")):
            continue
        if venue_filter and not fname.lower().startswith(venue_filter.lower()):
            continue
        files.append(os.path.join(PROJECT_DIR, fname))
    return files


def load_urls(filepath):
    """Extract URLs from data file."""
    urls = []
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.read().strip().split("\n")
    for line in lines[1:]:  # skip count line
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            title = parts[0]
            url = parts[1]
            urls.append((title, url))
    return urls


def check_url(title, url, timeout=15):
    """Check if URL is accessible. Returns (status, redirect_target or None)."""
    if not url:
        return "NO_URL", None
    try:
        r = requests.get(
            url,
            headers={"User-Agent": random.choice(USER_AGENTS)},
            timeout=timeout,
            allow_redirects=True,
            stream=True,
        )
        if r.status_code == 200:
            # Check content type
            ct = r.headers.get("Content-Type", "")
            if "application/pdf" in ct or "application/octet-stream" in ct or "text/html" in ct:
                return "OK", None
            else:
                return f"UNEXPECTED_CT({ct})", r.url
        elif r.status_code == 403:
            return "FORBIDDEN", r.url
        elif r.status_code == 404:
            return "NOT_FOUND", r.url
        elif 300 <= r.status_code < 400:
            return f"REDIRECT({r.status_code})", r.url
        else:
            return f"HTTP_{r.status_code}", r.url
    except requests.Timeout:
        return "TIMEOUT", None
    except requests.ConnectionError:
        return "CONNECTION_ERROR", None
    except requests.RequestException as e:
        return f"ERROR({type(e).__name__})", None


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Verify PDF links in security-top4-papers dataset")
    parser.add_argument("--venue", choices=["ndss", "sp", "ccs", "usenix", "ccs", "usenixsec"], help="Venue filter")
    parser.add_argument("--timeout", type=int, default=15, help="Request timeout in seconds")
    parser.add_argument("--sample", type=int, help="Sample N papers per file (for quick check)")
    args = parser.parse_args()

    venue_filter = args.venue
    if venue_filter == "usenixsec":
        venue_filter = "usenix"

    files = get_data_files(venue_filter)
    if not files:
        print("No data files found.")
        return

    print(f"Found {len(files)} data files")
    total_ok = 0
    total_bad = 0
    bad_links = []

    for filepath in files:
        fname = os.path.basename(filepath)
        urls = load_urls(filepath)
        if args.sample and len(urls) > args.sample:
            urls = urls[:args.sample]

        print(f"\n{'=' * 60}")
        print(f"  {fname} ({len(urls)} papers)")
        print(f"{'=' * 60}")

        ok = 0
        bad = 0
        for i, (title, url) in enumerate(urls, 1):
            print(f"  [{i}/{len(urls)}] {title[:55]:55s}", end=" ", flush=True)
            status, target = check_url(title, url, args.timeout)
            if status == "OK":
                ok += 1
                print("✓")
            else:
                bad += 1
                bad_links.append((fname, title, url, status))
                print(f"✗ {status}")
            time.sleep(random.uniform(0.5, 1.0))

        total_ok += ok
        total_bad += bad
        print(f"  Result: {ok} OK, {bad} bad")

    print(f"\n{'=' * 60}")
    print(f"  TOTAL: {total_ok} OK, {total_bad} bad out of {total_ok + total_bad}")
    print(f"{'=' * 60}")

    if bad_links:
        print(f"\n  Bad links ({len(bad_links)}):")
        print(f"  {'FILE':30s} {'TITLE':50s} {'STATUS'}")
        print(f"  {'-'*30} {'-'*50} {'-'*20}")
        for fname, title, url, status in bad_links:
            print(f"  {fname:30s} {title[:48]:48s} {status}")

    return 1 if total_bad > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
