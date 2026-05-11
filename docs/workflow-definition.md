# Workflow Definition: APRA Performance Data Loader

**Author:** Shweta Shah — Senior Product Manager, Investment & Financial Data & Regulatory Solutions
**Date:** 2026-03-20
**Framework:** Business-First AI — Step 2: Deconstruct (Output)
**Feeds into:** Investment Option Benchmark Tracker (Use Case 4) · YFYS Risk Simulator (Use Case 9)

---

## Scenario Metadata

| Field | Value |
|---|---|
| **Workflow Name** | APRA Performance Data Loader |
| **Description** | Downloads, parses, and stores APRA CPPP data for both MySuper and TDP (Trustee Directed) products — current year and all available historical files — into a structured JSON dataset ready for member-facing lookup in the Benchmark Tracker webapp |
| **Process Outcome** | A clean, queryable `performance-data.json` file containing per-product current year metrics (10yr NIR, fees, RAG status, pass/fail) and historical pass/fail records for both MySuper and TDP product types |
| **Trigger** | APRA publishes new annual CPPP data (June each year, available through December) — or developer initiates a manual data refresh |
| **Type** | Deterministic |
| **Lens** | Individual |
| **Business Objective** | Establish the complete public data foundation for the Investment Option Benchmark Tracker and YFYS Risk Simulator — covering both MySuper and TDP product cohorts under the YFYS Performance Test |
| **Current Owner** | Shweta Shah (developer / data owner during Maven course build, Apr–May 2026) |
| **Regulatory Tie-in** | YFYS Performance Test — APRA's annual assessment of MySuper and TDP products against SAA benchmarks; failure triggers mandatory member notification and eventual product closure to new members. In 2025: 563 MySuper products tested; 7 platform TDPs failed; 25 products in the danger zone |

---

## Refined Steps

### Step 1A — Download Current Year Files (MySuper + TDP)

**Action:** For the current year, construct both APRA page URLs, scrape each page to locate the CPPP Excel download links, and fetch both files.

**Sub-steps:**
1. Determine current year (accept as parameter or derive from system date)
2. MySuper file:
   - Construct URL: `https://www.apra.gov.au/YYYY-annual-superannuation-performance-test-mysuper-products`
   - Scrape page to find `.xlsx` link matching `YYYY CPP-MySuper`
   - Download to local working directory
3. TDP/Choice file:
   - Construct URL: `https://www.apra.gov.au/YYYY-annual-superannuation-performance-test-trustee-directed-products`
   - Scrape page to find `.xlsx` link matching `YYYY CPPP - Choice`
   - Download to local working directory

**Decision points:**
- If either page returns 404 → APRA has not yet published data; abort that file with message: `"CPPP [MySuper/TDP] data not yet available for YYYY. Published June–December annually."`
- If multiple `.xlsx` links found on a page → select the one matching the exact naming pattern
- Files are independent — if one fails, continue with the other and flag the failure

| | |
|---|---|
| **Data in** | Current year (integer) |
| **Data out** | `YYYY_CPP_MySuper.xlsx` and `YYYY_CPPP_Choice.xlsx` saved locally |

**Failure modes:**
- APRA changes URL structure for either product type → download fails; validation check needed post-fetch
- File not yet published (before June) → clear error message returned
- Page exists but file link renamed → no match found, requires manual intervention

---

### Step 1B — Download Historical Files (MySuper + TDP) *(runs in parallel with 1A)*

**Action:** Navigate to the APRA historical results page, identify all available files for both MySuper and TDP product types, and download any years not already stored locally.

**Historical URL:** `https://www.apra.gov.au/previous-performance-test-results`

**Sub-steps:**
1. Navigate to the historical results page
2. Scrape page to find all `.xlsx` links and classify by naming pattern:

| Year range | Product type | File naming pattern |
|---|---|---|
| 2023+ | MySuper | `YYYY-annual-superannuation-performance-test-mysuper-products` |
| 2023+ | TDP | `YYYY-annual-superannuation-performance-test-trustee-directed-products` |
| 2021–2022 | MySuper only | `YYYY Annual Superannuation Performance Test` |

3. Compare against already-downloaded files; skip years already stored
4. Download all missing files to local working directory

**Decision points:**
- First-time load → download all available files across both product types and all years
- Annual refresh → skip already-downloaded files; only Step 1A needed for the new year
- 2021 and 2022 files contain MySuper data only — do NOT expect or create TDP history for those years
- If a historical file is unavailable → log warning, continue with remaining files

