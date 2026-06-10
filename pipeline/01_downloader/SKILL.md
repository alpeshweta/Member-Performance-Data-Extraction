---
name: apra-file-downloader
description: >
  This skill should be used when the user wants to download APRA CPPP
  (Comprehensive Product Performance and Pricing) Excel files from the APRA
  website. Downloads current year MySuper and TDP files and manages the
  download manifest for use by the apra-excel-extractor skill.
  Part of the APRA Performance Data Loader pipeline (Step 1A and 1B).
metadata:
  author: Shweta Shah
  version: "2.0.0"
  workflow: APRA Performance Data Loader
  pipeline-step: "1A + 1B"
---

# APRA File Downloader

Downloads current year and historical APRA CPPP Excel files and produces a download manifest.

## ⚠️ Important: Historical Download Approach (Updated 2026)

**APRA's "previous performance test results" page no longer hosts direct `.xlsx` links.**
The `--mode historical` flag on the downloader returns 0 files. **Do not use it.**

Historical files must be downloaded from individual per-year pages and added to the manifest manually. All historical files from 2021–2024 are **already stored locally** at:

```
C:\Users\alpes\.claude\Member Performance Data\outputs\apra-skills\apra_data\
```

| File | Year | Contains |
|------|------|---------|
| `2024_CPPP_Combined.xlsx` | 2024 | MySuper + TDP (one file) |
| `2023_CPPP_Combined.xlsx` | 2023 | MySuper + TDP (one file) |
| `2022_CPPP_MySuper.xlsx`  | 2022 | MySuper only |
| `2021_CPPP_MySuper.xlsx`  | 2021 | MySuper only |
| `2025%20CPPP%20-%20MySuper.xlsx` | 2025 | MySuper (current year) |
| `2025%20CPPP%20-%20Choice.xlsx`  | 2025 | TDP/Choice (current year) |

---

## Before Running

Install required Python packages (run once per session):

```bash
pip install requests beautifulsoup4 --break-system-packages -q
```

---

## Workflow

### Step 1A — Download Current Year Files

For the current year (e.g., 2025), run:

```bash
PYTHONIOENCODING=utf-8 python "C:\Users\alpes\.claude\Member Performance Data\outputs\apra-skills\apra-file-downloader\scripts\apra_downloader.py" --mode current --year YYYY --dir "C:\Users\alpes\.claude\Member Performance Data\outputs\apra-skills\apra_data"
```

This scrapes the APRA page for the current year and downloads the MySuper and TDP xlsx files.

**Current year page URLs:**
- MySuper: `https://www.apra.gov.au/YYYY-annual-superannuation-performance-test-mysuper-products`
- TDP: `https://www.apra.gov.au/YYYY-annual-superannuation-performance-test-trustee-directed-products`

### Step 1B — Add Historical Files to Manifest

Historical files are already on disk. After running Step 1A, update `apra_manifest.json` to include all historical entries. The manifest must have **8 entries** for a full 2021–2025 run:

