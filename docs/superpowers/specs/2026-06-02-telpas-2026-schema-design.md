# Design: 2025-2026 TELPAS Schema Support

**Date:** 2026-06-02
**Status:** Approved (pending spec review)
**Source document:** `2026-telpas-data-file-layout.pdf` (Texas Statewide Assessments, "2025-2026 Layout for Student Results Data Files – TELPAS", layout table pages 3-17; assessment score reference page 18)
**Sample file:** `SP_0326_TELPAS_101902_ALDINE ISD_V01.txt` (22,342 data rows, fixed-width records of 1200 chars + CRLF)

## Problem

The tool processes TEA fixed-width text files into CSVs via `pd.read_fwf` driven by `start`/`end` byte positions in YAML schemas. TELPAS routing already exists: a filename containing `TELPAS` (case-insensitive) maps to `test_name = "telpas"`, and the 2024-2025 file shipped as `telpas_2025.yaml`.

The **2025-2026 TELPAS file** is delivered now (header `0326` = Spring 2026). With `TELPAS` in the filename and header `0326`, `processor.process_file` already resolves the schema path to:

```
<schema_folder>/telpas/telpas_2026.yaml
```

That file does not exist yet, so conversion fails. The layout is **fixed-width, 1200 positions**, like 2025 — but the field structure differs from 2025 (see §"2026 deltas"), so the schema must be transcribed from the 2026 PDF rather than copied.

## Goal

Add `telpas_2026.yaml` so a 2025-2026 TELPAS file converts to an output CSV via the existing engine, reusing codebase patterns. No engine, CLI, or routing change. No regression to any existing schema or test.

## Confirmed requirements (from brainstorming)

- **Keep flags:** Mirror `telpas_2025.yaml`'s 5 identity fields (`keep: true`) **and additionally** flag the TELPAS Composite Rating plus the 4 domain Proficiency Ratings — **10 `keep: true` fields total**. All fields use `mapped_field_name: .nan` (consistent with 2025; only affects the import-only `filter_columns` path, which the default CLI does not use).
- **Deliverable:** Ship `telpas_2026.yaml` + a validation test, **and** convert the actual sample file and report real output. **Not** exposing `--filter_columns` on the CLI.

## Design

### 1. Routing & year detection — no engine change

Existing filename-based routing maps `TELPAS` → `test_name = "telpas"`. The header `0326` yields `test_month = 03`, `school_year_abbr = 26`, `full_school_year = 2026` (month < 10, so no EOC increment), loading `telpas/telpas_2026.yaml`. Verified by the existing generic `test_process_file_detects_telpas_by_filename`; no change to `processor.py` is required.

### 2. Schema authoring (`telpas_2026.yaml`)

Transcribe every field from PDF layout pages 3-17 **in document order**, covering every position 1-1200 with no gaps or overlaps. Each entry mirrors the 2025 schema shape:

```yaml
fields:
  - start: 1
    end: 4
    output_field: "Administration and Student ID Information: Administration Date"
    keep: true
    mapped_field_name: .nan
  # ... all remaining fields in order, ending at:
  - start: 1200
    end: 1200
    output_field: "Reference: Period"
    keep: false
    mapped_field_name: .nan
```

**Conventions (match `telpas_2025.yaml`):**

