# AI Building Block Spec: APRA Performance Data Loader

**Author:** Shweta Shah — Senior Product Manager, Investment & Financial Data & Regulatory Solutions
**Date:** 2026-03-24
**Framework:** Business-First AI — Step 3.1: Design
**Feeds into:** Investment Option Benchmark Tracker (Use Case 4) · YFYS Risk Simulator (Use Case 9)
**Source definition:** `apra-performance-data-loader-definition.md`

---

## Scenario Summary

| Field | Value |
|---|---|
| **Workflow Name** | APRA Performance Data Loader |
| **Description** | Downloads, parses, and stores APRA CPPP data for both MySuper and TDP products — current year and all available historical files — into a structured JSON dataset ready for member-facing lookup in the Benchmark Tracker webapp |
| **Process Outcome** | A clean, queryable `performance-data.json` containing per-product current year metrics (10yr NIR, fees, RAG status, pass/fail) and historical pass/fail records for both MySuper and TDP product types |
| **Trigger** | Annual — APRA publishes new CPPP data (June each year); or manual developer-initiated refresh |
| **Lens** | Individual |
| **Current Owner** | Shweta Shah (developer / data owner, Maven course build Apr–May 2026) |
| **Platform** | Claude.ai — Cowork (desktop), user-selected folder mounted |

---

## Autonomy Level Assessment

**Workflow-level autonomy: Deterministic**

Every step executes in a fixed, predetermined sequence with all branching logic explicitly defined in the Workflow Definition (404 handling, missing sheet handling, file naming pattern matching, duplicate deduplication, fuzzy match threshold). The AI does not exercise judgment about what to do next — all decisions are encoded as rules. The single partial exception is Step 3's fuzzy match flag review, which introduces a bounded human checkpoint without altering the overall pipeline classification.

The Workflow Definition itself declares the type as "Deterministic," and the detailed step logic confirms this assessment.

---

## Orchestration Mechanism

**Mechanism: Skill-Powered Prompt**
**Involvement Mode: Augmented**

**Rationale:** A plain Prompt is insufficient because the pipeline requires active tool use across multiple steps (web access, Python execution, file writes) and produces intermediate outputs that feed the next step. A full Agent is not warranted because there is no dynamic sequencing — the order of steps is fixed and known in advance, and the AI does not need to decide what to do next based on runtime context. A Skill-Powered Prompt is the right fit: each major phase of the pipeline becomes a reusable Cowork skill, Claude executes them in sequence within a session, and Shweta remains present to review the fuzzy match summary and confirm the final JSON before it is written.

**Involvement Mode rationale:** The workflow is developer-triggered (manual or annual). Shweta is present during the run to initiate each skill, review the fuzzy match flag report from Step 3, and confirm output quality before the JSON is committed. This is Augmented — human steers at key checkpoints; AI executes all computation.

---

## Architecture Decisions

| Decision | Value | Rationale |
|---|---|---|
| Platform | Claude.ai — Cowork (desktop) | User confirmed; not Claude Code |
| Web access method | WebFetch tool (Cowork-native) or Bash/Python requests | To be resolved during Construct — APRA is a public Australian government site |
| Python runtime | Bash tool + Python in Cowork sandbox | Required for openpyxl (Excel parsing), fuzzy matching, JSON serialisation |
| File storage | User-selected mounted folder | Provides persistent access to downloaded files and output across sessions |
| Parallel execution (1A + 1B) | Sequential within single Cowork session | Cowork does not support parallel sub-processes; steps 1A and 1B will execute sequentially within the same skill invocation, which is acceptable given file sizes |
| Fuzzy match rules | Deferred — produce on first real data run | Definition marks this as "Needs Creation"; threshold of Levenshtein ≤ 2 is the default starting point |
| Shareability | Individual use only (Maven course build) | No team sharing requirements at this stage |

