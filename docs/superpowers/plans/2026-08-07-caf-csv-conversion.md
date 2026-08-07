# CAF 2025-2026 CSV Conversion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Process the delimited (CSV) 2025-2026 Consolidated Accountability File and emit a CSV whose column headers are readable names instead of TEA short codes, and bring the 2024-2025 fixed-width schema to the same naming convention.

**Architecture:** `process_file` gains a second parsing path. Format is inferred from the input file's extension (`.csv` → delimited); identification is separated from parsing so the fixed-width header logic never runs on a CSV. Delimited schemas use `source_column` in place of `start`/`end`; the validator branches on that shape and `process_file` guards that the schema shape matches the input. The existing `process_fixed_width_file` is not modified.

**Tech Stack:** Python 3.11-3.13, pandas, PyYAML, pytest, ruff (line length 120), uv, pre-commit.

**Design spec:** `docs/superpowers/specs/2026-08-07-caf-csv-conversion-design.md`

## Global Constraints

- Line length 120. Run `uv run ruff check --fix --line-length=120` and `uv run ruff format --line-length=120` before every commit.
- Run tests with `uv run pytest`. All pre-existing tests must keep passing, unchanged, at every commit.
- `process_fixed_width_file` must not be modified. Its behavior for STAAR, STAAR EOC, TELPAS, and the 2025 CAF is a fixed point.
- Everything is read as strings. Delimited reads use `pd.read_csv(..., dtype=str, keep_default_na=False)`; `keep_default_na=False` is required for correctness, not tidiness — TEA assigns meaning to blanks and uses literal codes such as `NA` that pandas would otherwise coerce to `NaN`.
- Schema files live at `<schema_folder>/<test_name>/<test_name>_<year>.yaml`.
- Naming convention for `output_field`: `<administration> - <subject> - <field description>`, per the spec's six naming rules. Separator is exactly `" - "` (space, hyphen, space).
- Format PDFs are never committed. The schema generator is throwaway and lives only in the scratchpad; only generated YAML is committed.
- Source files: `/Users/markm/Downloads/Consolidated Accountability File (CAF) 2025-2026/` holds `2025-2026-consolidated-accountability-file-0.pdf` and `DF_26_101902_Accountability_V01_07282026_dlm.csv`. `/Users/markm/Downloads/2024-2025-consolidated-accountability-file-data-format.pdf` is the prior-year format document.
- Scratchpad for throwaway work: `/private/tmp/claude-501/-Users-markm-Code-production-aldineisd-tea-data-file-conversion/e453b181-473f-4c66-82ed-7ee3ac2cd05f/scratchpad`. Later tasks write `<scratchpad>` as shorthand — substitute that full path literally wherever it appears; never create a directory named `<scratchpad>`.

---

## File Structure

| File                                                                                                            | Responsibility                                         | Change                              |
| --------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------ | ----------------------------------- |
| `src/tea_data_file_conversion/processor.py`                                                                     | Schema loading/validation, both parsing paths, routing | Modify                              |
| `src/tea_data_file_conversion/default_schema/consolidated_accountability/consolidated_accountability_2026.yaml` | 782-field delimited schema                             | Create                              |
| `src/tea_data_file_conversion/default_schema/consolidated_accountability/consolidated_accountability_2025.yaml` | 874-field fixed-width schema                           | Modify (`output_field` values only) |
| `tests/test_processor.py`                                                                                       | All processor tests                                    | Modify                              |
| `CLAUDE.md`                                                                                                     | Repo guidance                                          | Modify                              |

`processor.py` is currently 351 lines and stays a single module — the codebase's established pattern, and the delimited path is small enough (~60 lines) that splitting it out would separate code that changes together.

---

### Task 1: Branch the schema validator on field shape

`validate_yaml_config` currently hard-requires `start`, `end`, and `output_field` on every field, so a delimited schema cannot validate. It must accept either shape and reject a file that mixes them.

**Files:**

- Modify: `src/tea_data_file_conversion/processor.py:49-88` (`validate_yaml_config`)
- Test: `tests/test_processor.py`

**Interfaces:**

- Consumes: nothing from earlier tasks.
- Produces:
  - `validate_yaml_config(config: dict, file_path: str) -> None` — raises `ValueError`. Same signature as today.
  - `schema_shape(config: dict) -> str` — returns `"delimited"` or `"fixed_width"` for a config that has already passed `validate_yaml_config`.
  - Module constants `DELIMITED_FIELD_KEY = "source_column"` and `FIXED_WIDTH_FIELD_KEYS = ("start", "end")`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_processor.py`. Also add `schema_shape` to the existing import block at the top of the file (`from tea_data_file_conversion.processor import (...)`).

```python
def test_validate_yaml_config_accepts_delimited_shape():
    """A delimited schema uses source_column instead of start/end."""
    config = {"fields": [{"source_column": "MIGSTA", "output_field": "Migrant Code", "keep": False}]}
    validate_yaml_config(config, "test.yaml")  # Should not raise.


def test_validate_yaml_config_rejects_mixed_shapes():
    """A schema must use one field shape throughout, not both."""
    config = {
        "fields": [
            {"start": 1, "end": 4, "output_field": "Year"},
            {"source_column": "MIGSTA", "output_field": "Migrant Code"},
        ]
    }
    with pytest.raises(ValueError, match="one shape throughout"):
        validate_yaml_config(config, "test.yaml")


def test_validate_yaml_config_delimited_invalid_cases():
    cases = [
        ({"fields": [{"source_column": 1, "output_field": "field1"}]}, "source_column not str"),
        ({"fields": [{"source_column": "A"}]}, "missing output_field"),
        ({"fields": [{"source_column": "A", "output_field": 1}]}, "output_field not str"),
        ({"fields": [{"source_column": "A", "output_field": "f", "keep": "true"}]}, "keep not bool"),
        ({"fields": []}, "empty fields list"),
    ]
    for config, _ in cases:
        with pytest.raises(ValueError):
            validate_yaml_config(config, "test.yaml")


def test_schema_shape_reports_the_declared_shape():
    fixed = {"fields": [{"start": 1, "end": 4, "output_field": "Year"}]}
    delimited = {"fields": [{"source_column": "YEAR", "output_field": "Year"}]}
    assert schema_shape(fixed) == "fixed_width"
    assert schema_shape(delimited) == "delimited"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_processor.py -k "delimited_shape or mixed_shapes or delimited_invalid or schema_shape" -v`
Expected: FAIL — `ImportError: cannot import name 'schema_shape'`.

- [ ] **Step 3: Write the implementation**

In `src/tea_data_file_conversion/processor.py`, add the constants and helpers immediately above `validate_yaml_config`, then replace `validate_yaml_config` entirely.

```python
DELIMITED_FIELD_KEY = "source_column"
FIXED_WIDTH_FIELD_KEYS = ("start", "end")


def _field_shape(field):
    """
    Determine which schema shape a single field entry uses.

    Parameters
    ----------
    field : dict
        A single entry from a schema's 'fields' list.

    Returns
    -------
    str or None
        "delimited" if the field names a source column, "fixed_width" if it
        gives both boundaries, otherwise None.
    """
    if DELIMITED_FIELD_KEY in field:
        return "delimited"
    if all(key in field for key in FIXED_WIDTH_FIELD_KEYS):
        return "fixed_width"
    return None


