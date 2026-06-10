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

    Cross-year matching strategy
    ----------------------------
    2025 files: Product name | Investment menu name | Investment option name
    2023/2024 files: only Investment option name (no Product/Menu columns).

    To link historical records to current-year entries we use the APRA option
    identifier (Investment option identifier^^), which is stable across all years.

    For each current-year (2025) composite key we build an option_id lookup.
    Historical records whose option_identifier matches a current-year entry have
    their pass/fail result fanned out to every matching composite key — correctly
    propagating history to each product/section that offers the same option.

    Records with no cross-year match are retained as history-only entries.
    """
    tdp_records = [r for r in records
                   if r["product_type"] in ("Platform TDP", "Non-Platform TDP")]

    current_recs = [r for r in tdp_records if int(r["source_year"]) == current_year]
    hist_recs    = [r for r in tdp_records if int(r["source_year"]) != current_year]

    # ── Build option_id → set of current-year composite keys ─────────────────
    id_to_current_keys: dict[str, set[str]] = defaultdict(set)
    for rec in current_recs:
        opt_id = (rec.get("option_identifier") or "").strip()
        if opt_id:
            id_to_current_keys[opt_id].add(rec["join_key"])

    # ── Group current-year records by composite key ───────────────────────────
    # current_groups: join_key → list of same-year records (for dedup)
    current_groups: dict[str, list[dict]] = defaultdict(list)
    for rec in current_recs:
        current_groups[rec["join_key"]].append(rec)

    # ── Map each historical record to current-year join key(s) ───────────────
    # history_fan: composite_key → {year_str: pass_fail}
    history_fan: dict[str, dict[str, str]] = defaultdict(dict)
    # orphan_groups: join_key → by_year dict (no matching current-year entry)
    orphan_groups: dict[str, dict[int, dict]] = defaultdict(dict)
    log_entries = []

    for rec in hist_recs:
        yr = int(rec["source_year"])
        pass_fail = rec.get("pass_fail", "Unknown")
        opt_id = (rec.get("option_identifier") or "").strip()

        matched_keys = id_to_current_keys.get(opt_id, set()) if opt_id else set()

        if matched_keys:
            # Fan out history to all current-year products that use this option
            for ckey in matched_keys:
                existing = history_fan[ckey].get(str(yr))
                if existing and existing != pass_fail:
                    log_entries.append({
                        "type": "history_conflict",
                        "composite_key": ckey,
                        "option_identifier": opt_id,
                        "year": yr,
                        "kept": existing,
                        "discarded": pass_fail,
                    })
                else:
                    history_fan[ckey][str(yr)] = pass_fail
        else:
            # No current-year match — keep as history-only orphan
            jk = rec["join_key"]
            if yr not in orphan_groups[jk]:
                orphan_groups[jk][yr] = rec
            else:
                if orphan_groups[jk][yr].get("pass_fail") != pass_fail:
                    log_entries.append({
                        "type": "duplicate_conflict",
                        "join_key": jk,
                        "product_type": rec["product_type"],
                        "year": yr,
                        "kept": orphan_groups[jk][yr].get("pass_fail"),
                        "discarded": pass_fail,
                    })

    products = []

    # ── Build entries for current-year products ───────────────────────────────
    for join_key, recs in current_groups.items():
        # Deduplicate within current year
        current = recs[0]
        for rec in recs[1:]:
            if rec.get("pass_fail") != current.get("pass_fail"):
                log_entries.append({
                    "type": "duplicate_conflict",
                    "join_key": join_key,
                    "product_type": rec["product_type"],
                    "year": current_year,
                    "kept": current.get("pass_fail"),
                    "discarded": rec.get("pass_fail"),
                })

        history = {str(current_year): current.get("pass_fail", "Unknown")}
        history.update(history_fan.get(join_key, {}))

        entry: dict = {
            "product_name": current.get("product_name", ""),
            "investment_menu_name": current.get("investment_menu_name", ""),
            "investment_option_name": current.get("investment_option_name", ""),
            "product_type": current.get("product_type", ""),
            "current_metrics_available": True,
            "pass_fail_current": current.get("pass_fail"),
            "nir_10yr":     current.get("nir_10yr"),
            "nir_rag":      current.get("nir_rag", "Unknown"),
            "fees_50k":     current.get("fees_50k"),
            "fees_50k_rag": current.get("fees_50k_rag", "Unknown"),
            "fees_100k":    current.get("fees_100k"),
            "fees_100k_rag": current.get("fees_100k_rag", "Unknown"),
            "history": dict(sorted(history.items(), key=lambda x: x[0], reverse=True)),
        }
        products.append(entry)

    # ── Build entries for history-only orphans (no current-year match) ────────
    for join_key, by_year in orphan_groups.items():
        representative = next(iter(by_year.values()))
        history = {str(yr): rec.get("pass_fail", "Unknown") for yr, rec in by_year.items()}
        entry = {
            "product_name": representative.get("product_name", ""),
            "investment_menu_name": representative.get("investment_menu_name", ""),
            "investment_option_name": representative.get("investment_option_name", ""),
            "product_type": representative.get("product_type", ""),
            "current_metrics_available": False,
            "pass_fail_current": None,
            "nir_10yr": None, "nir_rag": None,
            "fees_50k": None, "fees_50k_rag": None,
            "fees_100k": None, "fees_100k_rag": None,
            "history": dict(sorted(history.items(), key=lambda x: x[0], reverse=True)),
        }
        products.append(entry)
        log_entries.append({
            "type": "history_only",
            "join_key": join_key,
            "product_type": representative.get("product_type"),
            "note": "No current year match via option_identifier",
        })

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