| | |
|---|---|
| **Data in** | List of already-downloaded historical files (for incremental refresh logic) |
| **Data out** | Historical `.xlsx` files per year per product type |

**Failure modes:**
- APRA restructures the historical results page → file discovery fails; URL needs manual update
- 2021–2022 combined files use inconsistent internal sheet structure → sheet navigation logic needs year-aware branching
- Older historical TDP files not available (TDP testing only started 2023) → TDP history will only span 2023+

---

### Step 2 — Extract Data from Each File

**Action:** Open each downloaded `.xlsx` file, navigate to the relevant sheet(s), and extract the required columns. Uses `openpyxl` (not pandas) to enable cell colour and conditional formatting inspection.

**Note on RAG extraction:** APRA CPPP files are likely to use Excel conditional formatting (rules-based) rather than direct cell fill for RAG colouring. `openpyxl` can read the conditional formatting rules but cannot evaluate which colour applies to a given cell. The extraction logic must attempt direct fill first and fall through a defined decision tree if fills return empty. See Decision points below.

**Sub-steps:**
1. For each file, open with `openpyxl` (read-only mode)
2. For current year files only: Open `Colour Legend` sheet first; read the label-to-colour mapping (RGB hex → Green / Amber / Red) — used to interpret direct cell fills if present. Note: this sheet maps colours to labels but does not contain the value thresholds used in conditional formatting rules.
3. Determine file type (MySuper or TDP/Choice) from filename
4. Navigate to the correct sheet(s) and extract:

**MySuper files — sheet: `MySuper Products`**

| Column | All years | Current year only |
|---|---|---|
| `RSE licensee MySuper product name` | ✅ | ✅ |
| `Pass/Fail Indicator` | ✅ | ✅ |
| `10 year Net Investment Return (NIR) p.a.` | — | ✅ |
| `Administration fees and costs charged ($50,000 account balance)` | — | ✅ |
| `Administration fees and costs charged ($100,000 account balance)` | — | ✅ |
| RAG cell fill colour (NIR + both fee columns) | — | ✅ |

**TDP/Choice files — sheets: `Non-Platform TDPs` and `Platform TDPs` (process both)**

| Column | All years | Current year only |
|---|---|---|
| `Product Name` | ✅ | ✅ |
| `Investment Menu Name` | ✅ | ✅ |
| `Investment Option Name` | ✅ | ✅ |
| `Pass/Fail Indicator` | ✅ | ✅ |
| `10 year Net Investment Return (NIR) p.a.` | — | ✅ |
| `Administration fees and costs charged ($50,000 account balance)` | — | ✅ |
| `Administration fees and costs charged ($100,000 account balance)` | — | ✅ |
| RAG cell fill colour (NIR + both fee columns) | — | ✅ |

5. Tag each record with: source year, product type (`MySuper` / `Platform TDP` / `Non-Platform TDP`)

**Decision points:**

**RAG extraction — apply this decision tree for each of the three RAG columns (NIR, fees $50k, fees $100k):**
1. Attempt direct cell fill read via `openpyxl` (`cell.fill.fgColor.rgb`)
2. If all three RAG columns return `None` or `"00000000"` (transparent/no fill) → APRA is using conditional formatting; proceed to step 3
3. Parse the worksheet's conditional formatting rules via `ws.conditional_formatting`; extract value thresholds and colour mappings from rule objects (e.g., `ColorScaleRule`, `CellIsRule`)
4. Apply extracted thresholds to each cell's numeric value to derive the RAG label (`"Green"` / `"Amber"` / `"Red"`)
5. If CF rules cannot be parsed or use an unsupported rule type → set RAG to `"Unknown"` for affected columns; record `"rag_method": "fallback_unknown"` in output metadata; do not abort

**Other decision points:**
- If expected sheet not found in a file → abort that sheet, log mismatch, continue with remaining files/sheets
- If `Colour Legend` sheet not found in current year file → log warning; skip Colour Legend step; rely on CF rule parsing (step 3 above) for RAG derivation
- 2021–2022 combined files: extract MySuper data from `MySuper Products` sheet only — no TDP sheets expected

| | |
|---|---|
| **Data in** | `.xlsx` files (current year + all historical years, both product types) |
| **Data out** | Raw extracted records per file per sheet, each tagged with source year and product type; colour legend map from current year files |