def schema_shape(config):
    """
    Report the shape of a schema that has already passed validation.

    Parameters
    ----------
    config : dict
        A validated schema configuration.

    Returns
    -------
    str
        Either "delimited" or "fixed_width".
    """
    return _field_shape(config["fields"][0])
```

Replace the body of `validate_yaml_config` (keep its existing docstring, updating the description to mention both shapes):

```python
def validate_yaml_config(config, file_path):
    """
    Validate the structure of the YAML configuration.

    The configuration must be a dictionary containing a key 'fields' mapping to a
    non-empty list. Every field must contain 'output_field', plus either
    'source_column' (delimited schemas) or both 'start' and 'end' (fixed-width
    schemas). A single schema must use one shape throughout.

    Parameters
    ----------
    config : dict
        The YAML configuration dictionary.
    file_path : str
        File path used for reporting in error messages.

    Raises
    ------
    ValueError
        If the configuration does not adhere to the expected schema.
    """
    if not isinstance(config, dict):
        raise ValueError(f"YAML file {file_path} should be a dictionary at the top level.")
    if "fields" not in config:
        raise ValueError(f"YAML file {file_path} is missing the required key 'fields'.")
    if not isinstance(config["fields"], list):
        raise ValueError(f"YAML file {file_path} key 'fields' should be a list.")
    if not config["fields"]:
        raise ValueError(f"YAML file {file_path} key 'fields' must not be empty.")

    shapes = set()
    for index, field in enumerate(config["fields"]):
        if not isinstance(field, dict):
            raise ValueError(f"YAML file {file_path}, field at index {index} is not a dictionary.")

        shape = _field_shape(field)
        if shape is None:
            raise ValueError(
                f"YAML file {file_path}, field at index {index} must define either "
                f"'{DELIMITED_FIELD_KEY}' (delimited) or both 'start' and 'end' (fixed width)."
            )
        shapes.add(shape)

        if "output_field" not in field:
            raise ValueError(f"YAML file {file_path}, field at index {index} is missing required key 'output_field'.")
        if not isinstance(field["output_field"], str):
            raise ValueError(f"YAML file {file_path}, field at index {index} key 'output_field' must be a string.")

        if shape == "fixed_width":
            for key in FIXED_WIDTH_FIELD_KEYS:
                if not isinstance(field[key], int):
                    raise ValueError(f"YAML file {file_path}, field at index {index} key '{key}' must be an integer.")
        elif not isinstance(field[DELIMITED_FIELD_KEY], str):
            raise ValueError(
                f"YAML file {file_path}, field at index {index} key '{DELIMITED_FIELD_KEY}' must be a string."
            )

        if "keep" in field and not isinstance(field["keep"], bool):
            raise ValueError(f"YAML file {file_path}, field at index {index} key 'keep' must be a boolean.")

    if len(shapes) > 1:
        raise ValueError(
            f"YAML file {file_path} mixes fixed-width fields ('start'/'end') and delimited fields "
            f"('{DELIMITED_FIELD_KEY}'); a schema must use one shape throughout."
        )
```

- [ ] **Step 4: Run the full test suite**

Run: `uv run pytest -v`
Expected: PASS, including the pre-existing `test_validate_yaml_config_valid` and `test_validate_yaml_config_invalid_cases`. Those still hold: a field with neither shape (`{"invalid": "field"}`) now raises the shape error, and a field with `start`/`end` present but wrongly typed still raises the integer error.

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check --fix --line-length=120
uv run ruff format --line-length=120
git add src/tea_data_file_conversion/processor.py tests/test_processor.py
git commit -m "feat: accept delimited schema shape in validate_yaml_config"
```

---

### Task 2: Add `process_delimited_file`

The core reader: rename columns per the schema, preserve the source file's column order, read everything as strings without NA coercion, and honor `keep`/`filter_columns` exactly as the fixed-width path does.

Column mismatch handling is deliberately **not** in this task — see Task 3. This task assumes the file's columns and the schema's columns match.

**Files:**

- Modify: `src/tea_data_file_conversion/processor.py` (add after `process_fixed_width_file`, which ends at line 154)
- Test: `tests/test_processor.py`

**Interfaces:**

- Consumes: `DELIMITED_FIELD_KEY` from Task 1.
- Produces: `process_delimited_file(input_file: str, schema_config: dict, filter_columns: bool = False) -> pd.DataFrame`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_processor.py`, and add `process_delimited_file` to the import block at the top of the file.

```python
def test_process_delimited_file_renames_and_preserves_order(tmp_path):
    """Columns are renamed per the schema and stay in the source file's order."""
    input_file = tmp_path / "test.csv"
    input_file.write_text('"YEAR","MIGSTA","LNAME"\n"2026","1","SMITH"\n')

    config = {
        "fields": [
            {"source_column": "MIGSTA", "output_field": "Migrant Code", "keep": False},
            {"source_column": "YEAR", "output_field": "Year", "keep": False},
            {"source_column": "LNAME", "output_field": "Last Name", "keep": False},
        ]
    }

    df = process_delimited_file(str(input_file), config)
    # Schema order is MIGSTA, YEAR, LNAME but the file's order wins.
    assert list(df.columns) == ["Year", "Migrant Code", "Last Name"]
    assert df.loc[0, "Migrant Code"] == "1"


def test_process_delimited_file_preserves_strings_and_blanks(tmp_path):
    """Everything reads as a string; blanks stay empty and literal NA stays 'NA'.

    Without keep_default_na=False, pandas turns the blank into NaN and coerces
    the literal string NA into a missing value, corrupting TEA codes.
    """
    input_file = tmp_path / "test.csv"
    input_file.write_text('"YEAR","CODE","NUM"\n"2026","NA","007"\n"2026","","012"\n')

    config = {
        "fields": [
            {"source_column": "YEAR", "output_field": "Year"},
            {"source_column": "CODE", "output_field": "Code"},
            {"source_column": "NUM", "output_field": "Number"},
        ]
    }

    df = process_delimited_file(str(input_file), config)
    assert pd.api.types.is_string_dtype(df["Code"])
    assert df.loc[0, "Code"] == "NA"
    assert df.loc[1, "Code"] == ""
    # Leading zeros survive because nothing is inferred as numeric.
    assert df.loc[0, "Number"] == "007"