**Constraints:**
- Binary file download (xlsx) from APRA via Cowork web access tools needs confirmation during Construct. If WebFetch cannot handle binary downloads, Bash with Python `requests` will be used.
- openpyxl is not a standard Cowork library — it must be installed in the Cowork sandbox via `pip install openpyxl --break-system-packages` at the start of each session (or added to a setup step in the skill).
- Parallel execution of 1A and 1B is not supported in Cowork; sequential execution is functionally equivalent given the file download sizes involved.

---

## Step-by-Step Decomposition

| Step | Name | Autonomy | Building Blocks | Tools / Connectors | Skill Candidate | Human Gate | Role |
|---|---|---|---|---|---|---|---|
| 1A | Download current year files (MySuper + TDP) | Deterministic | Skill, Context | Web access (APRA pages), File system | ✅ APRA File Downloader | None — failure message surfaced automatically | Developer |
| 1B | Download historical files (MySuper + TDP) | Deterministic | Skill, Context | Web access (APRA historical page), File system | ✅ APRA File Downloader (same skill, historical mode) | None — already-downloaded files skipped automatically | Developer |
| 2 | Extract data from each file | Deterministic | Skill, Context | Python (openpyxl), File system | ✅ APRA Excel Extractor | None — sheet/column mismatches logged automatically | Developer |
| 3 | Clean and standardise | Guided | Skill, Context | Python (Levenshtein / fuzzy library), File system | ✅ APRA Data Cleaner | **Review fuzzy match flag report before proceeding to Step 4** | Developer |
| 4 | Build longitudinal datasets | Deterministic | Skill | Python (in-memory processing) | ✅ Longitudinal Dataset Builder | None | Developer |
| 5 | Store output as JSON | Deterministic | Skill | Python (JSON serialisation), File system | ✅ JSON Writer | Optional: review log summary before confirming write | Developer |

### Autonomy Spectrum Summary

```
Deterministic ——————————[1A][1B][2]——————[3 (fuzzy gate)]——[4][5]——————— Autonomous
```

Steps 1A, 1B, 2, 4, and 5 are fully deterministic. Step 3 introduces a bounded human checkpoint (fuzzy match review) but does not make the overall workflow guided — it is a deterministic pipeline with one optional human review gate.

---

## Skill Candidates

### Skill 1 — APRA File Downloader
*Covers Steps 1A and 1B*

**Purpose:** Constructs APRA URLs for the current year and the historical results page, scrapes each page for xlsx links matching known naming patterns, downloads any files not already stored locally, and reports a download manifest.

**Inputs:**
- Current year (integer, e.g. 2025)
- List of already-downloaded file names (for incremental refresh logic)
- Target download directory path

**Outputs:**
- Downloaded xlsx files in the working directory
- Download manifest: `{ file_name, year, product_type, status: downloaded | skipped | failed, error_message }`

**Decision logic:**
- 404 on current year APRA page → surface message: "CPPP [MySuper/TDP] data not yet available for YYYY. Published June–December annually." Continue with the other product type file.
- Multiple xlsx links found on a page → select by exact naming pattern (see File Naming Patterns in Context Inventory)
- Historical file already present locally → skip (incremental refresh)
- 2021–2022 historical files → MySuper only; do not expect or create TDP records for those years
- If a historical file download fails → log warning, continue with remaining files

**Failure modes:**
- APRA changes URL structure → download fails; manual URL update required
- File link renamed on page → no match found; requires manual intervention
- Binary file download not supported via WebFetch → fall back to Bash/Python requests (to be confirmed in Construct)

---

### Skill 2 — APRA Excel Extractor
*Covers Step 2*

**Purpose:** Opens each xlsx file with openpyxl, reads the Colour Legend sheet (current year files only), navigates to the correct product sheets, and extracts required columns with RAG colour values, tagging each record with source year and product type.

**Inputs:**
- Download manifest from Skill 1
- Extraction schema: sheet names and column headers per product type and year range (from Context Inventory)

**Outputs:**
- Raw extracted records per file per sheet, tagged with source year and product type
- Colour legend map from current year files: `{ "RRGGBB": "Green" | "Amber" | "Red" }`

