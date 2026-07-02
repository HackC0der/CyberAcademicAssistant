#!/usr/bin/env python3
"""
Unified abstract enrichment script for security-top4-papers dataset.

Reads existing Paper-Link.txt files, fetches abstracts from venue-specific
sources, and writes enriched Paper-Data.txt files (title\turl\tabstract).

Usage:
  uv run enrich_abstracts.py                     # all venues
  uv run enrich_abstracts.py --venue ndss        # single venue
  uv run enrich_abstracts.py --venue sp --year 2024  # single year
"""

import json
import os
import random
import re
import sys
import time
import unicodedata

import requests
from bs4 import BeautifulSoup

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }


def fetch(url, retries=3, timeout=30, headers=None):
    for attempt in range(retries):
        try:
            time.sleep(random.uniform(1.0, 2.5))
            r = requests.get(url, headers=headers or get_headers(), timeout=timeout)
            r.raise_for_status()
            return r.text
        except requests.RequestException as e:
            print(f"    [重试 {attempt + 1}/{retries}] {e}")
            if attempt < retries - 1:
                time.sleep(random.uniform(2.0, 4.0))
    return None


def normalize_title(text):
    """Normalize for fuzzy matching: lowercase, strip non-alphanumeric."""
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]", "", text.lower())


def load_paper_link_txt(filepath):
    """Load existing Paper-Link.txt file, return list of (title, url) and a normalized-title index."""
    if not os.path.exists(filepath):
        return [], {}
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.read().strip().split("\n")
    count = int(lines[0]) if lines else 0
    papers = []
    for line in lines[1:]:
        if "\t" in line:
            title, url = line.split("\t", 1)
            papers.append((title.strip(), url.strip()))
        elif line.strip():
            papers.append((line.strip(), ""))
    norm_index = {normalize_title(t): (t, u) for t, u in papers}
    return papers, norm_index


def save_paper_data_txt(filepath, papers):
    """Save enriched data as title\turl\tabstract."""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"{len(papers)}\n")
        for title, url, abstract in papers:
            # Replace newlines in abstract with spaces to keep single-line-per-record
            abs_clean = abstract.replace("\n", " ").replace("\r", " ") if abstract else ""
            f.write(f"{title}\t{url}\t{abs_clean}\n")


def venue_dir(venue):
    return os.path.join(PROJECT_DIR, venue)


# ---------------------------------------------------------------------------
# NDSS Abstract Fetcher
# ---------------------------------------------------------------------------

NDSS_YEARS = [2023, 2024, 2025, 2026]


def fetch_ndss_abstracts(year):
    """Fetch abstracts for NDSS papers by scraping paper detail pages."""
    list_url = f"https://www.ndss-symposium.org/ndss{year}/accepted-papers/"
    print(f"  Fetching paper list: {list_url}")
    html = fetch(list_url)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    items = soup.select("div.pt-cv-content-item h2.pt-cv-title a")
    paper_links = [(item.get_text(strip=True), item.get("href", "")) for item in items if item.get("href")]
    print(f"  Found {len(paper_links)} papers")

    results = []
    for i, (title, detail_url) in enumerate(paper_links, 1):
        print(f"  [{i}/{len(paper_links)}] {title[:60]}...", end=" ", flush=True)
        html2 = fetch(detail_url)
        if not html2:
            print("FAIL (fetch)")
            results.append((title, "", ""))
            continue

        soup2 = BeautifulSoup(html2, "html.parser")

        # Extract PDF URL
        pdf_url = ""
        pdf_btn = soup2.select_one("a.pdf-button")
        if pdf_btn:
            pdf_url = pdf_btn.get("href", "")

        # Extract abstract (NDSS pages duplicate content with p[0]/p[1] = authors, p[2]/p[3] = abstract)
        abstract = ""
        paper_data = soup2.select_one("div.paper-data")
        if paper_data:
            paras = paper_data.find_all("p")
            for p in paras:
                text = p.get_text(strip=True)
                # Skip author lines: contain parenthetical institution names
                if re.search(r"\([A-Z][A-Za-z\s]+(University|Institute|Lab|Laboratory|College|School|Center|Labs|Inc|Research|Technologies)\)", text):
                    continue
                if len(text) > 100:
                    abstract = text
                    break

        if abstract:
            print("OK")
        else:
            print("no abstract")
        results.append((title, pdf_url, abstract))

        if i % 20 == 0:
            time.sleep(random.uniform(2.0, 4.0))

    return results


