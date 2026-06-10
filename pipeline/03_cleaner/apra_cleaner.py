"""
APRA Data Cleaner
=================
Normalises and standardises extracted APRA CPPP records.
Applies colour legend mapping, parses numeric fields, and flags fuzzy match
candidates for human review.
Part of the APRA Performance Data Loader pipeline — Step 3.

Usage:
    python3 apra_cleaner.py --workdir ./apra_work --threshold 2
"""

import argparse
import json
import re
import sys
from pathlib import Path

import Levenshtein

NIR_COL    = "10 year Net Investment Return (NIR) p.a."
FEES_50_COL  = "Administration fees and costs charged ($50,000 account balance)"
FEES_100_COL = "Administration fees and costs charged ($100,000 account balance)"

RAG_COLS = [NIR_COL, FEES_50_COL, FEES_100_COL]

RAG_COL_KEYS = {
    NIR_COL:     "nir_rag",
    FEES_50_COL: "fees_50k_rag",
    FEES_100_COL:"fees_100k_rag",
}

NUMERIC_COL_KEYS = {
    NIR_COL:     "nir_10yr",
    FEES_50_COL: "fees_50k",
    FEES_100_COL:"fees_100k",
}


# ── Text normalisation ────────────────────────────────────────────────────────

def normalise_text(value) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).strip()).lower()


def title_case(value) -> str:
    """Standardise casing: title-case with common fund name rules."""
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value).strip())


def normalise_pass_fail(raw: str) -> str:
    val = str(raw or "").strip().lower()
    if val in ("pass", "p", "1", "true", "yes"):
        return "Pass"
    if val in ("fail", "f", "0", "false", "no"):
        return "Fail"
    return "Unknown"


# ── Numeric parsing ───────────────────────────────────────────────────────────