**Decision logic:**
- File type (MySuper vs TDP) → determined from filename
- Current year file → extract full column set including RAG colours + read Colour Legend sheet
- Historical file → extract product identifier and Pass/Fail only
- Colour Legend sheet absent → attempt RGB inference from extracted values; log warning
- Expected sheet not found in file → skip that sheet, log mismatch, continue
- RAG stored as conditional formatting (not direct cell fill) → openpyxl cannot read it; fall back to Pass/Fail for RAG derivation; flag in output metadata
- 2021–2022 combined files → extract from `MySuper Products` sheet only; no TDP sheets expected

**Failure modes:**
- APRA renames a column in a future file → extraction fails silently (KeyError or wrong column)
- Conditional formatting → cell fill returns `None` for all three RAG columns
- Colour Legend sheet structure changes → colour mapping fails; manual update required

---

### Skill 3 — APRA Data Cleaner
*Covers Step 3*

**Purpose:** Normalises all extracted records across both product types for reliable cross-year joining — standardises identifiers, normalises pass/fail values, applies the colour legend map, parses numeric fields, and produces a fuzzy match flag report for human review.

**Inputs:**
- Raw extracted records from Skill 2 (both product types, all years)
- Colour legend map from Skill 2
- Fuzzy match threshold: Levenshtein distance ≤ 2 (default; adjustable)

**Outputs:**
- Cleaned, standardised records for both MySuper and TDP, ready for joining
- Fuzzy match flag report: list of identifier pairs that are borderline matches (for human review before Step 4)

**Decision logic:**
- MySuper join key → `RSE licensee MySuper product name` (trimmed, standardised casing)
- TDP composite join key → `Product Name` + `|` + `Investment Menu Name` + `|` + `Investment Option Name` (all three trimmed and standardised)
- Fuzzy match ≤ 2 → auto-match; include in flag report for human awareness
- Fuzzy match > 2 → treat as distinct records
- Product in current year only → include with empty `history: {}`
- Discontinued product (history only) → retain historical record, exclude from current metrics
- TDP options with no history before 2023 → expected; history object spans 2023+ only

**Failure modes:**
- Fund renames a product or investment option between years → breaks join key; historical records orphaned; flagged in fuzzy match report
- Numeric fields contain non-numeric characters (`"N/A"`, `"--"`, `"*"`) → parse error; explicit null handling required

**Human gate:** Review the fuzzy match flag report before invoking Skill 4. Confirm or manually correct any borderline joins.

---

### Skill 4 — Longitudinal Dataset Builder
*Covers Step 4*

**Purpose:** Joins cleaned current year records with historical pass/fail entries per product or investment option to produce two unified datasets — one flat (MySuper) and one hierarchical (TDP).

**Inputs:**
- Cleaned records from Skill 3 (both product types, all years)

**Outputs:**
- `mysuper_products` list: flat, each entry with current year metrics and `history` object spanning 2021+
- `tdp_products` list: hierarchical identifier, each entry with current year metrics and `history` object spanning 2023+; tagged with `product_type`: `"Platform TDP"` or `"Non-Platform TDP"`

**Decision logic:**
- Group by join key per product type (from Skill 3)
- Current year metrics set as top-level fields; history built from all available years
- History keys sorted descending by year
- Products with no current year record → include with `current_metrics: null`
- Duplicate identifiers within a single year's file → deduplicate; log warning if values conflict

**Failure modes:**
- Duplicate identifiers with conflicting values → deduplication requires tie-breaking rule (first occurrence by default; log conflict)
- All records fail to join across years → history empty for all products; data integrity check needed before proceeding to Skill 5

---

### Skill 5 — JSON Writer
*Covers Step 5*

**Purpose:** Archives the existing `performance-data.json`, serialises both unified datasets into the target schema with a metadata header, writes the final file to the webapp data directory, and produces a summary log.