# ---------------------------------------------------------------------------
# IEEE S&P Abstract Fetcher
# ---------------------------------------------------------------------------

SP_YEARS = [2023, 2024, 2025, 2026]

SP_PUBLICATION_QUERIES = {
    2023: '"2023 IEEE Symposium on Security and Privacy"',
    2024: '"2024 IEEE Symposium on Security and Privacy"',
    2025: '"2025 IEEE Symposium on Security and Privacy"',
    2026: '"2026 IEEE Symposium on Security and Privacy"',
}

IEEE_SEARCH_URL = "https://ieeexplore.ieee.org/rest/search"
IEEE_API_HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json",
    "Referer": "https://ieeexplore.ieee.org/",
}


def fetch_sp_ieee_records(year):
    """Search IEEE Xplore API for all S&P papers in a given year, return {norm_title: (title, pdf_url, abstract)}."""
    query = SP_PUBLICATION_QUERIES.get(year)
    if not query:
        return {}

    all_records = []
    page = 1
    total = None

    while True:
        payload = {
            "newsearch": True,
            "queryText": query,
            "highlight": False,
            "returnFacets": ["ALL"],
            "returnType": "SEARCH",
            "matchPubs": True,
            "pageNumber": page,
            "pageSize": 100,
        }
        try:
            time.sleep(random.uniform(1.0, 1.5))
            r = requests.post(IEEE_SEARCH_URL, json=payload, headers=IEEE_API_HEADERS, timeout=30)
            r.raise_for_status()
            data = r.json()
            if total is None:
                total = data.get("totalRecords", 0)
            records = data.get("records", [])
            if not records:
                break
            all_records.extend(records)
            if len(all_records) >= total:
                break
            page += 1
        except requests.RequestException as e:
            print(f"    [IEEE API 错误] page {page}: {e}")
            break

    result = {}
    for rec in all_records:
        title = rec.get("articleTitle", "")
        pdf = rec.get("pdfLink", "")
        abstract = rec.get("abstract", "")
        if title and pdf:
            pdf_url = f"https://ieeexplore.ieee.org{pdf}"
            result[normalize_title(title)] = (title, pdf_url, abstract)
    return result


def fetch_sp_abstracts(year):
    """Fetch abstracts for S&P papers via IEEE Xplore API."""
    print(f"  Querying IEEE Xplore API ({year})...")
    ieee_map = fetch_sp_ieee_records(year)
    print(f"  Got {len(ieee_map)} records from IEEE Xplore")

    # Load existing papers for title matching
    filepath = os.path.join(PROJECT_DIR, f"SP{year}-Paper-Link.txt")
    existing, norm_index = load_paper_link_txt(filepath)
    if not existing:
        print(f"  No existing data for SP {year}, using API records directly")
        return [(t, u, a) for t, u, a in ieee_map.values()]

    results = []
    matched = 0
    for orig_title, orig_url in existing:
        n = normalize_title(orig_title)
        if n in ieee_map:
            _, pdf_url, abstract = ieee_map[n]
            results.append((orig_title, pdf_url or orig_url, abstract))
            matched += 1
        else:
            results.append((orig_title, orig_url, ""))
    print(f"  Matched {matched}/{len(existing)} papers with abstracts")
    return results


# ---------------------------------------------------------------------------
# ACM CCS Abstract Fetcher
# ---------------------------------------------------------------------------

CCS_YEARS = [2023, 2024, 2025]


def _doi_from_url(url):
    """Extract DOI from ACM DL URL like https://dl.acm.org/doi/pdf/10.1145/XXXX.XXXX."""
    m = re.search(r"/doi/(?:pdf/)?(10\.\d{4,}/[^?&#\s]+)", url)
    return m.group(1) if m else ""


S2_API_URL = "https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=title,abstract"