def test_process_delimited_file_filter_columns(tmp_path):
    """filter_columns keeps only keep:true fields, using mapped_field_name when present."""
    input_file = tmp_path / "test.csv"
    input_file.write_text('"YEAR","MIGSTA","LNAME"\n"2026","1","SMITH"\n')

    config = {
        "fields": [
            {"source_column": "YEAR", "output_field": "Year", "keep": False},
            {
                "source_column": "MIGSTA",
                "output_field": "Migrant Code",
                "keep": True,
                "mapped_field_name": "migrant_code",
            },
            {"source_column": "LNAME", "output_field": "Last Name", "keep": True},
        ]
    }

    df = process_delimited_file(str(input_file), config, filter_columns=True)
    assert list(df.columns) == ["migrant_code", "Last Name"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_processor.py -k "process_delimited_file" -v`
Expected: FAIL — `ImportError: cannot import name 'process_delimited_file'`.

- [ ] **Step 3: Write the implementation**

Add to `src/tea_data_file_conversion/processor.py` after `process_fixed_width_file`:

```python
def process_delimited_file(input_file, schema_config, filter_columns=False):
    """
    Process a delimited (CSV) file using the provided YAML schema configuration.

    Each schema field maps a source column in the file to an output column name.
    Columns keep the order they have in the input file, which is also the order
    the TEA format document lists them in.

    Parameters
    ----------
    input_file : str
        The path to the delimited input file.
    schema_config : dict
        Schema configuration dictionary whose fields use 'source_column'.
    filter_columns : bool, optional
        If True, return only columns that are marked with "keep": true.

    Returns
    -------
    pd.DataFrame
        DataFrame with the processed data.
    """
    rename_map = {}  # Source column name -> output column name.
    keep_columns = []  # Output names of columns flagged to be retained.

    for field in schema_config["fields"]:
        # Use 'mapped_field_name' when filtering columns if available.
        if filter_columns:
            mapped_name = field.get("mapped_field_name")
            output_name = field["output_field"] if pd.isna(mapped_name) else mapped_name
        else:
            output_name = field["output_field"]
        rename_map[field[DELIMITED_FIELD_KEY]] = output_name
        if field.get("keep", False):
            keep_columns.append(output_name)

    # dtype=str matches the fixed-width path. keep_default_na=False stops pandas
    # from converting blanks to NaN and coercing literal TEA codes such as "NA".
    df = pd.read_csv(input_file, dtype=str, keep_default_na=False)

    df = df.rename(columns=rename_map)

    if filter_columns:
        df = df[keep_columns]

    return df
```

- [ ] **Step 4: Run the full test suite**

Run: `uv run pytest -v`
Expected: PASS.

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check --fix --line-length=120
uv run ruff format --line-length=120
git add src/tea_data_file_conversion/processor.py tests/test_processor.py
git commit -m "feat: add process_delimited_file for CSV input"
```

---

### Task 3: Warn and continue on schema/file column mismatches

TEA's format document and the delivered file drift — the 2025-2026 PDF documents `P_PARENTAL_DENIAL` where the file has `P_PARENT_DENIAL`. Rather than fail, emit unknown file columns under their original TEA code, skip schema columns the file lacks, and report both on stderr.

**Files:**

- Modify: `src/tea_data_file_conversion/processor.py` (`process_delimited_file`, plus two new helpers above it)
- Test: `tests/test_processor.py`

**Interfaces:**

- Consumes: `process_delimited_file` from Task 2.
- Produces:
  - `WARN_NAME_LIMIT = 20` module constant.
  - `_format_column_list(columns: list[str]) -> str`
  - `_warn_column_mismatch(unknown: list[str], missing: list[str]) -> None` — writes to stderr.
  - `process_delimited_file` signature is unchanged.

- [ ] **Step 1: Write the failing tests**

```python
def test_process_delimited_file_passes_through_unknown_columns(tmp_path, capsys):
    """A file column the schema does not know keeps its original name and warns."""
    input_file = tmp_path / "test.csv"
    input_file.write_text('"YEAR","P_PARENT_DENIAL"\n"2026","1"\n')

    config = {
        "fields": [
            {"source_column": "YEAR", "output_field": "Year"},
            {"source_column": "P_PARENTAL_DENIAL", "output_field": "TSDS PEIMS - Parental Denial"},
        ]
    }

    df = process_delimited_file(str(input_file), config)
    # Every file column is emitted; the unmatched one keeps its TEA code.
    assert list(df.columns) == ["Year", "P_PARENT_DENIAL"]

    stderr = capsys.readouterr().err
    assert "P_PARENT_DENIAL" in stderr
    assert "P_PARENTAL_DENIAL" in stderr


def test_process_delimited_file_skips_schema_columns_absent_from_file(tmp_path, capsys):
    """A schema column the file lacks is skipped, not fabricated as an empty column."""
    input_file = tmp_path / "test.csv"
    input_file.write_text('"YEAR"\n"2026"\n')

    config = {
        "fields": [
            {"source_column": "YEAR", "output_field": "Year"},
            {"source_column": "MIGSTA", "output_field": "Migrant Code"},
        ]
    }

    df = process_delimited_file(str(input_file), config)
    assert list(df.columns) == ["Year"]
    assert "MIGSTA" in capsys.readouterr().err


def test_process_delimited_file_silent_when_columns_match(tmp_path, capsys):
    """No warnings when the file and schema agree."""
    input_file = tmp_path / "test.csv"
    input_file.write_text('"YEAR"\n"2026"\n')
    config = {"fields": [{"source_column": "YEAR", "output_field": "Year"}]}

    process_delimited_file(str(input_file), config)
    assert capsys.readouterr().err == ""


def test_process_delimited_file_caps_warning_length(tmp_path, capsys):
    """A wholesale mismatch reports a count and the first 20 names, not all of them."""
    columns = [f"COL{i:03d}" for i in range(50)]
    input_file = tmp_path / "test.csv"
    input_file.write_text(",".join(columns) + "\n" + ",".join(["x"] * 50) + "\n")

    config = {"fields": [{"source_column": "YEAR", "output_field": "Year"}]}

    process_delimited_file(str(input_file), config)
    stderr = capsys.readouterr().err
    assert "50 column(s) in the file are not in the schema" in stderr
    assert "COL000" in stderr
    assert "COL019" in stderr
    assert "COL020" not in stderr
    assert "30 more" in stderr


def test_process_delimited_file_filter_columns_tolerates_missing(tmp_path):
    """filter_columns only returns keep-columns that are actually in the file."""
    input_file = tmp_path / "test.csv"
    input_file.write_text('"LNAME"\n"SMITH"\n')

    config = {
        "fields": [
            {"source_column": "LNAME", "output_field": "Last Name", "keep": True},
            {"source_column": "MIGSTA", "output_field": "Migrant Code", "keep": True},
        ]
    }

    df = process_delimited_file(str(input_file), config, filter_columns=True)
    assert list(df.columns) == ["Last Name"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_processor.py -k "unknown_columns or absent_from_file or silent_when or caps_warning or tolerates_missing" -v`
Expected: FAIL — the pass-through test fails because `rename` leaves the column named `P_PARENT_DENIAL` but nothing warns; the `filter_columns` test fails with a pandas `KeyError` on the missing `Migrant Code`.

- [ ] **Step 3: Write the implementation**

Add above `process_delimited_file` in `src/tea_data_file_conversion/processor.py`:

```python
WARN_NAME_LIMIT = 20  # Most column names to name individually in a warning.


def _format_column_list(columns):
    """
    Render a column-name list for a warning, truncated to WARN_NAME_LIMIT names.

    Parameters
    ----------
    columns : list of str
        Column names to render.

    Returns
    -------
    str
        Comma-separated names, with a trailing count if the list was truncated.
    """
    shown = ", ".join(columns[:WARN_NAME_LIMIT])
    if len(columns) > WARN_NAME_LIMIT:
        shown += f", ... ({len(columns) - WARN_NAME_LIMIT} more)"
    return shown


def _warn_column_mismatch(unknown, missing):
    """
    Report columns that the schema and the input file disagree about.

    TEA's format documents drift from the files they describe, so a mismatch is
    reported rather than treated as fatal.

    Parameters
    ----------
    unknown : list of str
        Columns present in the file but absent from the schema.
    missing : list of str
        Columns present in the schema but absent from the file.
    """
    if unknown:
        print(
            f"WARNING: {len(unknown)} column(s) in the file are not in the schema; "
            f"emitted with their original names: {_format_column_list(unknown)}",
            file=sys.stderr,
        )
    if missing:
        print(
            f"WARNING: {len(missing)} schema column(s) are not in the file; skipped: {_format_column_list(missing)}",
            file=sys.stderr,
        )
```

Then in `process_delimited_file`, replace the single `df = df.rename(columns=rename_map)` line and the `filter_columns` block with:

```python
    file_columns = list(df.columns)
    unknown = [column for column in file_columns if column not in rename_map]
    missing = [column for column in rename_map if column not in file_columns]
    _warn_column_mismatch(unknown, missing)

    df = df.rename(columns=rename_map)

    if filter_columns:
        df = df[[column for column in keep_columns if column in df.columns]]

    return df
```

- [ ] **Step 4: Run the full test suite**

Run: `uv run pytest -v`
Expected: PASS.

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check --fix --line-length=120
uv run ruff format --line-length=120
git add src/tea_data_file_conversion/processor.py tests/test_processor.py
git commit -m "feat: warn and continue on delimited schema/file column mismatches"
```

---

### Task 4: Route delimited input through `process_file`

`process_file` currently reads the first line and evaluates `int(header_line[:2])` before the filename-based branch runs, so a CSV crashes with an uncaught `ValueError` on `int('"Y')`. Separate identification from parsing, add the delimited branch, and guard that the schema's shape matches the input.

**Files:**

- Modify: `src/tea_data_file_conversion/processor.py:157-237` (`process_file`)
- Test: `tests/test_processor.py`

**Interfaces:**

- Consumes: `schema_shape` (Task 1), `process_delimited_file` (Tasks 2-3).
- Produces:
  - `_test_name_from_filename(input_file: str) -> str | None`
  - `_identify_fixed_width_file(input_file: str) -> tuple[str, int]` — `(test_name, full_school_year)`
  - `_identify_delimited_file(input_file: str) -> tuple[str, int]`
  - `process_file(input_file, output_file=None, schema_folder=None, filter_columns=False) -> pd.DataFrame` — signature unchanged.

- [ ] **Step 1: Write the failing tests**

```python
def test_process_file_routes_csv_to_delimited_path(tmp_path):
    """A .csv input uses the delimited path and takes its year from the YEAR column."""
    input_file = tmp_path / "DF_26_101902_Accountability_V01_07282026_dlm.csv"
    input_file.write_text('"YEAR","MIGSTA"\n"2026","1"\n')

    schema_folder = tmp_path / "schemas"
    accountability_folder = schema_folder / "consolidated_accountability"
    accountability_folder.mkdir(parents=True)
    (accountability_folder / "consolidated_accountability_2026.yaml").write_text(
        """
        fields:
          - source_column: YEAR
            output_field: "Year"
            keep: false
          - source_column: MIGSTA
            output_field: "Migrant Code"
            keep: false
        """
    )

    output_file = tmp_path / "output.csv"
    df = process_file(str(input_file), str(output_file), schema_folder=str(schema_folder))

    assert os.path.exists(output_file)
    assert list(df.columns) == ["Year", "Migrant Code"]
    assert df.loc[0, "Migrant Code"] == "1"


def test_process_file_delimited_requires_year_column(tmp_path):
    """Without a YEAR column the accountability year cannot be determined."""
    input_file = tmp_path / "DF_26_101902_Accountability_V01.csv"
    input_file.write_text('"REGION"\n"04"\n')

    with pytest.raises(ValueError, match="YEAR"):
        process_file(str(input_file), str(tmp_path / "out.csv"), schema_folder=str(tmp_path))


def test_process_file_delimited_requires_known_test_type(tmp_path):
    """A delimited filename with no recognized test type is an error, not a guess."""
    input_file = tmp_path / "mystery_file.csv"
    input_file.write_text('"YEAR"\n"2026"\n')

    with pytest.raises(ValueError, match="TELPAS"):
        process_file(str(input_file), str(tmp_path / "out.csv"), schema_folder=str(tmp_path))


def test_process_file_rejects_schema_shape_mismatch(tmp_path):
    """A fixed-width schema paired with a .csv input fails with a clear message."""
    input_file = tmp_path / "DF_26_101902_Accountability_V01.csv"
    input_file.write_text('"YEAR"\n"2026"\n')

    schema_folder = tmp_path / "schemas"
    accountability_folder = schema_folder / "consolidated_accountability"
    accountability_folder.mkdir(parents=True)
    (accountability_folder / "consolidated_accountability_2026.yaml").write_text(
        """
        fields:
          - start: 1
            end: 4
            output_field: "Year"
        """
    )

    with pytest.raises(ValueError, match="source_column"):
        process_file(str(input_file), str(tmp_path / "out.csv"), schema_folder=str(schema_folder))


def test_process_file_reports_missing_schema_path(tmp_path):
    """A missing schema names the path that was searched."""
    input_file = tmp_path / "DF_26_101902_Accountability_V01.csv"
    input_file.write_text('"YEAR"\n"2099"\n')

    with pytest.raises(FileNotFoundError, match="consolidated_accountability_2099.yaml"):
        process_file(str(input_file), str(tmp_path / "out.csv"), schema_folder=str(tmp_path))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/test_processor.py -k "routes_csv or requires_year or requires_known_test or shape_mismatch or missing_schema_path" -v`
Expected: FAIL — `ValueError: invalid literal for int() with base 10: '"Y'` from the current header parsing.

- [ ] **Step 3: Write the implementation**

In `src/tea_data_file_conversion/processor.py`, add these three helpers immediately above `process_file`:

```python
def _test_name_from_filename(input_file):
    """
    Determine the test type from the input filename.

    TELPAS shares STAAR's spring month range and the consolidated accountability
    file uses a year where a month is expected, so neither can be distinguished
    by header content alone.

    Parameters
    ----------
    input_file : str
        Path to the input file.

    Returns
    -------
    str or None
        The test name, or None if the filename implies no particular type.
    """
    basename_upper = os.path.basename(input_file).upper()
    if "TELPAS" in basename_upper:
        return "telpas"
    if "ACCOUNTABILITY" in basename_upper:
        return "consolidated_accountability"
    return None


def _identify_fixed_width_file(input_file):
    """
    Determine the test type and school year for a fixed-width input file.

    Parameters
    ----------
    input_file : str
        Path to the fixed-width input file.

    Returns
    -------
    tuple of (str, int)
        The test name and the full school year.

    Raises
    ------
    ValueError
        If the header line is too short to identify.
    """
    with open(input_file) as f:
        header_line = f.readline().strip()

    if len(header_line) < 4:
        raise ValueError("The header line must contain at least 4 characters.")

    # Extract test month and abbreviated school year from header.
    header = header_line[:4]
    test_month = int(header[:2])
    full_school_year = 2000 + int(header[2:4])

    # Filename-based detection runs first so files whose headers would otherwise
    # collide still route correctly.
    test_name = _test_name_from_filename(input_file)
    if test_name is not None:
        return test_name, full_school_year
    if test_month < 10:
        return "staar", full_school_year
    if test_month < 15:
        full_school_year += 1
    return "staar_eoc", full_school_year


def _identify_delimited_file(input_file):
    """
    Determine the test type and school year for a delimited input file.

    The year comes from the file's own YEAR column rather than from the header
    or the filename.

    Parameters
    ----------
    input_file : str
        Path to the delimited input file.

    Returns
    -------
    tuple of (str, int)
        The test name and the full school year.

    Raises
    ------
    ValueError
        If the test type cannot be determined, or the YEAR column is absent,
        empty, or not a year.
    """
    test_name = _test_name_from_filename(input_file)
    if test_name is None:
        raise ValueError(
            f"Cannot determine the test type for {input_file}; the filename must contain "
            f"'TELPAS' or 'ACCOUNTABILITY'."
        )

    # Only the first data row is needed, so the rest of the file is not read.
    header = pd.read_csv(input_file, nrows=1, dtype=str, keep_default_na=False)
    if "YEAR" not in header.columns:
        raise ValueError(
            f"Delimited file {input_file} has no 'YEAR' column, so its accountability year cannot be determined."
        )
    if header.empty:
        raise ValueError(f"Delimited file {input_file} has a header row but no data rows.")

    year_value = header.loc[0, "YEAR"]
    try:
        full_school_year = int(year_value)
    except (TypeError, ValueError) as ve:
        raise ValueError(f"Delimited file {input_file} has a 'YEAR' value of {year_value!r}, which is not a year.") from ve

    return test_name, full_school_year
```

Then replace the body of `process_file` from the `# Read and validate the header line.` comment (line 187) through `return df` (line 237) with:

```python
    # Format is inferred from the extension; identification must not assume
    # fixed-width, because a CSV header line has no month/year to parse.
    is_delimited = input_file.lower().endswith(".csv")
    if is_delimited:
        test_name, full_school_year = _identify_delimited_file(input_file)
    else:
        test_name, full_school_year = _identify_fixed_width_file(input_file)

    # Compose the path to the expected YAML schema file.
    base_folder = schema_folder if schema_folder is not None else "default_schema"
    schema_config_file = os.path.join(base_folder, test_name, f"{test_name}_{full_school_year}.yaml")
    print(f"Loading schema config: {schema_config_file}")

    if not os.path.isfile(schema_config_file):
        raise FileNotFoundError(
            f"No schema found for {test_name} {full_school_year}; expected it at {schema_config_file}."
        )

    # Load and validate the YAML configuration.
    schema_config = load_yaml_config(schema_config_file)
    try:
        validate_yaml_config(schema_config, schema_config_file)
    except ValueError as ve:
        print(f"YAML validation error: {ve}")
        sys.exit(1)

    # The schema's shape must match the input's format, or parsing fails obscurely.
    expected_shape = "delimited" if is_delimited else "fixed_width"
    if schema_shape(schema_config) != expected_shape:
        raise ValueError(
            f"Input file {input_file} is {expected_shape}, but schema {schema_config_file} is not. "
            f"A .csv input needs a schema whose fields use 'source_column'; any other input needs "
            f"a schema whose fields use 'start' and 'end'."
        )

    # Process the file using the loaded schema.
    if is_delimited:
        df = process_delimited_file(input_file, schema_config, filter_columns=filter_columns)
    else:
        df = process_fixed_width_file(input_file, schema_config, skip_header=True, filter_columns=filter_columns)

    # Write the processed data to a CSV file.
    df.to_csv(output_file, index=False)
    print(f"Data has been written to {output_file}")
    return df
```

Also update `process_file`'s docstring: it currently says "Process an input fixed-width file"; change to "Process an input fixed-width or delimited file and output a CSV file", and note that format is inferred from the input file extension.

- [ ] **Step 4: Run the full test suite**

Run: `uv run pytest -v`
Expected: PASS. The pre-existing `test_process_file_integration`, `test_process_file_detects_telpas_by_filename`, and `test_process_file_detects_consolidated_accountability_by_filename` all use `.txt` inputs and must be unaffected.

- [ ] **Step 5: Lint and commit**

```bash
uv run ruff check --fix --line-length=120
uv run ruff format --line-length=120
git add src/tea_data_file_conversion/processor.py tests/test_processor.py
git commit -m "feat: route .csv input through the delimited path in process_file"
```

---

### Task 5: Generate the 2025-2026 delimited schema

Produce `consolidated_accountability_2026.yaml`: 782 fields, one per column of the delivered CSV, in file order, with Admin + Subject + Description names.

The generator is throwaway and lives in the scratchpad. Only the YAML is committed.

**Files:**

- Create: `src/tea_data_file_conversion/default_schema/consolidated_accountability/consolidated_accountability_2026.yaml`
- Create (scratchpad, not committed): `<scratchpad>/generate_caf_2026.py`
- Test: `tests/test_processor.py`

**Interfaces:**

- Consumes: `load_yaml_config`, `validate_yaml_config` (Task 1).
- Produces: a delimited schema whose fields are `{source_column, output_field, keep: false}`. `keep` is `false` for every field — no filtering policy has been requested for this file, matching the 2025 schema.

- [ ] **Step 1: Extract the PDF text**

```bash
cd "/Users/markm/Downloads/Consolidated Accountability File (CAF) 2025-2026"
pdftotext -layout 2025-2026-consolidated-accountability-file-0.pdf \
  "<scratchpad>/caf2026.txt"
```

Expected: a 4150-line text file.

- [ ] **Step 2: Write the generator**

Create `<scratchpad>/generate_caf_2026.py`. It must implement exactly this:

**Parsing.** Walk `caf2026.txt` line by line, tracking the current administration section and subject subsection.

- A _field row_ matches `^\s*(\d+)\s+([A-Z][A-Z0-9_]*)\s+(.*)$` — max length, column header, start of description. Note the separator can be a single space (`P_PARENTAL_PERMISSION Parental Permission`), so do not require two.
- A field row's description continues on following lines that are indented into the description column and are not themselves field rows or headers. Join wrapped fragments with a single space.
- The description column ends where the "Note/Acceptable Values" column begins. Determine the note column's start offset from the `Max Field Column Header   Field Description   Note/Acceptable Values` band that repeats on each page, and slice each line at that offset so acceptable-values text never leaks into a description.
- A _section header_ is a line indented between 22 and 50 columns that is not a field row. Administration sections are the ones listed in the spec's prefix table; subject subsections are the ones listed in the spec's naming section.
- Discard page furniture: bare page numbers, and the repeating `Max Field Length | Column Header | Field Description | Note/Acceptable Values` band.

**Naming.** Apply the spec's six rules. Concretely:

- Suppress administration prefixes for General Information, Assessment Demographic Information, Other TSDS PEIMS Elements, Other Student Elements.
- Map TSDS PEIMS Demographic Information to the prefix `TSDS PEIMS`.
- Strip ` (Current Accountability Year)`, ` (Previous Accountability Year)`, ` (2-Year Prior Accountability Year)` from administration labels.
- Omit the subject level when the description already contains the subject label; omit the administration level when the description already contains a matching season-and-year token.
- Clean descriptions: replace `‘’` with `'`, `“”` with `"`, `‐–—` with `-`, and collapse runs of whitespace.
- Join surviving levels with `" - "`.
- Emit `EOF` as the literal name `EOF` (the document calls it "Period", which is not usable as a column name).

**Reconciliation.** Read the delivered CSV's 782-column header. Match PDF rows to CSV columns positionally, since both are in document order.

- If the names are equal, accept.
- If the PDF name is a _prefix_ of the CSV name, the PDF table cell was clipped — accept the CSV name. This is how `CU_A1_1SUBMIT_SUB_DAT` becomes `CU_A1_1SUBMIT_SUB_DATE`.
- Otherwise, print the position and both names and stop. Resolve by hand, then re-run. The one known case is the PDF's `P_PARENTAL_DENIAL` against the file's `P_PARENT_DENIAL`; take the file's name.

**Output.** Write YAML with `yaml.dump(data, f, sort_keys=False)`, matching the existing schema files' style: a top-level `fields` list of `{source_column, output_field, keep}`.

Start from this skeleton. The regexes, lookup tables, and reconciliation logic are correct as written; the parsing loop's handling of wrapped descriptions is the part expected to need iteration.

```python
"""Throwaway generator for consolidated_accountability_2026.yaml. Not committed."""

import csv
import re
import sys

import yaml

CAF_DIR = "/Users/markm/Downloads/Consolidated Accountability File (CAF) 2025-2026"
PDF_TEXT = "<scratchpad>/caf2026.txt"
CSV_FILE = f"{CAF_DIR}/DF_26_101902_Accountability_V01_07282026_dlm.csv"
OUT_YAML = (
    "src/tea_data_file_conversion/default_schema/consolidated_accountability/consolidated_accountability_2026.yaml"
)

# A field row: max length, column header, then the start of the description.
# The separator may be a single space, so do not require two.
FIELD_ROW = re.compile(r"^\s*(\d+)\s+([A-Z][A-Z0-9_]*)\s+(.*)$")
# The band repeated at the top of every page; used to locate the Note column.
BAND = re.compile(r"^\s*Max Field\s+Column Header\s+Field Description\s+(Note/Acceptable Values)")

# Administration sections that contribute no prefix (naming rule 1).
SUPPRESSED_SECTIONS = {
    "General Information",
    "Assessment Demographic Information",
    "Other TSDS PEIMS Elements",
    "Other Student Elements",
}
# Naming rule 2.
SECTION_PREFIX_OVERRIDES = {"TSDS PEIMS Demographic Information": "TSDS PEIMS"}
# Naming rule 3.
YEAR_QUALIFIERS = re.compile(
    r"\s*\((?:Current|Previous|2-Year Prior) Accountability Year\)\s*$"
)
SUBJECTS = {
    "Algebra I", "Biology", "English I", "English II", "U.S. History",
    "Reading Language Arts", "Mathematics", "Social Studies", "Science",
    "Reading", "Writing", "Listening", "Speaking", "Composite Information",
}
SEASONS = ("Summer", "Fall", "Spring")


def clean(text):
    """Apply naming rule 5: normalize typography and collapse wrap whitespace."""
    for src, dst in (("‘", "'"), ("’", "'"), ("“", '"'), ("”", '"'),
                     ("‐", "-"), ("–", "-"), ("—", "-")):
        text = text.replace(src, dst)
    return re.sub(r"\s+", " ", text).strip()


def build_name(section, subject, description):
    """Join the levels per naming rules 1-4, with ' - ' between them."""
    description = clean(description)
    levels = []

    if section and section not in SUPPRESSED_SECTIONS:
        label = SECTION_PREFIX_OVERRIDES.get(section, YEAR_QUALIFIERS.sub("", section))
        # Rule 4: skip the administration when the description already carries it.
        season_year = any(
            season in description and any(str(y) in description for y in range(2020, 2031))
            for season in SEASONS
        )
        if not season_year:
            levels.append(label)

    # Rule 4: skip the subject when the description already names it.
    if subject and subject not in description:
        levels.append(subject)

    levels.append(description)
    return " - ".join(levels)


def parse_pdf(path):
    """Yield (column_header, section, subject, description) in document order."""
    raise NotImplementedError("Implement the section/subsection walk described above.")


def reconcile(parsed, csv_columns):
    """Match parsed rows to the delivered file's columns, position for position."""
    if len(parsed) != len(csv_columns):
        sys.exit(f"Parsed {len(parsed)} rows but the file has {len(csv_columns)} columns.")

    resolved = []
    for index, (row, actual) in enumerate(zip(parsed, csv_columns, strict=True)):
        parsed_name = row[0]
        if parsed_name == actual:
            resolved.append(actual)
        elif actual.startswith(parsed_name):
            # The PDF table cell was clipped; the delivered file is authoritative.
            print(f"  clipped at {index}: {parsed_name!r} -> {actual!r}")
            resolved.append(actual)
        else:
            sys.exit(f"Unresolved mismatch at column {index}: PDF {parsed_name!r} vs file {actual!r}")
    return resolved


def main():
    with open(CSV_FILE, newline="") as f:
        csv_columns = next(csv.reader(f))

    parsed = list(parse_pdf(PDF_TEXT))
    source_columns = reconcile(parsed, csv_columns)

    fields = []
    for source_column, (_, section, subject, description) in zip(source_columns, parsed, strict=True):
        output_field = "EOF" if source_column == "EOF" else build_name(section, subject, description)
        fields.append({"source_column": source_column, "output_field": output_field, "keep": False})

    names = [field["output_field"] for field in fields]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        sys.exit(f"Duplicate output_field values, resolve before writing: {duplicates}")

    with open(OUT_YAML, "w") as f:
        yaml.dump({"fields": fields}, f, sort_keys=False)
    print(f"Wrote {len(fields)} fields to {OUT_YAML}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the generator until it is clean**

```bash
uv run python "<scratchpad>/generate_caf_2026.py"
```

Iterate until it reports all of:

- 782 fields emitted, in the delivered file's column order;
- every `source_column` matches the CSV header exactly, position for position;
- every `output_field` is unique;
- no unresolved reconciliation mismatches.

- [ ] **Step 4: Write the schema test**

Add to `tests/test_processor.py`:

```python
def test_consolidated_accountability_2026_default_schema_is_valid():
    """The shipped 2025-2026 schema is a delimited schema covering all 782 columns
    of the delivered file with unique source and output names."""
    schema_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "src",
        "tea_data_file_conversion",
        "default_schema",
        "consolidated_accountability",
        "consolidated_accountability_2026.yaml",
    )
    config = load_yaml_config(schema_path)
    validate_yaml_config(config, schema_path)  # Should not raise.
    assert schema_shape(config) == "delimited"

    fields = config["fields"]
    assert len(fields) == 782

    source_columns = [field["source_column"] for field in fields]
    assert len(set(source_columns)) == 782, "duplicate source_column values"

    output_fields = [field["output_field"] for field in fields]
    assert len(set(output_fields)) == 782, "duplicate output_field values"

    # Document order is preserved: the delivered file's first and last columns.
    assert source_columns[0] == "YEAR"
    assert source_columns[-1] == "EOF"

    # Naming anchors, one per rule in the design spec.
    by_source = dict(zip(source_columns, output_fields, strict=True))
    assert by_source["MIGSTA"] == "Migrant Code"
    assert by_source["P_MIGSTA"] == "TSDS PEIMS - Migrant Code"
    assert by_source["S2_A1_SSC"] == "2025 Summer EOC - Algebra I - Scale Score"
    assert by_source["P2_A1_SSC"] == "2026 Spring EOC - Algebra I - Scale Score"
    assert by_source["F2_E2_LVL3"] == "2025 Fall EOC - English II - Masters Grade Level"
    assert by_source["T2_RE_SCODE"] == "2026 TELPAS - Reading - Score Code"
    assert by_source["EOF"] == "EOF"

    # The one known drift between the format document and the delivered file.
    assert "P_PARENT_DENIAL" in by_source
    assert "P_PARENTAL_DENIAL" not in by_source