- `output_field` = `"<Section>: <Field Title>"`. Reuse the 2025 schema's section prefixes for shared position ranges so the two years stay diff-able. The 2025 schema's prefixes (authoritative for grouping) are: _Administration and Student ID Information_ (1-92), _Demographic Information_ (93-122), _Other Student Information_ (123-132), _Agency Use_ (133-909 — covers agency-use codes, rater info, every domain's score code / proficiency rating / scale score / item-level data, composite score & rating, yearly progress), _Crisis Codes_ (910-1000 — the TSDS PEIMS Crisis-Code field plus its trailing blank), _Historical Information TELPAS Spring &lt;year&gt; Administration_ (1001-1135), _Reference_ (1136-1200). The PDF itself only prints explicit section bands for Administration, Demographic, Other Student, Agency Use, the three Historical blocks, and Reference; the 2025 schema's finer grouping (e.g. _Crisis Codes_) is reused verbatim.
- Blank/filler runs are explicit fields named `"<Section>: Blank"` (the final position is `"Reference: Period"`).
- `mapped_field_name: .nan` on every field.
- `keep: true` on exactly these 10 (all others `keep: false`):
  - **Identity (5):** Administration Date (1-4), County-District-Campus Number (9-17), Last-Name (48-62), First-Name (63-72), PEIMS ID (74-82)
  - **Ratings (5):** Listening Proficiency Rating (263), Speaking Proficiency Rating (273), Reading Proficiency Rating (283), Writing Proficiency Rating (293), TELPAS Composite Rating (908)

**2026 deltas vs 2025** (must be applied; this is why the schema is transcribed, not copied):

- **Non-Participant split:** 2025 had two fields (`1181` Listening/Speaking, `1182` Reading/Writing). 2026 has four 1-char fields — `1181` Listening, `1182` Speaking, `1183` Reading, `1184` Writing — followed by Blank `1185-1199`, Period `1200`.
- **Historical sections relabeled** from 2025's Spring 2022/2023/2024 to Spring 2023 (1001-1045), 2024 (1046-1090), 2025 (1091-1135).
- **"Fall &lt;year&gt; TSDS PEIMS" labels advance one year** (2024 → 2025): e.g. _Crisis-Code_ (910-912) becomes "Fall 2025 TSDS PEIMS Crisis-Code", and likewise Homeless-Status, Military-Connected, Foster-Care, Dyslexia, the PEIMS CDC Number, and Student-Attribution fields. Transcribing titles verbatim from the 2026 PDF handles this automatically.
- Field titles/positions otherwise taken verbatim from the 2026 PDF.

**Construction method (recommended approach 2):** build a structured field list (2026 PDF = source of truth for `start`/`end`/title; 2025 schema = source of truth for section-prefix grouping and conventions), emit the YAML with a throwaway generator, then auto-verify before committing. Only the YAML is committed — schemas are the shipped artifact, generators are not (matches repo convention). `Field Length` from the PDF is **not** stored (derivable from `end - start + 1`).

### 3. Validation test (`tests/test_processor.py`)

Add `test_telpas_2026_default_schema_is_valid`, mirroring `test_consolidated_accountability_default_schema_is_valid`:

- Loads and `validate_yaml_config` passes (no raise).
- `fields` sorted by `start`: first `start == 1`, last `end == 1200`.
- Every position 1-1200 covered exactly once — `pairwise` check that `prev["end"] + 1 == curr["start"]` (no gaps, no overlaps).
- Assert the 10 expected `keep: true` `output_field`s are present (guards the brainstormed keep policy).

### 4. Sample conversion (acceptance, not committed)

Run the existing CLI/`process_file` on `SP_0326_TELPAS_101902_ALDINE ISD_V01.txt`, producing a full-column CSV (all ~214 columns × 22,342 rows). Report row/column counts and spot-check decoded identity + rating columns against the raw fixed-width positions (e.g. row 1: Administration Date `0326`, CDC `101902129`, Composite Rating `1`). Hand back the CSV path. This validates the schema end-to-end against real data; it does not add a committed fixture.

## Out of scope (YAGNI)

- Exposing `filter_columns` via the CLI (remains import-only, unchanged).
- Engine, routing, or `validate_yaml_config` changes (TELPAS 2026 is fixed-width, fully handled by the existing path).
- `CLAUDE.md` changes (TELPAS routing is already documented; a per-year schema adds no new logic).
- Committing the sample's converted CSV or a data fixture.
- Adding `crs`/`staar_alt` detection branches.

## Risks / notes

- **PDF transcription accuracy** across pages 3-17 (~214 fields) is the main correctness risk. Mitigated by: positions-tile-1..1200 test, field-by-field cross-check against the 2026 PDF, and decode spot-checks against the real sample file in §4.
- **CRLF line endings:** the sample's records are 1200 chars + `\r` (raw line length 1201). `pd.read_fwf` with `colspecs` ending at 1200 ignores the trailing `\r`; the Period field (1200) decodes as `.`. No special handling needed.
- **Duplicate `output_field` names** (e.g. repeated "Blank" / per-domain titles) are disambiguated by the engine's existing `_1`/`_2` uniquing — consistent with 2025 behavior.
