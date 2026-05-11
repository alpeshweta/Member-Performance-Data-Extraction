"""
APRA Longitudinal Builder
=========================
Joins cleaned APRA CPPP records across all years to produce two unified datasets:
  - mysuper_products: flat list, history spans 2021+
  - tdp_products: hierarchical identifier list, history spans 2023+

Part of the APRA Performance Data Loader pipeline — Step 4.

Usage:
    python3 apra_longitudinal.py --workdir ./apra_work --year 2025
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


def build_mysuper_products(records: list[dict], current_year: int) -> tuple[list[dict], list[dict]]:
    """
    Group MySuper records by join_key and build longitudinal entries.
    Returns (products_list, log_entries).
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        if rec["product_type"] == "MySuper":
            groups[rec["join_key"]].append(rec)

    products = []
    log_entries = []

    for join_key, recs in groups.items():
        # Deduplicate within a year — keep first; log conflicts
        by_year: dict[int, dict] = {}
        for rec in recs:
            yr = int(rec["source_year"])
            if yr in by_year:
                existing = by_year[yr]
                if existing.get("pass_fail") != rec.get("pass_fail"):
                    log_entries.append({
                        "type": "duplicate_conflict",
                        "join_key": join_key,
                        "product_type": "MySuper",
                        "year": yr,
                        "kept": existing.get("pass_fail"),
                        "discarded": rec.get("pass_fail"),
                    })
            else:
                by_year[yr] = rec

        current = by_year.get(current_year)
        has_current = current is not None

        entry: dict = {
            "product_name": current["product_name"] if has_current else recs[0]["product_name"],
            "current_metrics_available": has_current,
        }

        if has_current:
            entry["pass_fail_current"] = current.get("pass_fail")
            entry["nir_10yr"]    = current.get("nir_10yr")
            entry["nir_rag"]     = current.get("nir_rag", "Unknown")
            entry["fees_50k"]    = current.get("fees_50k")
            entry["fees_50k_rag"]  = current.get("fees_50k_rag", "Unknown")
            entry["fees_100k"]   = current.get("fees_100k")
            entry["fees_100k_rag"] = current.get("fees_100k_rag", "Unknown")
        else:
            entry["pass_fail_current"] = None
            entry["nir_10yr"] = entry["nir_rag"] = None
            entry["fees_50k"] = entry["fees_50k_rag"] = None
            entry["fees_100k"] = entry["fees_100k_rag"] = None
            log_entries.append({
                "type": "history_only",
                "join_key": join_key,
                "product_type": "MySuper",
                "note": "No current year record found",
            })

        # Build history object
        history = {}
        for yr, rec in by_year.items():
            if yr != current_year or not has_current:
                history[str(yr)] = rec.get("pass_fail", "Unknown")
            else:
                history[str(yr)] = rec.get("pass_fail", "Unknown")

        # Sort descending
        entry["history"] = dict(sorted(history.items(), key=lambda x: x[0], reverse=True))
        products.append(entry)

    return products, log_entries