```json
[
  { "product_type": "MySuper", "year": 2025, "file_name": "2025%20CPPP%20-%20MySuper.xlsx",
    "file_path": "C:\\...\\apra_data\\2025%20CPPP%20-%20MySuper.xlsx", "is_current_year": true,  "status": "downloaded" },
  { "product_type": "TDP",     "year": 2025, "file_name": "2025%20CPPP%20-%20Choice.xlsx",
    "file_path": "C:\\...\\apra_data\\2025%20CPPP%20-%20Choice.xlsx",  "is_current_year": true,  "status": "downloaded" },
  { "product_type": "MySuper", "year": 2024, "file_name": "2024_CPPP_Combined.xlsx",
    "file_path": "C:\\...\\apra_data\\2024_CPPP_Combined.xlsx", "is_current_year": false, "status": "downloaded" },
  { "product_type": "TDP",     "year": 2024, "file_name": "2024_CPPP_Combined.xlsx",
    "file_path": "C:\\...\\apra_data\\2024_CPPP_Combined.xlsx", "is_current_year": false, "status": "downloaded" },
  { "product_type": "MySuper", "year": 2023, "file_name": "2023_CPPP_Combined.xlsx",
    "file_path": "C:\\...\\apra_data\\2023_CPPP_Combined.xlsx", "is_current_year": false, "status": "downloaded" },
  { "product_type": "TDP",     "year": 2023, "file_name": "2023_CPPP_Combined.xlsx",
    "file_path": "C:\\...\\apra_data\\2023_CPPP_Combined.xlsx", "is_current_year": false, "status": "downloaded" },
  { "product_type": "MySuper", "year": 2022, "file_name": "2022_CPPP_MySuper.xlsx",
    "file_path": "C:\\...\\apra_data\\2022_CPPP_MySuper.xlsx",  "is_current_year": false, "status": "downloaded" },
  { "product_type": "MySuper", "year": 2021, "file_name": "2021_CPPP_MySuper.xlsx",
    "file_path": "C:\\...\\apra_data\\2021_CPPP_MySuper.xlsx",  "is_current_year": false, "status": "downloaded" }
]
```

**Key rule:** Combined files (2023, 2024) need **two manifest entries** — one for `MySuper` and one for `TDP` — both pointing to the same `file_path`. The extractor uses `product_type` to decide which sheets to open.

### Re-downloading a Missing Historical File

If a historical file is missing from disk, download it from the source URL:

| Year | xlsx URL |
|------|---------|
| 2024 | `https://www.apra.gov.au/sites/default/files/2024-09/30August2024%20-%20Annual%20superannuation%20performance%20test%20results%20-%20August%202024.xlsx` |
| 2023 | `https://www.apra.gov.au/sites/default/files/2023-08/Annual%20superannuation%20performance%20test%20results%20-%20August%202023.xlsx` |
| 2022 | `https://www.apra.gov.au/sites/default/files/2022-08/Performance%20Test%202021-22%20Results.xlsx` |
| 2021 | `https://www.apra.gov.au/sites/default/files/2021-09/MySuper%20Performance%20Test%20results.xlsx` |

Save as the standard filenames listed above. If APRA has moved the file, navigate to the per-year landing page to find the new URL:
- 2024: `https://www.apra.gov.au/2024-annual-superannuation-performance-test-mysuper-products`
- 2023: `https://www.apra.gov.au/2023-annual-superannuation-performance-test-mysuper-products`
- 2022: `https://www.apra.gov.au/annual-superannuation-performance-test-2022`
- 2021: `https://www.apra.gov.au/your-future-your-super-performance-test-2021`

---

## File Structure by Year

| Year | File format | MySuper sheet | TDP Non-Platform sheet | TDP Platform sheet |
|------|------------|--------------|----------------------|-------------------|
| 2025 | Separate files | `MySuper Products` | `Non-Platform TDPs` | `Platform TDPs` |
| 2023–2024 | Combined (one file) | `MySuper results` | `Non-Platform TDP results` | `Platform TDP results` |
| 2021–2022 | Single file, MySuper only | `Performance test results` | _(not present)_ | _(not present)_ |

---

## Outputs

### `apra_data/apra_manifest.json`

Array of entries as shown above. The extractor reads only entries with `"status": "downloaded"`.

---

## Failure Handling

- **404 on current year page:** APRA has not yet published data for that year (published June–December). Report to user.
- **`--mode historical` returns 0 files:** Known — APRA changed their site structure. Use the per-year URLs above or confirm files are already on disk.
- **Network connection reset:** APRA's server sometimes resets connections. Retry with a short delay (3–5 seconds between requests).
- **Combined file has unexpected sheets:** Check actual sheetnames with openpyxl before adding manifest entries. Adjust `product_type` entries accordingly.

## Guidelines

- TDP performance testing began in 2023 — do not expect TDP sheets in 2021–2022 files.
- Always verify the manifest has the correct number of entries before proceeding to Step 2.
- After a new year's files are added, historical files already on disk do **not** need to be re-downloaded — only new current year files need downloading.