```

- [ ] **Step 5: Run the test**

Run: `uv run pytest tests/test_processor.py::test_consolidated_accountability_2026_default_schema_is_valid -v`
Expected: PASS. If a naming anchor fails, fix the generator's rules and regenerate — do not edit the YAML by hand except for reconciliation mismatches the generator explicitly reports.

- [ ] **Step 6: Run the full suite, lint, and commit**

```bash
uv run pytest -v
uv run ruff check --fix --line-length=120
uv run ruff format --line-length=120
git add src/tea_data_file_conversion/default_schema/consolidated_accountability/consolidated_accountability_2026.yaml tests/test_processor.py
git commit -m "feat: add 2025-2026 consolidated accountability delimited schema"
```

---

### Task 6: Retrofit the 2024-2025 schema's names

The existing 874-field schema's 874 `output_field` values collapse to only 106 distinct names, so `process_fixed_width_file` appends `_1`, `_2`, … suffixes at runtime. Regenerate the names from the 2024-2025 format PDF using the same convention.

Only `output_field` values change. `start`, `end`, and `keep` stay exactly as they are, so the _data_ output is unchanged — identical `colspecs` produce identical values, and only the header row moves.

93 of the 874 fields are `Blank` filler, which cannot take an Admin + Subject + Description name. Name those `Blank <start>-<end>` (for example `Blank 71-90`) — unique, self-describing, and it removes the last source of runtime `_1` suffixes.

**Files:**

- Modify: `src/tea_data_file_conversion/default_schema/consolidated_accountability/consolidated_accountability_2025.yaml`
- Create (scratchpad, not committed): `<scratchpad>/retrofit_caf_2025.py`
- Test: `tests/test_processor.py`

**Interfaces:**

- Consumes: `load_yaml_config`, `validate_yaml_config` (Task 1).
- Produces: no new code interfaces. The schema stays fixed-width.

- [ ] **Step 1: Extract the PDF text**

```bash
cd /Users/markm/Downloads
pdftotext -layout 2024-2025-consolidated-accountability-file-data-format.pdf \
  "<scratchpad>/caf2025.txt"
