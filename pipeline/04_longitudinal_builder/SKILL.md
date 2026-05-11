---
name: apra-longitudinal-builder
description: >
  This skill should be used when the user wants to join cleaned APRA CPPP
  records across years to produce unified longitudinal datasets for MySuper
  and TDP products. Groups records by join key, sets current year metrics as
  top-level fields, and builds per-product history objects spanning all
  available years. Produces two arrays — mysuper_products and tdp_products —
  ready for JSON serialisation. Part of the APRA Performance Data Loader
  pipeline (Step 4). Must only be run after the fuzzy match review gate in
  the apra-data-cleaner skill has been resolved.
metadata:
  author: Shweta Shah
  version: "2.0.0"
  workflow: APRA Performance Data Loader
  pipeline-step: "4"
---

# APRA Longitudinal Builder

Joins cleaned APRA CPPP records across all years to produce two unified datasets: mysuper_products (flat) and tdp_products (hierarchical).

## Before Running

Confirm the Data Cleaner (Step 3) has completed and `apra_cleaned.json` exists.

## Run Command

```bash
PYTHONIOENCODING=utf-8 python "C:\Users\alpes\.claude\Member Performance Data\outputs\apra-skills\apra-longitudinal-builder\scripts\apra_longitudinal.py" --workdir "C:\Users\alpes\.claude\Member Performance Data\outputs\apra-skills\apra_work" --year YYYY
```

---

## What the Builder Does

**MySuper dataset:**
- Groups records by `join_key` (standardised product name)
- Current year record → top-level fields: `product_name`, `pass_fail_current`, `nir_10yr`, `nir_rag`, `fees_50k`, `fees_50k_rag`, `fees_100k`, `fees_100k_rag`
- All years → `history: { "YYYY": "Pass" | "Fail" }` — spans 2021–current year
- Products with no current year record → `pass_fail_current: null`, metrics null, `current_metrics_available: false`

**TDP dataset:**
- Groups by composite `join_key` (`product_name|investment_menu_name|investment_option_name`)
- Same structure as MySuper plus: `investment_menu_name`, `investment_option_name`, `product_type`
- History spans 2023–current year only (TDP testing began 2023)

**Deduplication:** Duplicate join keys within a single year → first occurrence kept; conflicts logged.

---

## History Years

| Product type | History spans | Notes |
|-------------|--------------|-------|
| MySuper | 2021–current year | Fully linked across all years |
| TDP | 2023–current year (current year metrics only for most products) | 2023–2024 historical TDP records use option name as key, so most don't link to current year products |

---

## Expected Output (2025 full run)

| Metric | Value |
|--------|-------|
| MySuper products | 127 |
| MySuper with current 2025 metrics | 47 |
| MySuper history-only | 80 |
| TDP Platform options | 1,706 |
| TDP Non-Platform options | 0 (all mapped to Platform due to join key behaviour) |
| TDP history-only | 824 |
| MySuper history years | `['2025', '2024', '2023', '2022', '2021']` |
| TDP history years | `['2025', '2024', '2023']` |
| Duplicate conflicts | ~287 |

---

## Outputs

- `apra_work/apra_longitudinal.json` — both product arrays and build summary
- `apra_work/apra_longitudinal_log.json` — duplicate warnings, orphaned history, history-only products

## Failure Handling

- **Duplicate join keys with conflicting values:** First occurrence kept; conflict logged. Surface to user before proceeding if count is unexpectedly high.
- **Empty history for all products:** Indicates join key mismatch — likely a column naming change. Do not proceed to JSON writer.
- **No current year records found:** Confirm `--year` matches the downloaded year.

## Guidelines

- TDP history only spans 2023+. Absence of 2021–2022 TDP history is not an error.
- MySuper history spans 2021+. Missing 2021 or 2022 records should be noted but do not abort.
- History keys are sorted descending (most recent year first).
- Products in history only are included with `current_metrics_available: false`.
