"""
APRA File Downloader
====================
Downloads current year and historical APRA CPPP Excel files.
Part of the APRA Performance Data Loader pipeline — Step 1A and 1B.

Usage:
    python3 apra_downloader.py --mode all --year 2025 --dir ./apra_data
    python3 apra_downloader.py --mode current --year 2025 --dir ./apra_data
    python3 apra_downloader.py --mode historical --dir ./apra_data

Modes:
    all        Download current year files AND all historical files not already present
    current    Download current year MySuper + TDP files only (Step 1A)
    historical Download all historical files not already present (Step 1B)
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

CURRENT_YEAR_URLS = {
    "MySuper": "https://www.apra.gov.au/{year}-annual-superannuation-performance-test-mysuper-products",
    "TDP":     "https://www.apra.gov.au/{year}-annual-superannuation-performance-test-trustee-directed-products",
}

CURRENT_YEAR_PATTERNS = {
    "MySuper": r"{year}\s*CPP[-\s]*MySuper",
    "TDP":     r"{year}\s*CPPP?\s*[-–]\s*Choice",
}

HISTORICAL_URL = "https://www.apra.gov.au/previous-performance-test-results"


def build_full_url(href: str) -> str:
    if href.startswith("http"):
        return href
    return "https://www.apra.gov.au" + href


def download_file(url: str, dest_path: Path) -> None:
    response = requests.get(url, headers=HEADERS, timeout=120)
    response.raise_for_status()
    dest_path.write_bytes(response.content)


def classify_historical_link(href: str, link_text: str) -> tuple[str, str]:
    """Return (year, product_type) from a historical page link."""
    year_match = re.search(r"(\d{4})", link_text + href)
    year = year_match.group(1) if year_match else "unknown"

    href_lower = href.lower()
    text_lower = link_text.lower()

    if "mysuper" in href_lower or "mysuper" in text_lower:
        product_type = "MySuper"
    elif "trustee-directed" in href_lower or "choice" in text_lower:
        product_type = "TDP"
    elif year.isdigit() and int(year) <= 2022:
        # 2021-2022 combined files are MySuper only
        product_type = "MySuper"
    else:
        product_type = "Unknown"

    return year, product_type


def download_current_year(year: int, download_dir: Path) -> list[dict]:
    """Step 1A — Download current year MySuper and TDP files."""
    results = []

    for product_type, url_template in CURRENT_YEAR_URLS.items():
        url = url_template.format(year=year)
        pattern = re.compile(
            CURRENT_YEAR_PATTERNS[product_type].format(year=year),
            re.IGNORECASE,
        )

        print(f"[1A] Fetching {product_type} page: {url}")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)

            if resp.status_code == 404:
                results.append({
                    "product_type": product_type,
                    "year": year,
                    "is_current_year": True,
                    "status": "failed",
                    "error": (
                        f"CPPP {product_type} data not yet available for {year}. "
                        f"Published June–December annually."
                    ),
                })
                continue

            resp.raise_for_status()
            soup = BeautifulSoup(resp.content, "html.parser")
            xlsx_links = [
                a for a in soup.find_all("a", href=True)
                if a["href"].lower().endswith(".xlsx")
            ]

            matched = None
            for link in xlsx_links:
                if pattern.search(link.get_text(strip=True)):
                    matched = link
                    break

            # Fallback: if only one xlsx link found, use it
            if matched is None and len(xlsx_links) == 1:
                matched = xlsx_links[0]

            if matched is None:
                found = [a.get_text(strip=True) for a in xlsx_links]
                results.append({
                    "product_type": product_type,
                    "year": year,
                    "is_current_year": True,
                    "status": "failed",
                    "error": (
                        f"No xlsx link matching pattern '{pattern.pattern}' found. "
                        f"Links on page: {found}"
                    ),
                })
                continue

            file_url = build_full_url(matched["href"])
            filename = file_url.split("/")[-1]
            if not filename.lower().endswith(".xlsx"):
                filename = f"{year}_CPP_{product_type}.xlsx"

            dest = download_dir / filename
            print(f"[1A] Downloading: {file_url} → {dest}")
            download_file(file_url, dest)

            results.append({
                "product_type": product_type,
                "year": year,
                "file_name": filename,
                "file_path": str(dest),
                "is_current_year": True,
                "status": "downloaded",
            })

        except requests.HTTPError as exc:
            results.append({
                "product_type": product_type,
                "year": year,
                "is_current_year": True,
                "status": "failed",
                "error": f"HTTP error: {exc}",
            })
        except Exception as exc:
            results.append({
                "product_type": product_type,
                "year": year,
                "is_current_year": True,
                "status": "failed",
                "error": str(exc),
            })

    return results


def download_historical(download_dir: Path, existing_files: set[str]) -> list[dict]:
    """Step 1B — Download historical files not already present locally."""
    results = []

    print(f"[1B] Fetching historical results page: {HISTORICAL_URL}")
    try:
        resp = requests.get(HISTORICAL_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")

        xlsx_links = [
            a for a in soup.find_all("a", href=True)
            if a["href"].lower().endswith(".xlsx")
        ]

        print(f"[1B] Found {len(xlsx_links)} xlsx links on historical page.")

        for link in xlsx_links:
            href = link["href"]
            link_text = link.get_text(strip=True)
            file_url = build_full_url(href)
            filename = file_url.split("/")[-1]
            if not filename.lower().endswith(".xlsx"):
                filename = link_text.replace(" ", "_") + ".xlsx"

            year, product_type = classify_historical_link(href, link_text)

            if filename in existing_files:
                results.append({
                    "product_type": product_type,
                    "year": year,
                    "file_name": filename,
                    "is_current_year": False,
                    "status": "skipped",
                    "reason": "already downloaded",
                })
                continue

            dest = download_dir / filename
            print(f"[1B] Downloading: {file_url} → {dest}")
            try:
                download_file(file_url, dest)
                results.append({
                    "product_type": product_type,
                    "year": year,
                    "file_name": filename,
                    "file_path": str(dest),
                    "is_current_year": False,
                    "status": "downloaded",
                })
            except Exception as exc:
                results.append({
                    "product_type": product_type,
                    "year": year,
                    "file_name": filename,
                    "is_current_year": False,
                    "status": "failed",
                    "error": str(exc),
                })

    except Exception as exc:
        results.append({
            "status": "failed",
            "error": f"Could not access historical results page: {exc}",
        })

    return results


def main():
    parser = argparse.ArgumentParser(description="APRA CPPP file downloader")
    parser.add_argument("--mode", choices=["all", "current", "historical"], default="all")
    parser.add_argument("--year", type=int, default=datetime.now().year)
    parser.add_argument("--dir", default="./apra_data")
    args = parser.parse_args()

    download_dir = Path(args.dir)
    download_dir.mkdir(parents=True, exist_ok=True)

    existing_files = {f for f in os.listdir(download_dir) if f.lower().endswith(".xlsx")}
    print(f"[setup] Download directory: {download_dir}")
    print(f"[setup] Existing files: {len(existing_files)}")
    print(f"[setup] Mode: {args.mode} | Year: {args.year}")

    results = []

    if args.mode in ("all", "current"):
        results.extend(download_current_year(args.year, download_dir))

    if args.mode in ("all", "historical"):
        # Refresh existing files list after current year downloads
        existing_files = {f for f in os.listdir(download_dir) if f.lower().endswith(".xlsx")}
        results.extend(download_historical(download_dir, existing_files))

    # Save manifest
    manifest_path = download_dir / "apra_manifest.json"
    manifest_path.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")

    # Summary
    downloaded = sum(1 for r in results if r.get("status") == "downloaded")
    skipped    = sum(1 for r in results if r.get("status") == "skipped")
    failed     = sum(1 for r in results if r.get("status") == "failed")

    print(f"\n{'=' * 50}")
    print(f"APRA File Downloader — Complete")
    print(f"  Downloaded : {downloaded}")
    print(f"  Skipped    : {skipped}")
    print(f"  Failed     : {failed}")
    print(f"  Manifest   : {manifest_path}")
    print(f"{'=' * 50}")

    if failed:
        print("\nFailed items:")
        for r in results:
            if r.get("status") == "failed":
                print(f"  - {r.get('product_type', 'N/A')} {r.get('year', '')}: {r.get('error', '')}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