**Inputs:**
- `mysuper_products` list from Skill 4
- `tdp_products` list from Skill 4
- Output path: `data/performance-data.json` (in webapp root)
- Current year (for backup file naming and metadata header)

**Outputs:**
- `data/performance-data.json` (UTF-8, indented)
- `data/performance-data-YYYY-backup.json` (archive of previous version if present)
- Summary log: total MySuper products, total TDP options, source years per type, timestamp

**Decision logic:**
- Existing `performance-data.json` found → archive as `performance-data-YYYY-backup.json` before writing
- Output directory does not exist → create before writing
- JSON serialisation error → abort write, preserve backup, surface error

**Failure modes:**
- File write fails mid-way → partial/corrupt JSON; backup enables recovery
- Serialisation error → pipeline fails after all processing; backup must be retained until confirmed resolved

---

## Session Context Document

A session context document will be produced during Construct to carry pipeline state across skill invocations. It will hold:
- Download manifest (file names, years, product types, statuses)
- Colour legend map (RGB → label)
- Cleaned record counts per product type and year
- Fuzzy match summary (count of flags, decisions made)
- Session run timestamp and current year in scope

This document ensures each skill invocation has the context it needs without requiring Shweta to re-specify inputs manually.

---

## Step Sequence and Dependencies

```
1A (current year: MySuper + TDP) ──┐
                                    ├──► 2 (extract all files) ──► 3 (clean + fuzzy review gate) ──► 4 (build longitudinal) ──► 5 (write JSON)
1B (historical: MySuper + TDP)   ──┘
```

| Step | Depends On |
|---|---|
| 1A | Trigger confirmed (APRA data published for current year) |
| 1B | Trigger confirmed |
| 2 | 1A and 1B complete (both download manifests available) |
| 3 | Step 2 complete |
| 4 | Step 3 complete AND fuzzy match report reviewed by developer |
| 5 | Step 4 complete |

*Note: In Cowork, 1A and 1B execute sequentially within the same skill invocation rather than in true parallel. This is functionally equivalent given the file sizes and does not affect data integrity.*

---

## Context Inventory

| Context Item | Status | Used By | Notes |
|---|---|---|---|
| Current year APRA page URLs (MySuper + TDP) | ✅ Confirmed | Skill 1 (1A) | URL pattern: `https://www.apra.gov.au/YYYY-annual-superannuation-performance-test-[product-type]` |
| Historical results page URL | ✅ Confirmed | Skill 1 (1B) | `https://www.apra.gov.au/previous-performance-test-results` |
| File naming patterns (current year + historical, both product types) | ✅ Confirmed | Skill 1 | 2021–2022: MySuper only; 2023+: both types |
| Excel schema (sheet names + column headers per product type) | ✅ Confirmed | Skill 2 | MySuper: `MySuper Products` sheet; TDP: `Non-Platform TDPs` and `Platform TDPs` sheets |
| RAG Colour Legend reading method | ✅ Confirmed | Skills 2, 3 | Read `Colour Legend` sheet programmatically; RGB → label dict |
| JSON output schema | ✅ Confirmed | Skill 5 | Defined in Workflow Definition — mysuper_products + tdp_products with metadata header |
| Fuzzy match rules | ⚠️ Needs Creation | Skill 3 | Default threshold Levenshtein ≤ 2; full rules to be defined after inspecting real data in first run |

---

## Tools and Connectors Required

| Tool | Purpose | Steps |
|---|---|---|
| Web access (WebFetch or Python `requests`) | Scrape APRA pages; download xlsx files | 1A, 1B |
| Python runtime (Bash tool) | Execute ETL logic, data transformation, JSON serialisation | 2, 3, 4, 5 |
| openpyxl | Open and parse xlsx files; read cell fill colours | 2 |
| Python fuzzy matching library (e.g., `python-Levenshtein` or `fuzzywuzzy`) | Identifier fuzzy matching across years | 3 |
| File system (mounted folder) | Read downloaded files; write output JSON; manage backups | 1A, 1B, 5 |

---