def build_tdp_products(records: list[dict], current_year: int) -> tuple[list[dict], list[dict]]:
    """
    Group TDP records by composite join_key and build longitudinal entries.
    Returns (products_list, log_entries).
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for rec in records:
        if rec["product_type"] in ("Platform TDP", "Non-Platform TDP"):
            groups[rec["join_key"]].append(rec)

    products = []
    log_entries = []

    for join_key, recs in groups.items():
        # Deduplicate within a year
        by_year: dict[int, dict] = {}
        for rec in recs:
            yr = int(rec["source_year"])
            if yr in by_year:
                existing = by_year[yr]
                if existing.get("pass_fail") != rec.get("pass_fail"):
                    log_entries.append({
                        "type": "duplicate_conflict",
                        "join_key": join_key,
                        "product_type": rec["product_type"],
                        "year": yr,
                        "kept": existing.get("pass_fail"),
                        "discarded": rec.get("pass_fail"),
                    })
            else:
                by_year[yr] = rec

        representative = by_year.get(current_year) or recs[0]
        current = by_year.get(current_year)
        has_current = current is not None

        entry: dict = {
            "product_name": representative.get("product_name", ""),
            "investment_menu_name": representative.get("investment_menu_name", ""),
            "investment_option_name": representative.get("investment_option_name", ""),
            "product_type": representative.get("product_type", ""),
            "current_metrics_available": has_current,
        }

        if has_current:
            entry["pass_fail_current"] = current.get("pass_fail")
            entry["nir_10yr"]    = current.get("nir_10yr")
            entry["nir_rag"]     = current.get("nir_rag", "Unknown")
            entry["fees_50k"]    = current.get("fees_50k")
            entry["fees_50k_rag"]  = current.get("fees_50k_rag", "Unknown")
            entry["fees_100k"]   = current.get("fees_100k")
            entry["fees_100k_rag"] = current.get("fees_100k_rag", "Unknown")
        else:
            entry["pass_fail_current"] = None
            entry["nir_10yr"] = entry["nir_rag"] = None
            entry["fees_50k"] = entry["fees_50k_rag"] = None
            entry["fees_100k"] = entry["fees_100k_rag"] = None
            log_entries.append({
                "type": "history_only",
                "join_key": join_key,
                "product_type": representative.get("product_type"),
                "note": "No current year record found",
            })

        history = {
            str(yr): rec.get("pass_fail", "Unknown")
            for yr, rec in by_year.items()
        }
        entry["history"] = dict(sorted(history.items(), key=lambda x: x[0], reverse=True))
        products.append(entry)

    return products, log_entries


def main():
    parser = argparse.ArgumentParser(description="APRA longitudinal dataset builder")
    parser.add_argument("--workdir", default="./apra_work")
    parser.add_argument("--year", type=int, required=True, help="Current year (e.g., 2025)")
    args = parser.parse_args()

    workdir = Path(args.workdir)
    cleaned_path = workdir / "apra_cleaned.json"

    if not cleaned_path.exists():
        print(f"ERROR: {cleaned_path} not found. Run apra_cleaner.py first.", file=sys.stderr)
        return 1

    records = json.loads(cleaned_path.read_text(encoding="utf-8"))
    print(f"[setup] Building longitudinal datasets from {len(records)} cleaned records.")
    print(f"[setup] Current year: {args.year}")

    mysuper_products, ms_log = build_mysuper_products(records, args.year)
    tdp_products, tdp_log = build_tdp_products(records, args.year)

    all_log = ms_log + tdp_log

    # Build summary
    ms_total = len(mysuper_products)
    ms_history_only = sum(1 for p in mysuper_products if not p["current_metrics_available"])
    tdp_platform = sum(1 for p in tdp_products if p.get("product_type") == "Platform TDP")
    tdp_non_platform = sum(1 for p in tdp_products if p.get("product_type") == "Non-Platform TDP")
    tdp_history_only = sum(1 for p in tdp_products if not p["current_metrics_available"])

    mysuper_years = sorted({yr for p in mysuper_products for yr in p.get("history", {}).keys()}, reverse=True)
    tdp_years = sorted({yr for p in tdp_products for yr in p.get("history", {}).keys()}, reverse=True)

    duplicate_conflicts = [e for e in all_log if e.get("type") == "duplicate_conflict"]

    build_summary = {
        "total_mysuper": ms_total,
        "mysuper_with_current_metrics": ms_total - ms_history_only,
        "mysuper_history_only": ms_history_only,
        "total_tdp_platform": tdp_platform,
        "total_tdp_non_platform": tdp_non_platform,
        "tdp_history_only": tdp_history_only,
        "mysuper_history_years": mysuper_years,
        "tdp_history_years": tdp_years,
        "duplicate_conflicts": len(duplicate_conflicts),
    }

    output = {
        "mysuper_products": mysuper_products,
        "tdp_products": tdp_products,
        "build_summary": build_summary,
    }

    longitudinal_path = workdir / "apra_longitudinal.json"
    log_path = workdir / "apra_longitudinal_log.json"

    longitudinal_path.write_text(json.dumps(output, indent=2, default=str), encoding="utf-8")
    log_path.write_text(json.dumps(all_log, indent=2, default=str), encoding="utf-8")

    print(f"\n{'=' * 50}")
    print(f"APRA Longitudinal Builder — Complete")
    print(f"  MySuper products     : {ms_total} ({ms_history_only} history only)")
    print(f"  TDP — Platform       : {tdp_platform}")
    print(f"  TDP — Non-Platform   : {tdp_non_platform}")
    print(f"  TDP — history only   : {tdp_history_only}")
    print(f"  MySuper history yrs  : {mysuper_years}")
    print(f"  TDP history years    : {tdp_years}")
    print(f"  Duplicate conflicts  : {len(duplicate_conflicts)}")
    print(f"  Longitudinal JSON    : {longitudinal_path}")
    print(f"{'=' * 50}")

    if duplicate_conflicts:
        print("\n⚠️  Duplicate conflicts found — review apra_longitudinal_log.json before proceeding.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
