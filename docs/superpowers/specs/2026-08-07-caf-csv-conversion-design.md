# Consolidated Accountability File (CAF) 2025-2026 — CSV support and readable column names

**Date:** 2026-08-07
**Status:** Approved

## Problem

TEA changed the Consolidated Accountability File for the 2025-2026 school year. Two things
broke at once:

1. **The file is now a CSV, not fixed-width.** TEA's 2025-2026 format document states the
   data "will be provided in a comma separated values file format"; the delivered file is
   `DF_26_101902_Accountability_V01_07282026_dlm.csv` — 782 columns, 42,421 rows, quoted
   and comma-delimited. `process_fixed_width_file` cannot read it.

2. **The column names are TEA short codes.** The CSV header is `YEAR,REGION,…,MIGSTA,…`.
   Knowing that `MIGSTA` is the Migrant Code, or that `P2_A1_SSC` is the 2026 Spring EOC
   Algebra I scale score, requires the format PDF at hand.

The current code does not merely fail to handle the file — it crashes on it.
`process_file` reads the first line and evaluates `int(header_line[:2])` _before_ the
filename-based `ACCOUNTABILITY` branch runs. On this CSV that is `int('"Y')`, an uncaught
`ValueError`.

Separately, the existing 2024-2025 schema has its own readability problem. Its
`output_field` values are the bare Field Titles from that year's PDF, which repeat across
administrations, so `process_fixed_width_file`'s de-duplication produces `Scale Score`,
`Scale Score_1`, `Scale Score_2`, … through roughly a hundred occurrences.

## Goal

Process the 2025-2026 CAF CSV and emit a CSV whose headers are self-explanatory, and bring
the 2024-2025 fixed-width output to the same naming convention so the two years read alike.

## Source documents

| File                                                         | Pages | Table columns                                                              |
| ------------------------------------------------------------ | ----- | -------------------------------------------------------------------------- |
| `2025-2026-consolidated-accountability-file-0.pdf`           | 74    | Max Field Length, Column Header, Field Description, Note/Acceptable Values |
| `2024-2025-consolidated-accountability-file-data-format.pdf` | 41    | Start, End, Field Length, Field Title, Note                                |

The 2025-2026 document has short column codes; the 2024-2025 document does not, but both
group fields under the same administration/subject section structure, which is what makes
a single naming convention possible across both years.

Neither PDF is committed to the repository.

## Decisions