## Integration Research Needed

The following integrations require platform availability verification during Construct:

| Tool | Purpose | Steps Dependent | Research Question |
|---|---|---|---|
| Web access — binary file download | Download xlsx files from APRA's public website | 1A, 1B | Can Cowork's WebFetch tool download binary files (xlsx)? If not, confirm that Bash/Python `requests` is available and can reach `apra.gov.au` |
| openpyxl | Excel parsing with cell fill colour reading | 2 | Confirm openpyxl can be installed in the Cowork sandbox via `pip install openpyxl --break-system-packages` and that cell fill RGB extraction works for APRA's file format |
| python-Levenshtein / fuzzywuzzy | Fuzzy string matching for identifier joining | 3 | Confirm fuzzy matching library is installable in Cowork sandbox; verify Levenshtein distance calculation is accurate for the fund name variations encountered in real APRA data |

---

## Model Recommendation

**Recommended model class: Fast (e.g., Claude Haiku or Sonnet)**

This workflow is a deterministic ETL pipeline. All logic is explicitly defined in the skill instructions — there is no open-ended reasoning required during execution. A fast model is appropriate for all five skill invocations. Depth and reasoning power are not needed here; what matters is accurate code generation and reliable step execution. Claude Sonnet is a practical default that balances speed and reliability for code generation tasks in Cowork.

If the pipeline is run in one long session (all five skills in sequence), the model's context window usage should be monitored, particularly during Step 2 if many xlsx files are processed and extracted records are passed through context.

---

## Prerequisites

Before running the workflow for the first time:

1. Confirm a folder is mounted in Cowork (user-selected folder is active in this session) — this is where downloaded files and output JSON will be stored
2. Confirm web access to `apra.gov.au` via Cowork tools (WebFetch or Bash/Python requests)
3. Install Python dependencies at the start of each session: `openpyxl`, `python-Levenshtein` (or equivalent)
4. Confirm current year — verify APRA has published CPPP data for the target year (published June–December annually)
5. On first run: expect to download all historical files (2021+); on subsequent annual runs, only Step 1A is needed unless historical files are missing

---

## Recommended Implementation Order

| Priority | Skill | Rationale |
|---|---|---|
| 1 | Skill 2 — APRA Excel Extractor | Validate the extraction logic against real APRA files first — this is the highest-risk step (APRA may store RAG as conditional formatting; column names may vary) |
| 2 | Skill 1 — APRA File Downloader | Confirm web access and binary download work before building the rest of the pipeline |
| 3 | Skill 3 — APRA Data Cleaner | Develop fuzzy match rules based on real data from Skills 1 and 2 |
| 4 | Skill 4 — Longitudinal Dataset Builder | Straightforward once cleaned records are confirmed correct |
| 5 | Skill 5 — JSON Writer | Final step; build last once the full dataset is validated |

*Quick win: Start by manually downloading one APRA xlsx file and running Skill 2 against it to validate extraction before building Skill 1.*

---

## Where to Run

**Cowork desktop session with a mounted folder.**

Run all five skills within a single Cowork session to maintain context across skill invocations (download manifest, colour legend map, cleaned record counts). The session context document ensures continuity even if the session is interrupted.

For the annual refresh cycle (June each year), only Skill 1A and Skills 2 through 5 are needed — Skill 1B can be skipped if historical files are already stored locally.

---

## Stakeholders

| Role | Person | Involvement |
|---|---|---|
| Developer / Data Owner | Shweta Shah | Triggers workflow; reviews fuzzy match report; confirms final JSON |
| Downstream consumer (course build) | Shweta Shah | Uses `performance-data.json` in Benchmark Tracker webapp and YFYS Risk Simulator |

*This is an Individual-lens workflow. No additional stakeholders, notification routes, or multi-user access requirements apply during the Maven course build phase.*

---

*AI Building Block Spec — APRA Performance Data Loader — generated 2026-03-24*
*Business-First AI Framework v6.0 — Step 3.1: Design*