def fetch_abstract_from_s2(doi):
    """Fetch abstract from Semantic Scholar API (free, no key needed)."""
    try:
        time.sleep(1.0)
        url = S2_API_URL.format(doi=doi)
        r = requests.get(url, headers={"User-Agent": "CCS-Abstract-Crawler/1.0"}, timeout=15)
        r.raise_for_status()
        data = r.json()
        abstract = data.get("abstract", "")
        return abstract or ""
    except requests.RequestException:
        return ""


CROSSREF_ABSTRACT_URL = "https://api.crossref.org/works/{doi}"


def fetch_abstract_from_crossref(doi):
    """Fetch abstract from Crossref API."""
    try:
        time.sleep(0.5)
        url = CROSSREF_ABSTRACT_URL.format(doi=doi)
        r = requests.get(url, headers={"User-Agent": "CCS-Abstract-Crawler/1.0"}, timeout=15)
        r.raise_for_status()
        data = r.json()
        abstract = data.get("message", {}).get("abstract", "")
        if abstract:
            return abstract
    except requests.RequestException:
        pass
    return ""


def fetch_ccs_abstracts(year):
    """Fetch abstracts for CCS papers by extracting DOIs from PDF URLs and querying S2."""
    filepath = os.path.join(PROJECT_DIR, f"CCS{year}-Paper-Link.txt")
    existing, norm_index = load_paper_link_txt(filepath)
    if not existing:
        print(f"  No existing data for CCS {year}")
        return []

    results = []
    matched_doi = 0
    for i, (orig_title, orig_url) in enumerate(existing, 1):
        doi = _doi_from_url(orig_url)
        if doi:
            matched_doi += 1
            print(f"  [{i}/{len(existing)}] {orig_title[:55]:55s}", end=" ", flush=True)
            abstract = fetch_abstract_from_s2(doi)
            if not abstract:
                abstract = fetch_abstract_from_crossref(doi)
            if abstract:
                print("OK")
            else:
                print("no abstract")
            results.append((orig_title, orig_url, abstract))
        else:
            # No DOI in URL
            results.append((orig_title, orig_url, ""))
    print(f"  DOIs extracted: {matched_doi}/{len(existing)}, "
          f"abstracts found: {len([r for r in results if r[2]])}")
    return results


# ---------------------------------------------------------------------------
# USENIX Abstract Fetcher
# ---------------------------------------------------------------------------

USENIX_CONFERENCES = [
    (2023, "summer", "https://www.usenix.org/conference/usenixsecurity23/summer-accepted-papers"),
    (2023, "fall", "https://www.usenix.org/conference/usenixsecurity23/fall-accepted-papers"),
    (2024, "summer", "https://www.usenix.org/conference/usenixsecurity24/summer-accepted-papers"),
    (2024, "fall", "https://www.usenix.org/conference/usenixsecurity24/fall-accepted-papers"),
    (2025, "cycle1", "https://www.usenix.org/conference/usenixsecurity25/cycle1-accepted-papers"),
    (2026, "cycle1", "https://www.usenix.org/conference/usenixsecurity26/cycle1-accepted-papers"),
]


def fetch_usenix_abstracts_for_session(year, label, url):
    """Fetch abstracts for one USENIX session."""
    print(f"  Fetching paper list: {url}")
    html = fetch(url)
    if not html:
        return [], label

    soup = BeautifulSoup(html, "html.parser")
    papers = set()
    for a in soup.select("div.field-name-field-session-papers a"):
        href = a.get("href", "")
        text = a.get_text(strip=True)
        if text and "/presentation/" in href:
            papers.add((text, href))

    papers = sorted(papers, key=lambda x: x[0])
    print(f"  Found {len(papers)} papers")

    results = []
    for i, (title, detail_path) in enumerate(papers, 1):
        print(f"  [{i}/{len(papers)}] {title[:60]}...", end=" ", flush=True)
        detail_url = f"https://www.usenix.org{detail_path}"
        html2 = fetch(detail_url)
        if not html2:
            print("FAIL (fetch)")
            results.append((title, "", ""))
            continue

        soup2 = BeautifulSoup(html2, "html.parser")

        # Extract PDF URL
        pdf_url = ""
        pdf_link = soup2.select_one("span.file a")
        if pdf_link:
            pdf_url = pdf_link.get("href", "")

        # Extract abstract (USENIX uses field-name-field-paper-description in Drupal 7 / Backdrop CMS)
        abstract = ""
        for sel in ["div.field-name-field-paper-description", "div.field--name-field-paper-description",
                     "div.field-type-text-with-summary", "div.node__content div.field"]:
            el = soup2.select_one(sel)
            if el:
                abstract = el.get_text(strip=True)
                break

        if abstract:
            print("OK")
        else:
            print("no abstract")
        results.append((title, pdf_url, abstract))

        if i % 20 == 0:
            time.sleep(random.uniform(2.0, 4.0))

    return results, label