| Decision                     | Choice                                                                                   |
| ---------------------------- | ---------------------------------------------------------------------------------------- |
| Naming scheme                | Administration + Subject + Field Description                                             |
| Scope                        | Both years — new 2026 delimited schema, plus 2025 schema regenerated with the same names |
| Column mismatches at runtime | Warn on stderr and continue                                                              |
| Format detection             | Inferred from the input file extension (`.csv` → delimited)                              |
| Schema generation tooling    | Throwaway script; only the generated YAML is committed                                   |
| 2026 output column order     | Source CSV order (which is also the PDF's documented order)                              |
| `EOF` column                 | Emitted as `EOF` (the PDF describes it as "Period", which is not a usable name)          |

## Architecture

### Routing

`process_file` separates identification from parsing:

```
process_file(input_file, output_file, schema_folder, filter_columns)
  ├─ is_delimited = input_file.lower().endswith(".csv")
  ├─ identify test_name and school year:
  │    delimited   → test_name from filename (TELPAS / ACCOUNTABILITY)
  │                  year      from the YEAR column of the first data row
  │    fixed-width → unchanged: filename, then header month/year logic
  ├─ load + validate schema at
  │    <schema_folder>/<test_name>/<test_name>_<year>.yaml
  ├─ guard: field entries carry the keys the chosen path needs
  │    delimited → source_column;  fixed-width → start + end
  └─ dispatch to process_delimited_file | process_fixed_width_file
```

`process_fixed_width_file` is not modified. STAAR, STAAR EOC, TELPAS, and the 2025 CAF keep
their existing behavior.

### Year detection for delimited files

The year comes from the `YEAR` column of the first data row. All 42,421 rows of the
delivered file carry `YEAR = 2026`, so the file states its own accountability year; this
selects `consolidated_accountability_2026.yaml` with no filename parsing and no new CLI
flag. A delimited file without a `YEAR` column raises a `ValueError` naming the missing
column.

### Format detection

Format is inferred from the input file's extension rather than declared in the YAML. The
known cost is that a schema/input pairing mismatch would otherwise fail obscurely, so
`process_file` guards explicitly: before dispatching, it checks that the schema's field
entries carry the keys the chosen path requires and fails with a message naming both the
input file and the schema path if not.

### `process_delimited_file`

Reads with `pd.read_csv(input_file, dtype=str, keep_default_na=False)`.

- `dtype=str` matches the fixed-width path, which also reads everything as strings.
- `keep_default_na=False` is required for correctness, not tidiness. Without it pandas
  converts empty cells to `NaN` and coerces literal values including `NA`, `NULL`, `N/A`,
  and `NaN` into missing values. TEA codes assign meaning to blanks and use short literal
  codes, so this coercion would corrupt the data.

The function then renames columns using the schema's `source_column → output_field` map,
preserving the source CSV's column order. 782 columns in, 782 out. `keep`,
`mapped_field_name`, and `filter_columns` behave exactly as they do on the fixed-width
path.

### Schema shape

Delimited schemas replace `start`/`end` with `source_column`:

```yaml
fields:
  - source_column: MIGSTA
    output_field: "Migrant Code"
    keep: false
  - source_column: S2_A1_SSC
    output_field: "2025 Summer EOC - Algebra I - Scale Score"
    keep: false
```

Fixed-width schemas are unchanged:

```yaml
fields:
  - start: 1
    end: 4
    output_field: "Year"
    keep: false
```

The 2025 schema remains a fixed-width schema. Only its `output_field` values change.

## Naming rules

A name is `<administration> - <subject> - <field description>`, omitting levels that are
absent or suppressed.

1. **Organizational sections contribute no prefix.** General Information, Assessment
   Demographic Information, Other TSDS PEIMS Elements, and Other Student Elements have
   descriptions that are already unique. `MIGSTA → Migrant Code`.

2. **TSDS PEIMS Demographic Information is prefixed `TSDS PEIMS`.** This block duplicates
   the assessment demographic descriptions exactly, so it needs the prefix to stay
   distinct. `P_MIGSTA → TSDS PEIMS - Migrant Code`.

3. **The accountability-year parenthetical is dropped.** `(Current Accountability Year)`,
   `(Previous Accountability Year)`, and `(2-Year Prior Accountability Year)` add nothing
   the leading year does not already carry.
   `2026 Spring EOC (Current Accountability Year) → 2026 Spring EOC`.

4. **Redundant components are suppressed,** by this mechanical test: if the field
   description already contains its subject label, the subject level is omitted; if it
   already contains a season-and-year token matching its administration, the administration
   level is omitted. `S0_A1_SCODE` is described as "Algebra I Summer 2023 Score Code", which
   contains both, so it keeps that name rather than becoming
   "2024 RLA & Math EOC - Algebra I - Algebra I Summer 2023 Score Code".

5. **Descriptions are used verbatim, typographically cleaned.** Curly quotes become
   straight, en/em dashes become hyphens, and whitespace introduced by line wrapping in the
   PDF is collapsed. `Approaches Grade Level at Student's Standard`.

6. **Uniqueness is asserted at generation time.** The generator fails on any collision so it
   is resolved by hand rather than shipping a `_1` suffix. The runtime de-duplication logic
   stays as a safety net but should never fire.

### Administration prefixes (2026)

Listed in the order they appear in both the PDF and the delivered file. Counts are the
number of columns carrying each prefix and sum to 782, confirmed against the delivered
file.

| Prefix | Administration                                    | Columns |
| ------ | ------------------------------------------------- | ------: |
| —      | General / Assessment Demographic / Other elements |      47 |
| `P_`   | TSDS PEIMS                                        |      30 |
| `S2_`  | 2025 Summer EOC                                   |      78 |
| `F2_`  | 2025 Fall EOC                                     |      78 |
| `P2_`  | 2026 Spring EOC                                   |      81 |
| `S1_`  | 2024 Summer EOC                                   |      57 |
| `F1_`  | 2024 Fall EOC                                     |      57 |
| `P1_`  | 2025 Spring EOC                                   |      57 |
| `CU_`  | EOC Cumulative History                            |     116 |
| `A2_`  | 2026 Grades 3-8                                   |      71 |
| `A1_`  | 2025 Grades 3-8                                   |      27 |
| `S0_`  | 2024 RLA & Math EOC                               |       3 |
| `A0_`  | 2024 Grades 3-8                                   |      25 |
| `T2_`  | 2026 TELPAS                                       |      26 |
| `T1_`  | 2025 TELPAS                                       |      25 |
| `PM_`  | EL Performance Measure Plan                       |       4 |

Two traps worth noting: `T2_*` is the current year and `T1_*` the previous — the reverse of
what the numbering suggests at a glance — and `S0_` (2024 RLA & Math EOC) is interleaved
between `A1_` and `A0_` rather than grouped with the other EOC administrations. Names are
derived by walking the PDF's section structure rather than by decoding prefixes, so these
and similar traps are handled without anyone having to guess.

Subjects come from the subsection headers verbatim: Algebra I, Biology, English I,
English II, U.S. History; Reading Language Arts, Mathematics, Social Studies, Science;
Reading, Writing, Listening, Speaking, Composite Information.

### Examples

```
MIGSTA                 -> Migrant Code
P_MIGSTA               -> TSDS PEIMS - Migrant Code
S2_A1_SSC              -> 2025 Summer EOC - Algebra I - Scale Score
P2_A1_SSC              -> 2026 Spring EOC - Algebra I - Scale Score
F2_E2_LVL3             -> 2025 Fall EOC - English II - Masters Grade Level
T2_RE_SCODE            -> 2026 TELPAS - Reading - Score Code
CU_A1_1SUBMIT_TESTVER  -> EOC Cumulative History - Algebra I First-Time Document Submitted - Test Version
EOF                    -> EOF
```

## Schema generation

The generator is a throwaway script kept in the session scratchpad. Only the generated YAML
is committed.

It parses `pdftotext -layout` output. Field rows have the form
`<max_len> <COLUMN_HEADER> <description…>`; descriptions wrap across lines; sections and
subsections are identified by indentation; page furniture — page numbers and the repeated
`Max Field Length | Column Header | …` band — is discarded.

### Reconciliation against the delivered file

PDF text extraction is not trustworthy on its own: some table cells are clipped by the
layout, yielding truncated column headers such as `CU_A1_1SUBMIT_SUB_DAT` and
`CU_A1_1SUBMIT_SUB_CA`. The generator therefore reconciles parsed names against the actual
CSV header:

- PDF rows and CSV columns are both in document order, so they are matched positionally.
- Where the PDF name is a _prefix_ of the CSV name, the cell was clipped and the CSV name
  wins. `CU_A1_1SUBMIT_SUB_DAT → CU_A1_1SUBMIT_SUB_DATE`.
- Any non-prefix mismatch is reported for manual resolution. This is what surfaces the one
  known documentation drift: the PDF's `P_PARENTAL_DENIAL` is `P_PARENT_DENIAL` in the
  delivered file. (A separate, genuinely distinct `PARENT_DENIAL` field exists in the
  TELPAS block of both documents.)

Generation is complete when all 782 CSV columns have a name, every name is unique, and no
field is unaccounted for.

### 2025 regeneration

The 2024-2025 PDF carries explicit Start/End columns, so positions are parsed directly and
diffed against the existing 874-field schema: same field count, same positions, contiguous
coverage. Discrepancies are reported rather than silently overwritten.

Because only `output_field` values change, the 2025 _data_ output is provably unchanged —
identical `colspecs` produce identical values. Only the header row moves.

The 874 fields currently collapse to just 106 distinct names, so 825 of them collide. 93 are
`Blank` filler, which has no administration or subject to draw on and so cannot take a name
under the rules above. Those become `Blank <start>-<end>` — for example `Blank 71-90` —
which is unique, self-describing, and removes the last source of runtime `_1` suffixes. The
filler columns are still emitted, so the output's column count and order are unaffected.

## Error handling

- `validate_yaml_config` branches on schema shape. `output_field` is always required; then
  either `start` + `end` or `source_column`. Mixing the two shapes within one file is
  rejected.
- `process_file` fails immediately when a fixed-width schema is paired with a `.csv` input
  or the reverse, naming both the file and the schema path.
- A delimited file with no `YEAR` column raises a `ValueError` naming the missing column.
- A missing schema file produces a message naming the path that was searched, rather than a
  bare `FileNotFoundError`.
- Column mismatches warn on stderr and processing continues:
  - columns in the file but not the schema are emitted under their original TEA code;
  - columns in the schema but not the file are skipped.

  Each warning lists at most the first 20 names plus a total count, so a wholesale mismatch
  does not flood the terminal.

## Testing

Fixtures are small — roughly a 6-column, 3-row CSV — never the 63 MB delivered file.

- **Renaming:** columns are renamed per the schema and source order is preserved.
- **Mismatches:** an unknown file column passes through under its original name; a schema
  column absent from the file is skipped; both emit warnings.
- **Filtering:** `keep` and `filter_columns` behave on the delimited path as they do on the
  fixed-width path.
- **`keep_default_na=False`:** a cell containing `NA` remains the string `"NA"` and blanks
  remain empty. This is the subtle failure mode and gets its own test.
- **Detection:** a `.csv` input routes to the delimited path with the year read from
  `YEAR`; `.txt` behavior is unchanged; a missing `YEAR` column raises.
- **Validation:** the validator accepts both schema shapes, rejects a file that mixes them,
  and rejects a field missing `output_field`; a separate test covers the schema/input
  guard.
- **Shipped-schema integrity,** following the existing `*_default_schema_is_valid` tests:
  the 2026 schema has 782 fields with unique `source_column` and unique `output_field`
  values, and the regenerated 2025 schema has unique `output_field` values.
- **Regression:** all existing fixed-width tests pass unchanged.

## Documentation

`CLAUDE.md` needs updating in two places:

- **Test Type Detection Logic** — document extension-based format inference and
  year-from-`YEAR` for delimited files.
- **Schema Structure** — document the `source_column` field shape alongside `start`/`end`.

The `--export_templates` and `filter_columns` items already recorded under Known Gotchas
are pre-existing and out of scope here.

## Out of scope

- Fixing `export_templates`' wrong package name.
- Exposing `filter_columns` through the CLI.
- Adding detection branches for the `crs/` and `staar_alt/` schema folders.
- Committing the format PDFs or a schema-generation script to the repository.
