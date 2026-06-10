---
name: apra-data-cleaner
description: >
  This skill should be used when the user wants to clean and standardise raw
  APRA CPPP records extracted from Excel files. Normalises product identifiers,
  standardises Pass/Fail values, applies the colour legend map to RAG columns,
  parses numeric fields, and runs fuzzy matching to flag borderline identifier
  variations across years for human review. Produces cleaned records and a
  fuzzy match flag report. Part of the APRA Performance Data Loader pipeline
  (Step 3). Contains a required human review gate before proceeding to Step 4.
metadata:
  author: Shweta Shah
  version: "2.0.0"
  workflow: APRA Performance Data Loader
  pipeline-step: "3"
---

# APRA Data Cleaner

Normalises and standardises extracted APRA records, applies colour mapping, and produces a fuzzy match flag report for human review before Step 4.

## Before Running

Install required Python packages (run once per session):

```bash
pip install thefuzz python-Levenshtein --break-system-packages -q
```

## Run Command

```bash
PYTHONIOENCODING=utf-8 python "C:\Users\alpes\.claude\Member Performance Data\outputs\apra-skills\apra-data-cleaner\scripts\apra_cleaner.py" --workdir "C:\Users\alpes\.claude\Member Performance Data\outputs\apra-skills\apra_work"
```

---

## What the Cleaner Does

**MySuper records:**
- Trim whitespace and standardise casing on `product_name` (used as join key)
- Normalise `pass_fail_raw` → `"Pass"` / `"Fail"` / `"Unknown"`
- Apply colour legend RGB → `"Green"` / `"Amber"` / `"Red"` / `"Unknown"`
- Parse numeric fields (NIR, fees) to float; `N/A`, `--`, `*` → `null`

**TDP records:**
- Trim and standardise all three identifier columns: `product_name`, `investment_menu_name`, `investment_option_name`
- Build composite join key: `product_name|investment_menu_name|investment_option_name`
- Same Pass/Fail, colour, and numeric handling as MySuper

**Fuzzy matching:**
- Identifies product identifiers that differ slightly across years (Levenshtein distance 1–2)
- Distance 1 → auto-accepted; distance 2 → flagged for human review

---

## Join Key Behaviour — Historical TDP Records

Historical TDP records (2023–2024) were extracted with `product_name` = investment option name and empty `investment_menu_name`. Their join key is therefore `"option_name||option_name"`. This does **not** match the 2025 TDP join key of `"product_name|menu_name|option_name"`.

This means historical TDP products appear as separate longitudinal entries rather than linking to their 2025 counterparts. **TDP history is effectively 2025-only for the current year metrics view.** MySuper history is fully linked 2021–2025. This is a known structural limitation of APRA's older file format.

---

## Human Gate: Fuzzy Match Review

After running the cleaner, `apra_fuzzy_flags.json` will contain flagged pairs. For a full 2021–2025 run, expect ~745 fuzzy pairs (~511 requiring review). This high number is driven by cross-year option name variations.

For routine pipeline runs, the fuzzy gate can be skipped — the longitudinal builder will handle mismatches by creating separate history-only entries for unmatched products. Only review the gate when investigating specific product tracking issues.

---

## Expected Output (full 2021–2025 run)

- Total records cleaned: ~2,931
- Records dropped: 0
- RAG fallback applied: Yes (conditional formatting in all files)
- Fuzzy pairs found: ~745
- Fuzzy pairs requiring review: ~511

---

## Outputs

- `apra_work/apra_cleaned.json` — cleaned records with `join_key`, `pass_fail`, numeric fields, RAG values
- `apra_work/apra_fuzzy_flags.json` — fuzzy match pairs report
- `apra_work/apra_cleaning_log.json` — record counts, null field counts, RAG distribution

## Failure Handling

- **Numeric field with non-numeric content** (`N/A`, `--`, `*`): converted to `null`; logged.
- **Empty join key after cleaning:** Record excluded; warning logged with source file and row context.
- **All RAG values Unknown:** Pass/Fail fallback applied automatically (Pass → Green, Fail → Red); noted in cleaning log.

## Guidelines

- The human review gate is advisory for routine runs — skipping it is acceptable if you trust the fuzzy auto-accept logic.
- Products appearing in current year only → included with empty history.
- Discontinued products (history only) → retained; Longitudinal Builder handles `current_metrics_available: false`.
- TDP options with no history before 2023 → expected; do not flag as an error.