**Failure modes:**
- APRA renames a column in a future file → extraction fails silently (KeyError or wrong column); add explicit column-presence validation post-extraction
- CF rule type unrecognised by openpyxl (e.g., data bar, icon set) → RAG set to `"Unknown"` for affected columns; downstream webapp must handle `null`/`"Unknown"` RAG values gracefully
- `Colour Legend` sheet structure changes → colour mapping step skipped; RAG falls through to CF rule parsing; only a problem if CF rules also fail

---

### Step 3 — Clean and Standardise

**Action:** Normalise all extracted records — across both product types — for reliable joining across years and accurate downstream output.

**Sub-steps:**
1. MySuper records:
   - Trim whitespace and standardise casing on `RSE licensee MySuper product name` (join key)
2. TDP records:
   - Trim whitespace and standardise casing on all three identifier columns: `Product Name`, `Investment Menu Name`, `Investment Option Name`
   - Composite join key = `Product Name` + `|` + `Investment Menu Name` + `|` + `Investment Option Name`
3. Normalise `Pass/Fail Indicator` to consistent values: `"Pass"` / `"Fail"` (across all product types)
4. Apply colour legend map (read in Step 2) to convert RGB cell fill values → `"Green"` / `"Amber"` / `"Red"` / `"Unknown"` for each of the three metric columns independently (NIR, fees $50k, fees $100k)
5. Parse numeric fields (`NIR`, fees) — strip percentage signs, currency symbols, formatting; convert to `float`; set to `null` if value is non-numeric (`"N/A"`, `"--"`, `"*"`)
6. Apply fuzzy match logic across years for each product type to resolve minor identifier variations:
   - **Distance ≤ 1** → auto-apply match silently; log to run log; no human action required
   - **Distance = 2** → apply best-guess match; set `"match_confidence": "low"` on the record; append full detail to `data/flagged-matches.json` sidecar for post-pipeline human review
   - **Distance > 2 or no match** → treat as distinct product/option; do not merge; if history-only record, mark `current_metrics: null`

**Decision points:**
- Fuzzy match distance ≤ 1 → auto-apply; log only
- Fuzzy match distance = 2 → apply best-guess; flag in `flagged-matches.json`; pipeline continues without pausing
- Fuzzy match distance > 2 → no merge; orphan record handled per product-type rules below
- MySuper product appears in current year only → include with empty `history: {}`
- TDP investment option appears in current year only → include with empty `history: {}`
- Product/option discontinued (in history only) → retain historical record, mark `current_metrics: null`
- TDP options with no history before 2023 → expected; `history` object will only contain 2023+ entries
- Human reviewer consults `flagged-matches.json` after pipeline completes; pipeline does NOT pause; corrections applied via `match-overrides.json` on the next run (see Context Item 7 for schema)

| | |
|---|---|
| **Data in** | Raw extracted records from all files |
| **Data out** | Cleaned, standardised records for both MySuper and TDP, ready for joining; `data/flagged-matches.json` sidecar (written if any distance-2 matches found) |

**Context needs:**
- Colour legend map and/or CF rule thresholds (from Step 2)
- Fuzzy match threshold: distance ≤ 1 (auto-apply), distance = 2 (flag), distance > 2 (no merge)

**Failure modes:**
- Fund renames a product or investment option between years → distance > 2; historical records orphaned; reviewer must add a manual override entry in `match-overrides.json`
- Numeric fields contain non-numeric characters → set to `null` (handled in sub-step 5); downstream webapp must handle `null` numeric fields

---

### Step 4 — Build Longitudinal Datasets

**Action:** Join current year records with historical pass/fail records per product/option to produce unified entries — separately for MySuper (flat) and TDP (hierarchical).

**Sub-steps:**
1. MySuper longitudinal:
   - Group cleaned MySuper records by `RSE licensee MySuper product name`
   - Set current year metrics as top-level fields
   - Build `history` object: `{ "YYYY": "Pass" | "Fail" }` for each available year (2021+)
   - Sort `history` keys by year descending
2. TDP longitudinal:
   - Group cleaned TDP records by composite key (`Product Name` + `Investment Menu Name` + `Investment Option Name`)
   - Set current year metrics as top-level fields
   - Tag with `product_type`: `"Platform TDP"` or `"Non-Platform TDP"` (from source sheet)
   - Build `history` object: `{ "YYYY": "Pass" | "Fail" }` for each available year (2023+)
   - Sort `history` keys by year descending

**Decision points:**
- Products/options with no current year record but historical entries → include with `current_metrics: null` flag
- Duplicate identifiers within a single year's file → deduplicate; log warning if values conflict

