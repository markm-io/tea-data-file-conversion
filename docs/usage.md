# Usage Guide

This guide explains how to use the **tea-data-file-conversion** package via the command-line interface (CLI) and programmatically through the `processor` module.

---

## Command-Line Interface (CLI)

The CLI converts a TEA data file into CSV format using a dynamic YAML schema. It reads two input formats:

- **Fixed-width**, where each field occupies a fixed column range.
- **Delimited (CSV)**, where fields are identified by a header column name.

The format is inferred from the input file's extension: a file ending in `.csv` is read as delimited, and anything else is read as fixed-width. A delimited file must therefore be named with a `.csv` extension to be parsed correctly — a fixed-width read of delimited content, or vice versa, fails with an error rather than producing silently wrong output.

### Display Help

To see the available commands and options, run:

```bash
tea-data-file-conversion --help
```

### Process a Fixed-Width File

To convert a fixed-width file to CSV using a schema, use the following command:

```bash
tea-data-file-conversion input_file.txt --output_file output.csv --schema_folder path/to/schema
```

- `input_file.txt`: Path to the fixed-width input file.
- `--output_file output.csv` (optional): Path for the converted CSV file. If omitted, `_output.csv` is appended to the input filename.
- `--schema_folder path/to/schema` (optional): Path to the folder containing YAML schema files.

### Process a Delimited (CSV) File

To convert a delimited file, pass a `.csv` input the same way:

```bash
tea-data-file-conversion input_file.csv --output_file output.csv --schema_folder path/to/schema
```

Delimited files are identified differently than fixed-width ones: the test type comes from the input filename (for example, a filename containing `ACCOUNTABILITY` selects the `consolidated_accountability` schema) and the school year comes from a `YEAR` column in the file's first data row, rather than from a header prefix. The schema selected for the input must use the matching field shape — see the "YAML Schema Format" section below.

### Exporting YAML Schema Templates

To export default YAML schema templates for customization, run:

```bash
tea-data-file-conversion --export_templates --schema_folder path/to/schema_folder
```

This will copy built-in templates into the specified folder.

---

## Processor Module

If you need to integrate file conversion into a Python script, use the `processor` module.

### Processing a File Programmatically

You can use the `process_file` function to process either a fixed-width or a delimited (`.csv`) file programmatically; it infers the format from the input file's extension the same way the CLI does:

```python
from tea_data_file_conversion.processor import process_file

# Define file paths
input_file = "data/input_file.txt"  # or "data/input_file.csv" for a delimited file
output_file = "data/output_file.csv"
schema_folder = "schemas"

# Process the file
df = process_file(input_file, output_file=output_file, schema_folder=schema_folder)

print("File converted successfully!")
```

### Exporting YAML Schema Templates Programmatically

To export the built-in YAML schema templates via a script:

```python
from tea_data_file_conversion.processor import export_templates

export_templates("schemas")
```

### Generating a YAML Schema from a CSV File

If you have a CSV defining field positions, you can convert it to a YAML schema:

```python
from tea_data_file_conversion.processor import csv_to_schema_yaml

csv_to_schema_yaml("fields.csv", yaml_output_file="schema.yaml")
```

---

## YAML Schema Format

YAML configuration files define how the input file should be parsed. A schema is either fixed-width or delimited, and its fields must all use the same shape — the two are not mixed within one file.

Fixed-width fields locate data by column position:

```yaml
fields:
  - start: 1
    end: 10
    output_field: "StudentID"
    keep: true
  - start: 11
    end: 20
    output_field: "Score"
    keep: false
```

Delimited fields locate data by the column name in the input file's header, via `source_column` in place of `start`/`end`:

```yaml
fields:
  - source_column: "STU_ID"
    output_field: "StudentID"
    keep: true
  - source_column: "SCORE"
    output_field: "Score"
    keep: false
```

Both shapes support two further optional keys on each field: `keep` (a boolean; only fields marked `true` are returned when `process_file` is called with `filter_columns=True`) and `mapped_field_name` (an alternative output name used in place of `output_field` when filtering).

### Schema Validation

The `validate_yaml_config` function ensures a schema follows one of these two structures; an invalid or mixed-shape schema raises an error. Delimited schemas are additionally required to have unique `output_field` values, since `process_delimited_file` renames columns by that name and a duplicate would silently fan one source column out into several. Fixed-width schemas are exempt from that particular check because `process_fixed_width_file` de-duplicates repeated output names itself at runtime.

---

## Error Handling

If an error occurs while processing a file, ensure:

- The schema file exists at the expected path and is correctly formatted for its format (fixed-width or delimited).
- The input file follows the expected format for its extension — fixed-width for anything other than `.csv`, delimited for `.csv`.
- The schema's field shape matches the input format: a `.csv` input needs a schema whose fields use `source_column`; any other input needs a schema whose fields use `start`/`end`.
- For delimited files, a `YEAR` column is present in the data and the filename identifies a known test type (for example, contains `TELPAS` or `ACCOUNTABILITY`).

When using the processor module, wrap function calls in a try/except block:

```python
try:
    process_file("input.txt", "output.csv", schema_folder="schemas")
except Exception as e:
    print(f"Error: {e}")
```

---
