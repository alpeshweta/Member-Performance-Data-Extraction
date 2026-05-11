---
name: apra-excel-extractor
description: >
  This skill should be used when the user wants to extract data from downloaded
  APRA CPPP Excel files. Opens each xlsx file using openpyxl, reads the Colour
  Legend sheet from current year files to build an RGB-to-label map, navigates
  to the correct product sheets using year-aware sheet name fallbacks, and
  extracts all required columns. Handles APRA's year-on-year column renames and
  sheet name changes automatically. Saves raw extracted records and the colour
  legend map for use by the apra-data-cleaner skill. Part of the APRA
  Performance Data Loader pipeline (Step 2).
metadata:
  author: Shweta Shah
  version: "2.0.0"
  workflow: APRA Performance Data Loader
  pipeline-step: "2"
---

# APRA Excel Extractor

Extracts raw data from APRA CPPP xlsx files using openpyxl, with automatic handling of year-on-year sheet name and column name changes.

## Before Running

Install required Python packages (run once per session):

```bash
pip install openpyxl --break-system-packages -q
```

## Run Command

```bash
PYTHONIOENCODING=utf-8 python "C:\Users\alpes\.claude\Member Performance Data\outputs\apra-skills\apra-excel-extractor\scripts\apra_extractor.py" --manifest "C:\Users\alpes\.claude\Member Performance Data\outputs\apra-skills\apra_data\apra_manifest.json" --out "C:\Users\alpes\.claude\Member Performance Data\outputs\apra-skills\apra_work"
```

---

## Sheet Name Handling

The extractor tries sheet names in order (newest naming first) and uses the first match found:

| Sheet type | Candidates tried (in order) |
|-----------|---------------------------|
| MySuper | `MySuper Products` (2025), `MySuper results` (2023–2024), `Performance test results` (2021–2022) |
| Non-Platform TDP | `Non-Platform TDPs` (2025), `Non-Platform TDP results` (2023–2024) |
| Platform TDP | `Platform TDPs` (2025), `Platform TDP results` (2023–2024) |

2021–2022 files contain MySuper only — no TDP sheets. This is expected and not an error.

---

## Column Name Aliases

APRA renames columns year-on-year. All known renames are registered in `COLUMN_ALIASES` in the script and resolved automatically during header parsing:

| Name found in file | Canonical name in code | Years |
|-------------------|----------------------|-------|
| `MySuper product name` | `RSE licensee MySuper product name` | 2021–2025 |
| `Pass/Fail indicator` (lowercase i) | `Pass/Fail Indicator` | 2025 |
| `Product name` (lowercase n) | `Product Name` | 2025 TDP |
| `Investment menu name` | `Investment Menu Name` | 2025 TDP |
| `Investment option name` | `Investment Option Name` | 2025 TDP |

**To add a new alias** (when APRA renames a column in a future year): add one line to `COLUMN_ALIASES` in `apra_extractor.py`:
```python
"New column name in file": "Canonical column name",
```

---

## Header Row Detection

The `build_col_index()` function:
- Scans rows 1–15 (not just rows 1–10) to handle files where headers are deep (e.g., 2025 TDP header is on row 5)
- Requires the candidate row to contain **at least one recognised column name** — this prevents group-heading rows (e.g. "Performance Test Metrics", "As at 30 June 2025") from being mistakenly selected
- Applies COLUMN_ALIASES before membership check
- Returns both the column index dict AND the header row number
- Extractors start data iteration from `header_row + 1` — the header text is never captured as a data record

---

## Historical TDP Extraction

2023–2024 TDP files lack `Product Name` and `Investment Menu Name` columns. The extractor automatically falls back to using `Investment Option Name` as the primary row identifier and logs:
```
[info] Non-Platform TDP results: no 'Product Name' column — using 'Investment Option Name' as product identifier.
```

This means historical TDP records have:
- `product_name` = investment option name
- `investment_menu_name` = empty
- `investment_option_name` = investment option name

As a result, historical TDP join keys are `option_name||option_name` (repeated), which does **not** match the 2025 join key of `product_name|menu_name|option_name`. TDP history therefore does not link back to 2025 TDP entries. This is a known structural limitation of the APRA data format.

**MySuper history is fully linked** (2021–2025) because product names are consistent across all years.

---

## RAG Colours

APRA uses conditional formatting (not cell fill colours) in recent files. The `Colour Legend` sheet is read when present, but as of 2025 all RAG values come back as `Unknown`. The Data Cleaner automatically applies the Pass/Fail fallback (Pass → Green, Fail → Red). This is expected behaviour.

---

## Expected Output (full 8-file run, 2021–2025)

| File | Year | Type | Records |
|------|------|------|---------|
| 2025 TDP (Choice) | 2025 | TDP | ~882 |
| 2025 MySuper | 2025 | MySuper | ~384 |
| 2024 Combined | 2024 | MySuper | ~57 |
| 2024 Combined | 2024 | TDP | ~590 |
| 2023 Combined | 2023 | MySuper | ~64 |
| 2023 Combined | 2023 | TDP | ~805 |
| 2022 MySuper | 2022 | MySuper | ~69 |
| 2021 MySuper | 2021 | MySuper | ~80 |
| **Total** | | | **~2,931** |

---

## Outputs

- `apra_work/apra_extracted.json` — all raw records
- `apra_work/apra_colour_legend.json` — RGB-to-label map (may be empty if conditional formatting used)
- `apra_work/apra_extraction_log.json` — per-file record counts and sheet processing log

## Failure Handling

- **Sheet not found:** The extractor tries all candidates in the fallback list, logs a warning for each miss, and continues. It does not abort.
- **0 records from a sheet that should have data:** Check actual sheet names using openpyxl; add the new name to the appropriate `_SHEET_NAMES` list in the script.
- **New column name not found:** Add to `COLUMN_ALIASES` in the script.
- **File in manifest not found on disk:** Skipped with a warning — does not abort the run.

## Guidelines

- Always process both Non-Platform and Platform TDP sheets from TDP/Choice files.
- Do not normalise or join records at this step — that is the Data Cleaner's job.
- The extractor reads every file with `data_only=True` to get calculated cell values, not formulas.
- Strip leading/trailing whitespace from all extracted string values.