| | |
|---|---|
| **Data in** | Cleaned records from all years, both product types |
| **Data out** | Two unified datasets — `mysuper_products` list (flat) and `tdp_products` list (hierarchical identifier) |

**Failure modes:**
- Duplicate identifiers in one year's file → conflicting records; deduplication logic required
- All records fail to join across years → history empty for all products; data integrity check needed

---

### Step 5 — Store Output as JSON

**Action:** Serialise both unified datasets into a single `performance-data.json` file with metadata header and safety backup of the previous version.

**Sub-steps:**
1. Archive existing `performance-data.json` as `performance-data-YYYY-backup.json` (if present)
2. Construct output object with metadata header and both product type arrays (see schema below)
3. Serialise to JSON (UTF-8, indented for readability)
4. Write to `data/performance-data.json` in the webapp root directory
5. Log: total MySuper products, total TDP options, source years per type, timestamp

**Decision points:**
- Output directory does not exist → create it before writing
- JSON serialisation error → abort write, preserve backup, surface error

| | |
|---|---|
| **Data in** | `mysuper_products` list + `tdp_products` list |
| **Data out** | `data/performance-data.json` |

**Failure modes:**
- File write fails mid-way → partial/corrupt JSON; backup enables recovery
- Serialisation error at final step → pipeline fails after all processing; backup must be retained

---

## Step Sequence and Dependencies

### Parallel Steps

Steps 1A and 1B run in parallel — independent downloads. Within Step 2, each file can be processed independently (parallelisable).

### Sequential Steps

```
1A (MySuper + TDP current year) ──┐
                                   ├──► 2 (extract all files) ──► 3 (clean) ──► 4 (join longitudinal) ──► 5 (write JSON)
1B (MySuper + TDP historical)   ──┘
```

### Critical Path

`1A + 1B (parallel)` → `2` → `3` → `4` → `5`

### Dependency Map

| Step | Depends On |
|---|---|
| 1A | Trigger confirmed (APRA data published for current year) |
| 1B | Trigger confirmed |
| 2 | 1A and 1B complete |
| 3 | 2 complete |
| 4 | 3 complete |
| 5 | 4 complete |

---

## Context Shopping List

### 1. Current Year APRA Page URLs

| Product Type | URL Pattern |
|---|---|
| MySuper | `https://www.apra.gov.au/YYYY-annual-superannuation-performance-test-mysuper-products` |
| TDP / Choice | `https://www.apra.gov.au/YYYY-annual-superannuation-performance-test-trustee-directed-products` |

**Used by:** Step 1A
**Status:** ✅ Exists — confirmed by Shweta Shah

---

### 2. Historical Results Page URL

**Value:** `https://www.apra.gov.au/previous-performance-test-results`
**Used by:** Step 1B
**Status:** ✅ Exists — confirmed by Shweta Shah

---

### 3. File Naming Patterns

| Year range | Product type | File naming pattern |
|---|---|---|
| Current year | MySuper | `YYYY CPP-MySuper XLSX` |
| Current year | TDP / Choice | `YYYY CPPP - Choice XLSX` |
| 2023+ historical | MySuper | `YYYY-annual-superannuation-performance-test-mysuper-products` |
| 2023+ historical | TDP | `YYYY-annual-superannuation-performance-test-trustee-directed-products` |
| 2021–2022 historical | MySuper only | `YYYY Annual Superannuation Performance Test` |

**Used by:** Steps 1A, 1B
**Status:** ✅ Exists — confirmed by Shweta Shah
**Note:** TDP performance testing began in 2023. No TDP historical files exist for 2021–2022.

---

### 4. Excel Schema (Sheet Names + Column Headers)

**MySuper files — sheet: `MySuper Products`**

| Column | Purpose |
|---|---|
| `RSE licensee MySuper product name` | Product identifier (join key) |
| `Pass/Fail Indicator` | YFYS test result — all years |
| `10 year Net Investment Return (NIR) p.a.` | Return metric — current year only |
| `Administration fees and costs charged ($50,000 account balance)` | Fee metric — current year only |
| `Administration fees and costs charged ($100,000 account balance)` | Fee metric — current year only |

**TDP/Choice files — sheets: `Non-Platform TDPs` and `Platform TDPs`**

| Column | Purpose |
|---|---|
| `Product Name` | Top-level product identifier |
| `Investment Menu Name` | Mid-level identifier |
| `Investment Option Name` | Lowest-level identifier (join key component) |
| `Pass/Fail Indicator` | YFYS test result — all years |
| `10 year Net Investment Return (NIR) p.a.` | Return metric — current year only |
| `Administration fees and costs charged ($50,000 account balance)` | Fee metric — current year only |
| `Administration fees and costs charged ($100,000 account balance)` | Fee metric — current year only |

