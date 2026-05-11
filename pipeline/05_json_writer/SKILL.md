---
name: apra-json-writer
description: >
  This skill should be used when the user wants to serialise unified APRA CPPP
  longitudinal datasets into the final performance-data.json output file for
  the Benchmark Tracker webapp. Archives any existing output file as a dated
  backup, constructs the metadata header, and writes the complete JSON
  structure to the webapp data directory. Includes an optional human review
  of the summary log before committing the write. Part of the APRA Performance
  Data Loader pipeline (Step 5).
metadata:
  author: Shweta Shah
  version: "1.0.0"
  workflow: APRA Performance Data Loader
  pipeline-step: "5"
---

# APRA JSON Writer

Serialises the final performance-data.json file for the Benchmark Tracker webapp, with backup and summary logging.

## Workflow

### Step 1 — Read the Script

Read `${CLAUDE_SKILL_DIR}/scripts/apra_json_writer.py` so you understand the serialisation and backup logic before running.

### Step 2 — Confirm Parameters

Ask the user to confirm:
1. **Work directory:** Where `apra_longitudinal.json` is stored (e.g., `./apra_work`).
2. **Output path:** Full path to the webapp data directory (e.g., `./webapp/data/`). The script will create this directory if it does not exist.
3. **Current year:** The year being loaded (used for backup filename and metadata header).
4. **Last updated value:** The `last_updated` field in the JSON metadata header (e.g., `"2025-06"` — month of APRA publication).

Before running, present the summary from `apra_longitudinal.json` (total MySuper products, total TDP options, history year ranges) and ask the user to confirm the numbers look correct.

### Step 3 — OPTIONAL HUMAN GATE: Review Before Write

Present the proposed JSON metadata header to the user for confirmation:

```json
{
  "last_updated": "<last_updated>",
  "source_years_mysuper": [ ... ],
  "source_years_tdp": [ ... ],
  "total_mysuper_products": <n>,
  "total_tdp_options": <n>
}
```

Ask: "Confirm you are happy with these values and the record counts before I write the file."

Do not write until the user confirms.

### Step 4 — Run the JSON Writer

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/apra_json_writer.py \
  --workdir <work_dir> \
  --outdir <output_dir> \
  --year <current_year> \
  --updated "<last_updated>"
```

The script will:
1. Check for an existing `performance-data.json` in the output directory — if found, archive as `performance-data-<YYYY>-backup.json` before writing
2. Construct the full output object with metadata header + both product arrays
3. Serialise to UTF-8 indented JSON
4. Write to `<output_dir>/performance-data.json`
5. Log: total MySuper products, total TDP options, source years per type, timestamp

### Step 5 — Confirm Success

Read the summary log produced by the script and present the final confirmation to the user:

- Output file written: `<path>/performance-data.json`
- Backup created (if applicable): `<path>/performance-data-<YYYY>-backup.json`
- Total MySuper products
- Total TDP options
- Source years included

Tell the user: "The APRA Performance Data Loader pipeline is complete. `performance-data.json` is ready for the Benchmark Tracker webapp."

## Outputs

### `<output_dir>/performance-data.json` — Final Output

Complete JSON file matching the schema defined in the Workflow Definition:

```json
{
  "last_updated": "2025-06",
  "source_years_mysuper": ["2025", "2024", "2023", "2022", "2021"],
  "source_years_tdp": ["2025", "2024", "2023"],
  "total_mysuper_products": 563,
  "total_tdp_options": 1250,
  "mysuper_products": [ ... ],
  "tdp_products": [ ... ]
}
```

### `<output_dir>/performance-data-<YYYY>-backup.json` — Backup (if prior file existed)

### `<workdir>/apra_write_log.json` — Write Summary Log

## Failure Handling

- **JSON serialisation error:** Abort the write immediately. Do not overwrite the existing file. Preserve the backup. Surface the error to the user.
- **Output directory does not exist:** Create it before writing.
- **File write fails mid-way:** The backup file ensures recovery. Inform the user the write failed and the previous version remains intact as the backup.
- **Longitudinal file not found:** Do not proceed — ask the user to confirm the work directory path and run apra-longitudinal-builder first.

## Guidelines

- Never write the output file without user confirmation of the record counts (Step 3 human gate).
- Always archive an existing `performance-data.json` before overwriting — even if the user says it is fine to overwrite.
- The `total_tdp_options` count is the sum of Platform TDP and Non-Platform TDP entries.
- The output file must be valid JSON before the skill is considered complete — read back the first 10 lines after writing to confirm it was not truncated.
