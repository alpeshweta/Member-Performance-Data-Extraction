# APRA Member Performance Data Extraction Pipeline

**Author:** Shweta Shah — Senior Product Manager, Investment & Financial Data & Regulatory Solutions  
**Completed:** April–May 2026 (Maven Course Training Project)  
**Regulatory Domain:** YFYS Performance Test · APRA CPPP · MySuper & Trustee Directed Products (TDP)

---

## Overview

This repository contains a complete, end-to-end data engineering pipeline built to extract, clean, and structure five years of public superannuation performance data published annually by the **Australian Prudential Regulation Authority (APRA)**.

The pipeline processes APRA's **Comprehensive Product Performance Publications (CPPP)** — the annual results of the *Your Future, Your Super (YFYS)* performance test — for both **MySuper** and **Trustee Directed Product (TDP)** cohorts, spanning **2021 to 2025**.

The final output (`outputs/performance-data.json`) is a structured, webapp-ready dataset containing:
- Current year metrics for 127 MySuper products and 1,706 TDP investment options
- Historical pass/fail records per product across all available years
- Net Investment Return (NIR), fee data, and RAG performance indicators

  https://github.com/alpeshweta/Member-Fund-Webapp

---

## Why This Project Exists

In the Australian superannuation industry, the YFYS performance test determines whether a product can remain open to new members. A fund that fails twice in a row must close to new members by law. This dataset powers:

- **Investment Option Benchmark Tracker** — a member-facing lookup tool for comparing fund performance
- **YFYS Risk Simulator** — a scenario modelling tool for advisers and member communications teams

This project demonstrates how a product manager with regulatory domain knowledge can design, specify, and build a production-quality data pipeline using modern AI-assisted development tooling.

---

## Skills Demonstrated

| Skill | Evidence |
|---|---|
| Regulatory data fluency | Deep knowledge of APRA CPPP schema, YFYS test mechanics, and product taxonomy |
| Data pipeline design | 5-step pipeline with parallel download, extraction, cleaning, longitudinal joining, and serialisation |
| Python scripting | `openpyxl`-based Excel extraction; fuzzy matching with Levenshtein distance; JSON serialisation |
| AI-assisted development | Each pipeline step designed as a reusable AI skill (see `pipeline/*/SKILL.md`) using the Business-First AI framework |
| Data quality engineering | Fuzzy matching across 2,931 records; RAG fallback logic; conditional formatting extraction; structured audit logs |
| Documentation | Workflow definition, building block spec, pipeline context, and per-skill documentation |
| Product thinking | End-to-end ownership from regulatory source to webapp-ready JSON — with clear failure modes and refresh instructions |

---

## Repository Structure

```
Member-Performance-Data-Extraction/
│
├── README.md                        ← This file
│
├── data/
│   └── raw/                         ← Source APRA CPPP Excel files (2021–2025)
│       ├── 2021_CPPP_MySuper.xlsx
│       ├── 2022_CPPP_MySuper.xlsx
│       ├── 2023_CPPP_Combined.xlsx
│       ├── 2024_CPPP_Combined.xlsx
│       ├── 2025_CPPP_Choice.xlsx
│       └── 2025_CPPP_MySuper.xlsx
│
├── pipeline/                        ← 5-step modular pipeline
│   ├── 01_downloader/               ← Downloads current & historical APRA files
│   ├── 02_extractor/                ← Extracts records from each xlsx (openpyxl)
│   ├── 03_cleaner/                  ← Normalises, fuzzy-matches, applies RAG logic
│   ├── 04_longitudinal_builder/     ← Joins records across years per product
│   └── 05_json_writer/              ← Serialises unified datasets to JSON
│       (Each folder contains: SKILL.md — the AI skill spec + Python script)
│
├── scripts/
│   └── build_excel.py               ← Generates the 3-sheet Excel export
│
├── outputs/                         ← Pipeline outputs from the completed 2025 run
│   ├── performance-data.json        ← Final output: 127 MySuper + 1,706 TDP records
│   ├── performance-data.xlsx        ← Excel export (Summary, MySuper, TDP sheets)
│   ├── apra_extracted.json          ← Raw extracted records (2,931)
│   ├── apra_cleaned.json            ← Cleaned and normalised records
│   ├── apra_longitudinal.json       ← Longitudinal datasets (pre-serialisation)
│   └── logs/                        ← Structured audit logs per pipeline step
│       ├── apra_extraction_log.json
│       ├── apra_cleaning_log.json
│       ├── apra_longitudinal_log.json
│       ├── apra_fuzzy_flags.json    ← 745 fuzzy-matched pairs flagged for review
│       └── apra_write_log.json
│
├── metadata/
│   ├── apra_manifest.json           ← Download manifest (8 source files)
│   └── apra_colour_legend.json      ← APRA RAG colour-to-label mapping
│
└── docs/
    ├── pipeline-context.md          ← Run log, file inventory, known issues
    ├── workflow-definition.md       ← Full step-by-step workflow spec (Business-First AI)
    └── building-block-spec.md       ← AI building block architecture specification
```