def fetch_usenix_abstracts(year, label=None):
    """Fetch USENIX abstracts for a given year (and optional label filter)."""
    all_results = []
    for y, lbl, url in USENIX_CONFERENCES:
        if y != year:
            continue
        if label and lbl != label:
            continue
        results, _ = fetch_usenix_abstracts_for_session(y, lbl, url)
        all_results.extend(results)
    return all_results


# ---------------------------------------------------------------------------
# Main Orchestrator
# ---------------------------------------------------------------------------

VENUE_HANDLERS = {
    "ndss": (NDSS_YEARS, fetch_ndss_abstracts),
    "sp": (SP_YEARS, fetch_sp_abstracts),
    "ccs": (CCS_YEARS, fetch_ccs_abstracts),
    "usenix": ([y for y, _, _ in USENIX_CONFERENCES], None),
}


def enrich_venue(venue, years, fetcher):
    """Run enrichment for a venue across given years."""
    print(f"\n{'=' * 60}")
    print(f"  Enriching {venue.upper()} abstracts")
    print(f"{'=' * 60}")

    for year in years:
        print(f"\n--- {venue.upper()} {year} ---")
        try:
            results = fetcher(year)
            if not results:
                print("  No results, skipping")
                continue

            # Filter to papers that actually have abstracts
            with_abstracts = [(t, u, a) for t, u, a in results if a]
            print(f"  Abstracts found: {len(with_abstracts)}/{len(results)}")
            if not with_abstracts:
                print("  No abstracts to save")
                continue

            outpath = os.path.join(PROJECT_DIR, f"{venue.upper()}{year}-Paper-Data.txt")
            save_paper_data_txt(outpath, results)
            print(f"  Saved -> {os.path.basename(outpath)}")

        except Exception as e:
            print(f"  [Error] {e}")


def _enrich_usenix(year_filter=None):
    """Run USENIX enrichment for all (or filtered) sessions."""
    for y, lbl, url in USENIX_CONFERENCES:
        if year_filter and y != year_filter:
            continue
        outpath = os.path.join(PROJECT_DIR, f"USENIXSEC{y}-{lbl}-Paper-Data.txt")
        if os.path.exists(outpath):
            print(f"  Already exists: {os.path.basename(outpath)}, skipping")
            continue
        print(f"\n--- USENIX {y} {lbl} ---")
        try:
            results, _ = fetch_usenix_abstracts_for_session(y, lbl, url)
            if results:
                with_abs = [(t, u, a) for t, u, a in results if a]
                print(f"  Abstracts: {len(with_abs)}/{len(results)}")
                save_paper_data_txt(outpath, results)
                print(f"  Saved -> {os.path.basename(outpath)}")
        except Exception as e:
            print(f"  [Error] {e}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Enrich security-top4-papers dataset with abstracts")
    parser.add_argument("--venue", choices=["ndss", "sp", "ccs", "usenix"], help="Specific venue to process")
    parser.add_argument("--year", type=int, help="Specific year to process")
    args = parser.parse_args()

    if args.venue:
        venues = {args.venue: VENUE_HANDLERS[args.venue]}
    else:
        venues = VENUE_HANDLERS

    for venue, (years, fetcher) in venues.items():
        if venue == "usenix":
            _enrich_usenix(args.year)
        else:
            if args.year:
                years = [y for y in years if y == args.year]
            if not years:
                print(f"No years to process for {venue}")
                continue
            enrich_venue(venue, years, fetcher)


if __name__ == "__main__":
    main()
