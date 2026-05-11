"""
APRA JSON Writer
================
Serialises unified APRA CPPP longitudinal datasets into the final
performance-data.json file for the Benchmark Tracker webapp.

Part of the APRA Performance Data Loader pipeline — Step 5.

Usage:
    python3 apra_json_writer.py \
        --workdir ./apra_work \
        --outdir ./webapp/data \
        --year 2025 \
        --updated "2025-06"
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="APRA JSON output writer")
    parser.add_argument("--workdir", default="./apra_work", help="Work directory with apra_longitudinal.json")
    parser.add_argument("--outdir", required=True, help="Output directory for performance-data.json")
    parser.add_argument("--year", type=int, required=True, help="Current year (e.g., 2025)")
    parser.add_argument("--updated", required=True, help="last_updated value e.g. '2025-06'")
    args = parser.parse_args()

    workdir = Path(args.workdir)
    outdir = Path(args.outdir)
    longitudinal_path = workdir / "apra_longitudinal.json"

    # ── Load longitudinal data ────────────────────────────────────────────────

    if not longitudinal_path.exists():
        print(f"ERROR: {longitudinal_path} not found. Run apra_longitudinal.py first.", file=sys.stderr)
        return 1

    longitudinal = json.loads(longitudinal_path.read_text(encoding="utf-8"))
    mysuper_products = longitudinal["mysuper_products"]
    tdp_products = longitudinal["tdp_products"]
    build_summary = longitudinal.get("build_summary", {})

    # ── Derive metadata ───────────────────────────────────────────────────────

    source_years_mysuper = sorted(
        {yr for p in mysuper_products for yr in p.get("history", {}).keys()},
        reverse=True,
    )
    source_years_tdp = sorted(
        {yr for p in tdp_products for yr in p.get("history", {}).keys()},
        reverse=True,
    )

    total_mysuper = len(mysuper_products)
    total_tdp = len(tdp_products)

    print(f"[setup] MySuper products : {total_mysuper}")
    print(f"[setup] TDP options      : {total_tdp}")
    print(f"[setup] MySuper years    : {source_years_mysuper}")
    print(f"[setup] TDP years        : {source_years_tdp}")

    # ── Ensure output directory exists ────────────────────────────────────────

    outdir.mkdir(parents=True, exist_ok=True)
    output_path = outdir / "performance-data.json"
    backup_path = outdir / f"performance-data-{args.year}-backup.json"

    # ── Archive existing file ─────────────────────────────────────────────────

    if output_path.exists():
        print(f"[backup] Archiving existing file → {backup_path}")
        backup_path.write_bytes(output_path.read_bytes())
        print(f"[backup] Archived successfully.")

    # ── Build output object ───────────────────────────────────────────────────

    output = {
        "last_updated": args.updated,
        "source_years_mysuper": source_years_mysuper,
        "source_years_tdp": source_years_tdp,
        "total_mysuper_products": total_mysuper,
        "total_tdp_options": total_tdp,
        "mysuper_products": mysuper_products,
        "tdp_products": tdp_products,
    }

    # ── Serialise and write ───────────────────────────────────────────────────

    print(f"[write] Serialising to JSON...")
    try:
        json_str = json.dumps(output, indent=2, ensure_ascii=False, default=str)
    except Exception as exc:
        print(f"ERROR: JSON serialisation failed: {exc}", file=sys.stderr)
        print("  The backup file (if created) remains intact.", file=sys.stderr)
        return 1

    print(f"[write] Writing {output_path}...")
    try:
        output_path.write_text(json_str, encoding="utf-8")
    except Exception as exc:
        print(f"ERROR: File write failed: {exc}", file=sys.stderr)
        print("  The backup file (if created) remains intact.", file=sys.stderr)
        return 1

    # ── Validate: read back first lines ──────────────────────────────────────

    try:
        first_lines = output_path.read_text(encoding="utf-8", errors="replace")[:500]
        if not first_lines.strip().startswith("{"):
            print("ERROR: Output file does not start with '{' — likely corrupt.", file=sys.stderr)
            return 1
        print(f"[validate] File starts correctly.")
    except Exception as exc:
        print(f"[warn] Could not validate output file: {exc}")

    # ── Write log ─────────────────────────────────────────────────────────────

    write_log = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "output_file": str(output_path),
        "backup_file": str(backup_path) if (outdir / f"performance-data-{args.year}-backup.json").exists() else None,
        "last_updated": args.updated,
        "current_year": args.year,
        "total_mysuper_products": total_mysuper,
        "total_tdp_options": total_tdp,
        "source_years_mysuper": source_years_mysuper,
        "source_years_tdp": source_years_tdp,
        "file_size_bytes": output_path.stat().st_size,
    }

    log_path = workdir / "apra_write_log.json"
    log_path.write_text(json.dumps(write_log, indent=2, default=str), encoding="utf-8")

    print(f"\n{'=' * 50}")
    print(f"APRA JSON Writer — Complete")
    print(f"  Output file          : {output_path}")
    print(f"  File size            : {write_log['file_size_bytes']:,} bytes")
    print(f"  Total MySuper        : {total_mysuper}")
    print(f"  Total TDP            : {total_tdp}")
    print(f"  Source years MySuper : {source_years_mysuper}")
    print(f"  Source years TDP     : {source_years_tdp}")
    print(f"  Write log            : {log_path}")
    print(f"{'=' * 50}")
    print(f"\n✅ performance-data.json is ready for the Benchmark Tracker webapp.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