---

## Pipeline Summary

The pipeline runs in five sequential steps (Steps 1A and 1B can run in parallel):

```
Step 1A: Download current year APRA files (MySuper + TDP)  ──┐
                                                               ├──► Step 2: Extract ──► Step 3: Clean ──► Step 4: Longitudinal join ──► Step 5: Write JSON
Step 1B: Download historical APRA files (2021–2024)        ──┘
```

| Step | Script | Records In | Records Out |
|---|---|---|---|
| 1A/1B | `apra_downloader.py` | — | 6 xlsx files |
| 2 | `apra_extractor.py` | 6 xlsx files | 2,931 raw records |
| 3 | `apra_cleaner.py` | 2,931 records | 2,931 cleaned records |
| 4 | `apra_longitudinal.py` | 2,931 cleaned | 127 MySuper + 1,706 TDP unified |
| 5 | `apra_json_writer.py` | Unified datasets | `performance-data.json` (935 KB) |
| 6 | `build_excel.py` | JSON output | `performance-data.xlsx` (3 sheets) |

---

## Run Results (2025 Full Run — March 2026)

| Metric | Value |
|---|---|
| Source files processed | 6 (2021–2025, MySuper + TDP) |
| Total records extracted | 2,931 |
| Fuzzy match pairs flagged | 745 |
| Final MySuper products | 127 (including 80 history-only discontinued products) |
| Final TDP investment options | 1,706 (including 824 history-only) |
| Output file size | 935 KB |
| MySuper history span | 2021–2025 |
| TDP history span | 2023–2025 (TDP testing commenced 2023) |

---

## How to Run the Pipeline

### Prerequisites

```bash
pip install requests beautifulsoup4 openpyxl python-Levenshtein
```

### Annual Refresh (e.g., adding 2026 data)

```bash
# Step 1: Download new current year files
python pipeline/01_downloader/apra_downloader.py --mode current --year 2026

# Step 2: Extract all files (historical already on disk)
python pipeline/02_extractor/apra_extractor.py

# Step 3: Clean and normalise
python pipeline/03_cleaner/apra_cleaner.py

# Step 4: Build longitudinal datasets
python pipeline/04_longitudinal_builder/apra_longitudinal.py

# Step 5: Write JSON output
python pipeline/05_json_writer/apra_json_writer.py

# Step 6: Generate Excel export
python scripts/build_excel.py
```

---

## Known Limitations

1. **TDP history is sparse before 2023** — APRA's TDP testing only commenced in 2023; no historical files exist for 2021–2022.
2. **RAG colours use conditional formatting** — APRA's Excel files apply colours via conditional formatting rules rather than direct cell fills. The pipeline derives RAG from Pass/Fail where direct fill extraction fails.
3. **Historical TDP linking is partial** — 2023/2024 TDP files use different column structures to 2025, which limits cross-year join accuracy for TDP records.
4. **`--mode historical` requires manual download** — APRA's historical results page no longer hosts direct `.xlsx` links; historical files are already included in `data/raw/`.

---

## Documentation

| Document | Purpose |
|---|---|
| [`docs/pipeline-context.md`](docs/pipeline-context.md) | Live run log, file inventory, parameters, and session notes |
| [`docs/workflow-definition.md`](docs/workflow-definition.md) | Detailed workflow specification including all decision points and failure modes |
| [`docs/building-block-spec.md`](docs/building-block-spec.md) | AI-assisted architecture spec mapping pipeline steps to reusable building blocks |
| `pipeline/*/SKILL.md` | Per-step AI skill specifications (prompt + schema + invocation guide) |

---

## Data Source

All source data is published by the **Australian Prudential Regulation Authority (APRA)** under the [APRA Open Data Policy](https://www.apra.gov.au/open-data).  
CPPP publications: [https://www.apra.gov.au/annual-superannuation-performance-test](https://www.apra.gov.au/annual-superannuation-performance-test)

---

*Built as part of a Maven AI for Product Managers training course — demonstrating end-to-end AI-assisted data pipeline design for regulatory financial data.*
