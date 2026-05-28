# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python package called `tea-data-file-conversion` that transforms fixed-width text files into CSVs using dynamic YAML schema configurations. The package is specifically designed for processing Texas Education Agency (TEA) data files with different test formats (STAAR, STAAR EOC, STAAR Alt, CRS).

## Architecture

The codebase follows a simple, focused architecture:

- **Entry Point**: `src/tea_data_file_conversion/cli.py` - Command-line interface using argparse
- **Core Processing**: `src/tea_data_file_conversion/processor.py` - Main processing logic for file conversion
- **Schema Management**: `src/tea_data_file_conversion/default_schema/` - Contains YAML schema definitions organized by test type and year
- **Package Management**: Uses `uv` for dependency management with `pyproject.toml` configuration

### Key Components

1. **Schema-Based Processing**: The system automatically detects the test type and year from the first 4 characters of input files and selects the appropriate YAML schema
2. **Dynamic Field Mapping**: YAML schemas define field boundaries, output names, and filtering rules for fixed-width files
3. **Template Export**: Built-in capability to export default schema templates for customization

## Development Commands

### Setup and Dependencies

```bash
# Install dependencies
uv sync

# Install in development mode
uv sync --dev
```

### Testing

```bash
# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=tea_data_file_conversion
```

### Code Quality

```bash
# Run linting and formatting
uv run ruff check --fix --line-length=120
uv run ruff format --line-length=120

# Run type checking
uv run mypy

# Run pre-commit hooks
pre-commit run --all-files
```

### Building and Distribution

```bash
# Build package
uv build

# Lock dependencies
uv lock
```

### Using the CLI

```bash
# Process a fixed-width file
uv run tea-data-file-conversion input_file.txt

# Export schema templates
uv run tea-data-file-conversion --export_templates --schema_folder ./schemas

# Process with custom schema folder
uv run tea-data-file-conversion input_file.txt --schema_folder ./schemas
```

## Test Type Detection Logic

The system determines test type and year from the header:

- Characters 1-2: Test month (01-12 for STAAR, 10+ for STAAR EOC)
- Characters 3-4: School year abbreviation (e.g., 25 for 2025)
- STAAR EOC files with month 10-14 have their year incremented by 1

**Currently implemented test types:** `processor.process_file` selects:

- `telpas` when "TELPAS" appears in the input filename (case-insensitive)
- `consolidated_accountability` when "ACCOUNTABILITY" appears in the input filename (case-insensitive); schemas live under `default_schema/consolidated_accountability/`
- `staar` when the header month is < 10
- `staar_eoc` otherwise

Filename-based detection runs before month-based detection, so files whose headers would otherwise collide (TELPAS spring months overlap STAAR; accountability files use the year `2025` as their header which parses as month 20) still route correctly. The `crs/` and `staar_alt/` folders under `default_schema/` ship schemas but have no detection branch — adding support requires editing `processor.py:201`.

## Known Gotchas

- **`--export_templates` is broken**: `processor.export_templates` calls `importlib_resources.path("fixedwidth_processor", ...)` with the wrong package name. Should be `tea_data_file_conversion`. Fix before relying on it.
- **`filter_columns` is not exposed via CLI**: only callable by importing `process_file` directly.
- **`csv_to_schema_yaml` helper** in `processor.py` is interactive and unlinked from the CLI — invoke from a Python REPL if needed.

## Schema Structure

YAML schemas must contain a `fields` array with objects having:

- `start`: 1-based starting position
- `end`: Ending position
- `output_field`: Column name in output CSV
- `keep`: (optional) Boolean to filter columns
- `mapped_field_name`: (optional) Alternative field name for filtering

## Configuration Notes

- Uses `ruff` for linting and formatting (line length: 120)
- Type checking configured with `mypy`
- Pre-commit hooks enforce code quality
- Semantic versioning with automatic releases via GitHub Actions
- Testing across Python 3.11-3.13 on multiple OS platforms