def parse_numeric(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    # Replace common non-numeric markers with null
    if text in ("N/A", "n/a", "--", "-", "*", "", "N/A*"):
        return None
    # Strip currency symbols, percentage signs, commas
    cleaned = re.sub(r"[$%,\s]", "", text)
    try:
        return float(cleaned)
    except ValueError:
        return None


# ── RAG mapping ───────────────────────────────────────────────────────────────

def apply_rag(rec: dict, colour_legend: dict, pass_fail: str, rag_all_unknown: bool) -> dict:
    """Apply colour legend to RAG columns. Fall back to Pass/Fail if all Unknown."""
    for col_name, out_key in RAG_COL_KEYS.items():
        rgb_key = col_name + "_rag_rgb"
        raw_rag = rec.get(col_name + "_rag", "Unknown")
        rgb = rec.get(rgb_key, "")

        if raw_rag != "Unknown":
            rec[out_key] = raw_rag
        elif rgb and colour_legend.get(rgb):
            rec[out_key] = colour_legend[rgb]
        elif rag_all_unknown:
            # Fallback: derive from Pass/Fail
            rec[out_key] = "Green" if pass_fail == "Pass" else "Red"
        else:
            rec[out_key] = "Unknown"

    return rec


# ── Join key builders ─────────────────────────────────────────────────────────

def mysuper_join_key(rec: dict) -> str:
    return title_case(rec.get("product_name", ""))


def tdp_join_key(rec: dict) -> str:
    # Always use the composite name key as the join key.
    # This preserves 2025's full product/menu/option granularity.
    # Cross-year linking via option_identifier is handled in the longitudinal builder.
    parts = [
        title_case(rec.get("product_name", "")),
        title_case(rec.get("investment_menu_name", "")),
        title_case(rec.get("investment_option_name", "")),
    ]
    return "|".join(parts)


# ── Fuzzy matching ────────────────────────────────────────────────────────────

def find_fuzzy_pairs(keys: list[str], threshold: int) -> list[dict]:
    """Find pairs of join keys with Levenshtein distance 1 to threshold."""
    flags = []
    unique_keys = list(set(keys))
    seen = set()

    for i, k1 in enumerate(unique_keys):
        for k2 in unique_keys[i + 1:]:
            pair = tuple(sorted([k1, k2]))
            if pair in seen:
                continue
            dist = Levenshtein.distance(k1.lower(), k2.lower())
            if 0 < dist <= threshold:
                seen.add(pair)
                flags.append({
                    "key_a": k1,
                    "key_b": k2,
                    "distance": dist,
                    "suggested_canonical": k1,  # default to first; user can override
                    "action": "review_needed" if dist == threshold else "auto_accepted",
                })

    return sorted(flags, key=lambda x: x["distance"])


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="APRA data cleaner")
    parser.add_argument("--workdir", default="./apra_work")
    parser.add_argument("--threshold", type=int, default=2)
    args = parser.parse_args()

    workdir = Path(args.workdir)
    extracted_path = workdir / "apra_extracted.json"
    legend_path = workdir / "apra_colour_legend.json"

    if not extracted_path.exists():
        print(f"ERROR: {extracted_path} not found. Run apra_extractor.py first.", file=sys.stderr)
        return 1

    records = json.loads(extracted_path.read_text(encoding="utf-8"))
    colour_legend = {}
    if legend_path.exists():
        colour_legend = json.loads(legend_path.read_text(encoding="utf-8"))
        print(f"[setup] Colour legend loaded: {len(colour_legend)} entries")
    else:
        print("[warn] No colour legend file found. RAG will be derived from Pass/Fail.")

    print(f"[setup] Records to clean: {len(records)}")

    # Detect if RAG is all Unknown (conditional formatting scenario)
    current_records = [r for r in records if r.get("is_current_year")]
    rag_all_unknown = (
        len(current_records) > 0 and
        all(r.get(NIR_COL + "_rag", "Unknown") == "Unknown" for r in current_records)
    )
    if rag_all_unknown:
        print("[warn] All RAG values are Unknown. Applying Pass/Fail fallback.")

    cleaned = []
    null_counts = {}

    for rec in records:
        is_current = rec.get("is_current_year", False)
        source_type = rec.get("product_type", "Unknown")

        # Build join key
        if source_type == "MySuper":
            join_key = mysuper_join_key(rec)
        else:
            join_key = tdp_join_key(rec)

        if not join_key.strip("|").strip():
            print(f"[skip] Empty join key in {rec.get('source_file')} year {rec.get('source_year')}")
            continue

        # Normalise Pass/Fail
        pass_fail = normalise_pass_fail(rec.get("pass_fail_raw", ""))

        out = {
            "join_key": join_key,
            "product_name": title_case(rec.get("product_name", "")),
            "product_type": source_type,
            "source_year": rec.get("source_year"),
            "source_file": rec.get("source_file"),
            "is_current_year": is_current,
            "pass_fail": pass_fail,
            "fuzzy_flag": False,
        }

        if source_type != "MySuper":
            out["investment_menu_name"] = title_case(rec.get("investment_menu_name", ""))
            out["investment_option_name"] = title_case(rec.get("investment_option_name", ""))
            if rec.get("option_identifier"):
                out["option_identifier"] = rec["option_identifier"]

        if is_current:
            # Numeric fields
            for col_name, out_key in NUMERIC_COL_KEYS.items():
                val = parse_numeric(rec.get(col_name))
                out[out_key] = val
                if val is None:
                    null_counts[out_key] = null_counts.get(out_key, 0) + 1

            # RAG
            out = apply_rag({**out, **rec}, colour_legend, pass_fail, rag_all_unknown)
            # Clean up raw RAG fields
            for col_name in RAG_COLS:
                out.pop(col_name, None)
                out.pop(col_name + "_rag", None)
                out.pop(col_name + "_rag_rgb", None)

        cleaned.append(out)

    print(f"[clean] {len(cleaned)} records after cleaning (dropped {len(records) - len(cleaned)} empty keys).")

    # Fuzzy matching — per product type
    fuzzy_flags = []

    for pt in ("MySuper", "Platform TDP", "Non-Platform TDP"):
        keys_by_year = {}
        for r in cleaned:
            if r["product_type"] == pt:
                yr = r["source_year"]
                keys_by_year.setdefault(yr, []).append(r["join_key"])

        all_keys = [k for keys in keys_by_year.values() for k in keys]
        flags = find_fuzzy_pairs(all_keys, args.threshold)
        for f in flags:
            f["product_type"] = pt
        fuzzy_flags.extend(flags)

    print(f"[fuzzy] {len(fuzzy_flags)} fuzzy pairs found (threshold ≤ {args.threshold}).")
    review_needed = [f for f in fuzzy_flags if f["action"] == "review_needed"]
    print(f"[fuzzy] {len(review_needed)} pairs require human review.")

    # RAG distribution (current year)
    rag_dist = {}
    for r in cleaned:
        if r.get("is_current_year"):
            for key in ("nir_rag", "fees_50k_rag", "fees_100k_rag"):
                val = r.get(key, "Unknown")
                rag_dist[key] = rag_dist.get(key, {})
                rag_dist[key][val] = rag_dist[key].get(val, 0) + 1

    # Save outputs
    cleaned_path = workdir / "apra_cleaned.json"
    flags_path = workdir / "apra_fuzzy_flags.json"
    log_path = workdir / "apra_cleaning_log.json"

    cleaned_path.write_text(json.dumps(cleaned, indent=2, default=str), encoding="utf-8")
    flags_path.write_text(json.dumps(fuzzy_flags, indent=2, default=str), encoding="utf-8")

    log = {
        "total_input_records": len(records),
        "total_cleaned_records": len(cleaned),
        "records_dropped": len(records) - len(cleaned),
        "rag_all_unknown_fallback_applied": rag_all_unknown,
        "null_field_counts": null_counts,
        "rag_distribution": rag_dist,
        "fuzzy_pairs_found": len(fuzzy_flags),
        "fuzzy_pairs_review_needed": len(review_needed),
    }
    log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")

    print(f"\n{'=' * 50}")
    print(f"APRA Data Cleaner — Complete")
    print(f"  Cleaned records     : {len(cleaned)}")
    print(f"  Fuzzy pairs flagged : {len(fuzzy_flags)}")
    print(f"  Review needed       : {len(review_needed)}")
    print(f"  Cleaned JSON        : {cleaned_path}")
    print(f"  Fuzzy flags         : {flags_path}")
    print(f"  Cleaning log        : {log_path}")
    print(f"{'=' * 50}")
    print("\n⚠️  HUMAN GATE: Review apra_fuzzy_flags.json before running apra_longitudinal.py.")
    print("   Accept, reject, or override each flagged pair, then run apra_longitudinal.py.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