**Used by:** Step 2
**Status:** ✅ Exists — confirmed by Shweta Shah

---

### 5. RAG Colour Mapping (Colour Legend Sheet)

**Description:** The APRA CPPP files contain a dedicated `Colour Legend` sheet in the same workbook (both MySuper and TDP/Choice files). The pipeline reads this sheet programmatically in Step 2 to build the RGB → label map — no manual hardcoding required.

**Columns carrying RAG cell fill (same across all product types):**
- `10 year Net Investment Return (NIR) p.a.`
- `Administration fees and costs charged ($50,000 account balance)`
- `Administration fees and costs charged ($100,000 account balance)`

**How to read:** Open `Colour Legend` sheet with openpyxl; iterate rows; extract cell fill RGB + label text; build dict `{ "RRGGBB": "Green", ... }`

**Used by:** Steps 2, 3
**Status:** ✅ Exists — confirmed by Shweta Shah
**Risk:** If APRA changes `Colour Legend` structure in a future year, mapping extraction logic needs updating

---

### 6. JSON Output Schema

**Used by:** Step 5
**Status:** ✅ Defined

```json
{
  "last_updated": "2025-06",
  "source_years_mysuper": ["2025", "2024", "2023", "2022", "2021"],
  "source_years_tdp": ["2025", "2024", "2023"],
  "total_mysuper_products": 563,
  "total_tdp_options": 1250,
  "mysuper_products": [
    {
      "product_name": "AustralianSuper — Balanced",
      "pass_fail_current": "Pass",
      "nir_10yr": 7.2,
      "nir_rag": "Green",
      "fees_50k": 450,
      "fees_50k_rag": "Green",
      "fees_100k": 550,
      "fees_100k_rag": "Amber",
      "history": {
        "2024": "Pass",
        "2023": "Pass",
        "2022": "Fail",
        "2021": "Pass"
      }
    }
  ],
  "tdp_products": [
    {
      "product_name": "BT Panorama",
      "investment_menu_name": "BT Panorama Super",
      "investment_option_name": "Australian Shares",
      "product_type": "Platform TDP",
      "pass_fail_current": "Fail",
      "nir_10yr": 5.1,
      "nir_rag": "Red",
      "fees_50k": 820,
      "fees_50k_rag": "Red",
      "fees_100k": 1100,
      "fees_100k_rag": "Red",
      "history": {
        "2024": "Pass",
        "2023": "Pass"
      }
    }
  ]
}
```

> **Note:** `nir_rag`, `fees_50k_rag`, and `fees_100k_rag` are independent across all product types. TDP `history` only spans 2023+ (TDP testing began 2023). MySuper `history` spans 2021+. The webapp filters TDP records by `Product Name`, `Investment Menu Name`, and `Investment Option Name` independently.

---

### 7. Fuzzy Match Rules for Identifier Joining

**Description:** Decision rules and output artifacts for handling minor identifier variations across years
**Used by:** Step 3
**Status:** ✅ Defined

**Match thresholds:**
| Distance | Action |
|---|---|
| ≤ 1 | Auto-apply match; log to run log only |
| = 2 | Apply best-guess match; set `"match_confidence": "low"`; append to `flagged-matches.json` |
| > 2 | No merge; treat as distinct product; orphaned history-only records marked `current_metrics: null` |

**TDP composite key matching:** All three identifier columns (`Product Name`, `Investment Menu Name`, `Investment Option Name`) are matched independently. A match is only applied if all three components are within threshold.

**`data/flagged-matches.json` sidecar schema:**
```json
[
  {
    "product_type": "MySuper",
    "year_a": "2024",
    "name_a": "AustralianSuper Balanced",
    "year_b": "2023",
    "name_b": "AustralianSuper - Balanced",
    "levenshtein_distance": 2,
    "action_taken": "best_guess_match_applied",
    "match_confidence": "low"
  }
]
```

**`match-overrides.json` (future capability — run 2+):** Allows reviewer to confirm or reject flagged matches. On the next pipeline run, confirmed overrides are applied before fuzzy matching runs. Schema to be defined on first run after reviewing `flagged-matches.json` output.

**Pipeline behaviour:** Pipeline never pauses for human review. It always completes with best-available data. Reviewer consults `flagged-matches.json` post-run.
