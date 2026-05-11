# APRA Performance Data Loader — Pipeline Context

Use this document to carry pipeline state across sessions. Update it after each run.

---

## Pipeline Parameters

| Parameter | Value |
|-----------|-------|
| **Current year** | 2025 |
| **Last updated** | 2025-06 |
| **Base directory** | `C:\Users\alpes\.claude\Member Performance Data\outputs\apra-skills\` |
| **Download directory** | `apra_data\` |
| **Work directory** | `apra_work\` |
| **Output file** | `apra_work\performance-data.json` |
| **Excel output** | `apra_work\performance-data.xlsx` |
| **Fuzzy match threshold** | Levenshtein ≤ 2 (default) |

---

## Last Completed Run — 2025 (with full 2021–2025 history)

| Step | Script | Status | Key Output |
|------|--------|--------|-----------|
| 1A | apra_downloader.py `--mode current` | ✅ Complete | `apra_data\apra_manifest.json` (8 entries) |
| 1B | Manual manifest update | ✅ Complete | Historical files already on disk |
| 2 | apra_extractor.py | ✅ Complete | `apra_work\apra_extracted.json` (2,931 records) |
| 3 | apra_cleaner.py | ✅ Complete | `apra_work\apra_cleaned.json` (2,931 records) |
| 3 gate | Human review | ⏭ Skipped | 745 fuzzy pairs; gate skipped for routine run |
| 4 | apra_longitudinal.py | ✅ Complete | `apra_work\apra_longitudinal.json` |
| 5 | apra_json_writer.py | ✅ Complete | `apra_work\performance-data.json` (935 KB) |
| 6 | build_excel.py | ✅ Complete | `apra_work\performance-data.xlsx` |

---

## Files on Disk

### Downloaded xlsx files (`apra_data\`)

| File | Year | Type | Status |
|------|------|------|--------|
| `2025%20CPPP%20-%20MySuper.xlsx` | 2025 | MySuper | ✅ |
| `2025%20CPPP%20-%20Choice.xlsx` | 2025 | TDP | ✅ |
| `2024_CPPP_Combined.xlsx` | 2024 | MySuper + TDP | ✅ |
| `2023_CPPP_Combined.xlsx` | 2023 | MySuper + TDP | ✅ |
| `2022_CPPP_MySuper.xlsx` | 2022 | MySuper only | ✅ |
| `2021_CPPP_MySuper.xlsx` | 2021 | MySuper only | ✅ |

### Output files (`apra_work\`)

| File | Description | Size |
|------|-------------|------|
| `performance-data.json` | Final output for webapp | ~935 KB |
| `performance-data.xlsx` | Excel export (3 sheets) | dynamically generated |
| `performance-data-2025-backup.json` | Backup of prior run | — |
| `apra_extracted.json` | Raw extracted records | — |
| `apra_cleaned.json` | Cleaned records | — |
| `apra_longitudinal.json` | Longitudinal datasets | — |
| `apra_manifest.json` | Download manifest | 8 entries |
| `build_excel.py` | Excel builder script | — |

---

## Run Results Summary

### Step 2 — Extraction

| File | Year | Type | Records |
|------|------|------|---------|
| 2025 Choice (TDP) | 2025 | TDP | 882 |
| 2025 MySuper | 2025 | MySuper | 384 |
| 2024 Combined | 2024 | MySuper | 57 |
| 2024 Combined | 2024 | TDP | 590 |
| 2023 Combined | 2023 | MySuper | 64 |
| 2023 Combined | 2023 | TDP | 805 |
| 2022 MySuper | 2022 | MySuper | 69 |
| 2021 MySuper | 2021 | MySuper | 80 |
| **Total** | | | **2,931** |

RAG colour legend: empty (conditional formatting — Pass/Fail fallback applied).

### Step 3 — Cleaning

- Records cleaned: 2,931 (0 dropped)
- Fuzzy pairs: 745 (~511 requiring review — gate skipped)
- RAG fallback: applied (all RAG was Unknown)

### Step 4 — Longitudinal

- MySuper products: 127 (47 with current metrics, 80 history-only)
- TDP Platform: 1,706
- TDP Non-Platform: 0
- TDP history-only: 824
- MySuper history years: `['2025', '2024', '2023', '2022', '2021']`
- TDP history years: `['2025', '2024', '2023']`
- Duplicate conflicts: 287

### Step 5 — JSON Writer

- Output: `apra_work\performance-data.json`
- Backup: `apra_work\performance-data-2025-backup.json`
- File size: 934,662 bytes
- Total MySuper: 127 | Total TDP: 1,706

### Excel Output

- Sheets: Summary, MySuper Products (5 history year columns), TDP Options (3 history year columns)
- MySuper Pass/Fail columns: 2025, 2024, 2023, 2022, 2021
- TDP Pass/Fail columns: 2025, 2024, 2023

---

## Known Issues / Limitations

1. **TDP history does not link across years** — 2023/2024 TDP files lack `Product Name` and `Investment Menu Name` columns, so historical TDP join keys (`option_name||option_name`) don't match 2025 join keys (`product_name|menu|option_name`). TDP history columns will be mostly empty for current products.

2. **RAG colours unavailable** — APRA uses conditional formatting which openpyxl cannot read. All RAG fields are derived from Pass/Fail (Pass → Green, Fail → Red, Unknown → Unknown).

3. **`--mode historical` broken** — The APRA "previous results" landing page no longer hosts direct xlsx links. Historical files must be downloaded from per-year pages or are already on disk.

4. **MySuper record count lower than expected** — APRA's 2025 file lists 48 distinct products but the longitudinal builder shows 127 total (including history-only discontinued products from prior years).

---

## Session Notes

- 2026-03-30: First full run with 2021–2025 history. Extractor updated to handle historical sheet names, header row detection improved, COLUMN_ALIASES added for 2025 renames. Historical files downloaded manually from per-year APRA pages.
- Excel builder (`build_excel.py`) updated to dynamically generate one Pass/Fail column per history year.

---

## Python Package Setup (run once per session)

```bash
pip install requests beautifulsoup4 openpyxl python-Levenshtein --break-system-packages -q
```

---

## Skill Invocation Order (next run)

For a new year refresh (e.g., 2026):
1. Run `apra_downloader.py --mode current --year 2026` to download new current year files
2. Add new entries to `apra_manifest.json` (keep all existing historical entries)
3. Run Steps 2–5 (historical files already on disk — no re-download needed)
4. Run `build_excel.py` for the updated Excel file

_APRA Performance Data Loader — Pipeline Context v2.0_
_Last updated: 2026-03-30_
