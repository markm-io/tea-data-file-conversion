# Usage Guide

This guide explains how to use the **tea-data-file-conversion** package via the command-line interface (CLI) and programmatically through the `processor` module.

---

## Command-Line Interface (CLI)

The CLI provides a simple way to convert fixed-width files into CSV format using a dynamic YAML schema.

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

### Exporting YAML Schema Templates

To export default YAML schema templates for customization, run:

```bash
tea-data-file-conversion --export_templates --schema_folder path/to/schema_folder
```

This will copy built-in templates into the specified folder.

---

## Processor Module

If you need to integrate file conversion into a Python script, use the `processor` module.

### Processing a Fixed-Width File Programmatically

You can use the `process_file` function to process a file programmatically:

```python
from tea_data_file_conversion.processor import process_file

# Define file paths
input_file = "data/input_file.txt"
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

YAML configuration files define how the fixed-width file should be parsed. They follow this format:

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

### Schema Validation

The `validate_yaml_config` function ensures schemas follow this structure. If the schema is invalid, an error will be raised.

---

## Error Handling

If an error occurs while processing a file, ensure:

- The schema file exists and is correctly formatted.
- The input file follows the expected fixed-width format.

When using the processor module, wrap function calls in a try/except block:

```python
try:
    process_file("input.txt", "output.csv", schema_folder="schemas")
except Exception as e:
    print(f"Error: {e}")
```

---