```

This document's table is `Start | End | Field Length | Field Title | Note` — it has explicit positions and no short column codes, unlike the 2025-2026 document.

- [ ] **Step 2: Write the retrofit script**

Create `<scratchpad>/retrofit_caf_2025.py`.

**Parsing.** A field row matches `^\s*(\d+)\s+(\d+)\s+(\d+)\s+(.*)$` — start, end, field length, field title. Track administration sections and subject subsections by indentation exactly as in Task 5. Descriptions wrap across lines; join with a single space and slice off the Note column.

**Verification before writing anything.** Load the existing schema and assert against the parsed PDF:

- same field count (874);
- identical `(start, end)` sequence, position for position.

If either check fails, print the first ten differing rows and stop. Do not overwrite the schema on a position mismatch — the existing positions are load-bearing and covered by `test_consolidated_accountability_default_schema_is_valid`.

**Naming.** Apply the same six rules and the same cleaning as Task 5. Additionally, any field whose title is `Blank` becomes `Blank <start>-<end>`.

**Output.** Rewrite only the `output_field` value of each field, preserving `start`, `end`, `keep`, and `mapped_field_name` byte-for-byte in their existing order and style.

Start from this skeleton. `build_name` and `clean` are imported from the Task 5 generator, so keep both scripts in the scratchpad together.

```python
"""Throwaway retrofit for consolidated_accountability_2025.yaml names. Not committed."""

import re
import sys

import yaml

from generate_caf_2026 import build_name  # Same six naming rules.

PDF_TEXT = "<scratchpad>/caf2025.txt"
SCHEMA = (
    "src/tea_data_file_conversion/default_schema/consolidated_accountability/consolidated_accountability_2025.yaml"
)

# This document's table is Start | End | Field Length | Field Title | Note.
FIELD_ROW = re.compile(r"^\s*(\d+)\s+(\d+)\s+(\d+)\s+(.*)$")


def parse_pdf(path):
    """Yield (start, end, section, subject, title) in document order."""
    raise NotImplementedError("Implement the section/subsection walk described above.")


def main():
    parsed = list(parse_pdf(PDF_TEXT))
    config = yaml.safe_load(open(SCHEMA))
    fields = config["fields"]

    # Verify before touching anything: the positions are load-bearing.
    if len(parsed) != len(fields):
        sys.exit(f"PDF has {len(parsed)} rows but the schema has {len(fields)} fields.")

    mismatches = [
        (index, (row[0], row[1]), (field["start"], field["end"]))
        for index, (row, field) in enumerate(zip(parsed, fields, strict=True))
        if (row[0], row[1]) != (field["start"], field["end"])
    ]
    if mismatches:
        for index, pdf_pos, schema_pos in mismatches[:10]:
            print(f"  field {index}: PDF {pdf_pos} vs schema {schema_pos}")
        sys.exit(f"{len(mismatches)} position mismatches; not overwriting the schema.")

    for field, (start, end, section, subject, title) in zip(fields, parsed, strict=True):
        if title.strip() == "Blank":
            field["output_field"] = f"Blank {start}-{end}"
        else:
            field["output_field"] = build_name(section, subject, title)

    names = [field["output_field"] for field in fields]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        sys.exit(f"Duplicate output_field values, resolve before writing: {duplicates}")

    with open(SCHEMA, "w") as f:
        yaml.dump(config, f, sort_keys=False)
    print(f"Renamed {len(fields)} fields; positions unchanged.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Run the retrofit until it is clean**

```bash
uv run python "<scratchpad>/retrofit_caf_2025.py"
```

Iterate until it reports 874 fields, positions identical to the existing schema, and 874 unique `output_field` values.

- [ ] **Step 4: Write the schema test**

Add to `tests/test_processor.py`:

```python
def test_consolidated_accountability_2025_output_fields_are_unique():
    """After the naming retrofit every 2024-2025 field has a distinct name, so
    process_fixed_width_file never appends a _1 suffix at runtime."""
    schema_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "src",
        "tea_data_file_conversion",
        "default_schema",
        "consolidated_accountability",
        "consolidated_accountability_2025.yaml",
    )
    config = load_yaml_config(schema_path)
    fields = config["fields"]
    assert len(fields) == 874

    output_fields = [field["output_field"] for field in fields]
    counts = Counter(output_fields)
    duplicates = sorted(name for name, count in counts.items() if count > 1)
    assert duplicates == [], f"duplicate output_field values: {duplicates}"

    # Naming anchors matching the 2026 convention.
    by_position = {(field["start"], field["end"]): field["output_field"] for field in fields}
    assert by_position[(1, 4)] == "Year"
    assert by_position[(71, 90)] == "Blank 71-90"
```

Add `from collections import Counter` to the imports at the top of `tests/test_processor.py`.

- [ ] **Step 5: Run the tests**

Run: `uv run pytest tests/test_processor.py -k "consolidated_accountability" -v`
Expected: PASS, including the pre-existing `test_consolidated_accountability_default_schema_is_valid`, which asserts the schema still tiles positions 1-2206 with no gaps or overlaps. That test passing is the proof that only names changed.

- [ ] **Step 6: Run the full suite, lint, and commit**

```bash
uv run pytest -v
uv run ruff check --fix --line-length=120
uv run ruff format --line-length=120
git add src/tea_data_file_conversion/default_schema/consolidated_accountability/consolidated_accountability_2025.yaml tests/test_processor.py
git commit -m "refactor: rename 2024-2025 accountability fields to the readable convention"
```

---

### Task 7: Verify end-to-end on the delivered file and update docs

Everything so far is tested against fixtures of a few columns. This task runs the real 63 MB, 782-column, 42,421-row file through the CLI and confirms the output is what the spec promised, then documents the new path.

**Files:**

- Modify: `CLAUDE.md`
- No source changes expected. If the real file exposes a defect, fix it here with a test that reproduces it first.

**Interfaces:**

- Consumes: everything from Tasks 1-6.
- Produces: nothing new.

- [ ] **Step 1: Run the CLI against the delivered file**

```bash
cd /Users/markm/Code/production/aldineisd/tea-data-file-conversion
uv run tea-data-file-conversion \
  "/Users/markm/Downloads/Consolidated Accountability File (CAF) 2025-2026/DF_26_101902_Accountability_V01_07282026_dlm.csv" \
  --output_file "<scratchpad>/caf2026_output.csv" \
  --schema_folder src/tea_data_file_conversion/default_schema
```

Expected: prints the schema path, no warnings on stderr, and `Data has been written to …`. Note that the output goes to the scratchpad — it is roughly the size of the input and must not land in the repo.

- [ ] **Step 2: Verify the output**

```bash
uv run python - <<'PY'
import csv

src = "/Users/markm/Downloads/Consolidated Accountability File (CAF) 2025-2026/DF_26_101902_Accountability_V01_07282026_dlm.csv"
out = "<scratchpad>/caf2026_output.csv"

with open(src, newline="") as f:
    reader = csv.reader(f)
    src_header = next(reader)
    src_rows = sum(1 for _ in reader)

with open(out, newline="") as f:
    reader = csv.reader(f)
    out_header = next(reader)
    out_rows = sum(1 for _ in reader)

assert len(out_header) == 782, len(out_header)
assert out_rows == src_rows == 42421, (out_rows, src_rows)
assert len(set(out_header)) == 782, "duplicate output headers"
assert not any(h.endswith(("_1", "_2", "_3")) for h in out_header), "runtime de-duplication fired"

by_src = dict(zip(src_header, out_header, strict=True))
assert by_src["MIGSTA"] == "Migrant Code"
assert by_src["P2_A1_SSC"] == "2026 Spring EOC - Algebra I - Scale Score"
assert by_src["T2_RE_SCODE"] == "2026 TELPAS - Reading - Score Code"
print("OK:", out_rows, "rows,", len(out_header), "columns")
PY
```

Expected: `OK: 42421 rows, 782 columns`.

- [ ] **Step 3: Verify the 2025 retrofit changed only headers**

There is no 2024-2025 `.txt` sample on hand, so verify structurally instead: the schema's `(start, end)` pairs are unchanged, which is what determines every value the fixed-width reader produces.

```bash
uv run python - <<'PY'
import subprocess
import yaml

path = "src/tea_data_file_conversion/default_schema/consolidated_accountability/consolidated_accountability_2025.yaml"
before = yaml.safe_load(subprocess.run(["git", "show", f"main:{path}"], capture_output=True, text=True, check=True).stdout)
after = yaml.safe_load(open(path))

pos_before = [(f["start"], f["end"], f.get("keep", False)) for f in before["fields"]]
pos_after = [(f["start"], f["end"], f.get("keep", False)) for f in after["fields"]]
assert pos_before == pos_after, "positions or keep flags changed - data output would change"
print("OK: positions and keep flags identical;", sum(
    1 for a, b in zip(before["fields"], after["fields"], strict=True)
    if a["output_field"] != b["output_field"]
), "names changed")
PY
```

Expected: positions identical, with a large number of names changed.

- [ ] **Step 4: Update CLAUDE.md**

Two edits.

In the **Test Type Detection Logic** section, after the existing paragraph about filename-based detection, add:

```markdown
**File format detection:** the input file's extension selects the parsing path.
A `.csv` input is read as delimited (`processor.process_delimited_file`); anything
else is read as fixed-width (`processor.process_fixed_width_file`). For delimited
files the school year comes from the `YEAR` column of the first data row rather
than from a header prefix, and the filename must identify the test type. The
schema's field shape must match the input's format — `process_file` raises if a
`.csv` is paired with a `start`/`end` schema or vice versa.

Columns that the schema and the delimited file disagree about are reported on
stderr and processing continues: file columns absent from the schema are emitted
under their original TEA code, and schema columns absent from the file are
skipped. TEA's format documents drift from the files they describe — the
2025-2026 document specifies `P_PARENTAL_DENIAL` where the file has
`P_PARENT_DENIAL`.
```

In the **Schema Structure** section, replace the existing field list with:

```markdown
YAML schemas must contain a `fields` array. A schema is either fixed-width or
delimited and cannot mix the two shapes.

Fixed-width fields:

- `start`: 1-based starting position
- `end`: Ending position
- `output_field`: Column name in output CSV
- `keep`: (optional) Boolean to filter columns
- `mapped_field_name`: (optional) Alternative field name for filtering

Delimited fields:

- `source_column`: Column name as it appears in the input file's header
- `output_field`: Column name in output CSV
- `keep`: (optional) Boolean to filter columns
- `mapped_field_name`: (optional) Alternative field name for filtering

Consolidated accountability schemas name their output fields
`<administration> - <subject> - <field description>`, for example
`2026 Spring EOC - Algebra I - Scale Score`. See
`docs/superpowers/specs/2026-08-07-caf-csv-conversion-design.md` for the
naming rules.
```

Also update the **Currently implemented test types** list to note that `consolidated_accountability` covers both the 2025 fixed-width file and the 2026 delimited file.

- [ ] **Step 5: Run the full suite, lint, and commit**

```bash
uv run pytest -v
uv run ruff check --fix --line-length=120
uv run ruff format --line-length=120
pre-commit run --all-files
git add CLAUDE.md
git commit -m "docs: document delimited input handling and schema shapes"
```

- [ ] **Step 6: Clean up**

Confirm no large artifacts were left in the repo:

```bash
git status --short
du -sh "<scratchpad>/caf2026_output.csv"
```

Expected: `git status` shows only the pre-existing `pyproject.toml` and `uv.lock` modifications; the generated output CSV lives in the scratchpad only.

---

## Verification Summary

At completion:

- `uv run pytest` passes, with every pre-existing test unmodified.
- The delivered 2025-2026 CSV converts to 782 uniquely-named columns across 42,421 rows with no warnings.
- The 2024-2025 schema produces 874 uniquely-named columns from unchanged field positions.
- No `_1`/`_2` suffixes appear in either output.
- `process_fixed_width_file` is byte-for-byte unchanged.
