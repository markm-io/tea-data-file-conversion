import os
from itertools import pairwise

import pandas as pd
import pytest

from tea_data_file_conversion.processor import (
    csv_to_schema_yaml,
    load_yaml_config,
    process_delimited_file,
    process_file,
    process_fixed_width_file,
    schema_shape,
    validate_yaml_config,
)

# Existing tests remain the same...


def test_validate_yaml_config_valid():
    valid_config = {"fields": [{"start": 1, "end": 5, "output_field": "field1", "keep": True}]}
    validate_yaml_config(valid_config, "test.yaml")  # Should not raise


def test_validate_yaml_config_invalid_cases():
    cases = [
        ({}, "missing fields key"),
        ({"fields": {}}, "fields not a list"),
        ({"fields": [{"invalid": "field"}]}, "missing required keys"),
        ({"fields": [{"start": "1", "end": 5, "output_field": "field1"}]}, "start not int"),
        ({"fields": [{"start": 1, "end": "5", "output_field": "field1"}]}, "end not int"),
        ({"fields": [{"start": 1, "end": 5, "output_field": 1}]}, "output_field not str"),
        ({"fields": [{"start": 1, "end": 5, "output_field": "field1", "keep": "true"}]}, "keep not bool"),
    ]

    for config, _ in cases:
        with pytest.raises(ValueError):
            validate_yaml_config(config, "test.yaml")


def test_process_fixed_width_file(tmp_path):
    # Create a test fixed-width file
    input_data = "ABC123\nDEF456"
    input_file = tmp_path / "test.txt"
    input_file.write_text(input_data)

    config = {
        "fields": [
            {
                "start": 1,
                "end": 3,
                "output_field": "letters",
                "keep": True,
                "mapped_field_name": "letters_mapped",  # Added mapped field name
            },
            {
                "start": 4,
                "end": 6,
                "output_field": "numbers",
                "keep": False,
                "mapped_field_name": "numbers_mapped",  # Added mapped field name
            },
        ]
    }

    # Test with filter_columns=True
    df = process_fixed_width_file(str(input_file), config, filter_columns=True)
    assert list(df.columns) == ["letters_mapped"]  # Updated assertion to use mapped name

    # Test with filter_columns=False
    df = process_fixed_width_file(str(input_file), config, filter_columns=False)
    assert list(df.columns) == ["letters", "numbers"]


def test_process_file_integration(tmp_path):
    # Create test input file
    input_data = "0224ABC123\nDEF456789"
    input_file = tmp_path / "test.txt"
    input_file.write_text(input_data)

    # Create test schema folder and file
    schema_folder = tmp_path / "schemas"
    schema_folder.mkdir()
    staar_folder = schema_folder / "staar"
    staar_folder.mkdir()

    schema_content = """
    fields:
      - start: 1
        end: 3
        output_field: "field1"
        keep: true
      - start: 4
        end: 6
        output_field: "field2"
        keep: false
    """
    schema_file = staar_folder / "staar_2024.yaml"
    schema_file.write_text(schema_content)

    # Test processing
    output_file = tmp_path / "output.csv"
    df = process_file(str(input_file), str(output_file), schema_folder=str(schema_folder))
    assert os.path.exists(output_file)
    assert isinstance(df, pd.DataFrame)


def test_process_file_detects_telpas_by_filename(tmp_path):
    """A filename containing TELPAS routes to the telpas schema even when the
    header month (03) would otherwise be detected as STAAR."""
    # Header month 03 collides with STAAR's range; the filename must win.
    input_data = "0325ABCDEF\nDEF456789"
    input_file = tmp_path / "SF_0325_TELPAS_101902_TEST.txt"
    input_file.write_text(input_data)

    schema_folder = tmp_path / "schemas"
    telpas_folder = schema_folder / "telpas"
    telpas_folder.mkdir(parents=True)
    schema_content = """
    fields:
      - start: 1
        end: 4
        output_field: "telpas_admin_date"
        keep: false
      - start: 5
        end: 10
        output_field: "telpas_field"
        keep: false
    """
    (telpas_folder / "telpas_2025.yaml").write_text(schema_content)

    output_file = tmp_path / "output.csv"
    df = process_file(str(input_file), str(output_file), schema_folder=str(schema_folder))

    assert os.path.exists(output_file)
    # Columns come from the telpas schema, confirming it was selected over staar.
    assert list(df.columns) == ["telpas_admin_date", "telpas_field"]


def test_telpas_default_schema_is_valid():
    """The shipped TELPAS 2024-2025 schema validates and ends at position 1200."""
    schema_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "src",
        "tea_data_file_conversion",
        "default_schema",
        "telpas",
        "telpas_2025.yaml",
    )
    config = load_yaml_config(schema_path)
    validate_yaml_config(config, schema_path)  # Should not raise.
    assert max(field["end"] for field in config["fields"]) == 1200


def test_process_file_detects_consolidated_accountability_by_filename(tmp_path):
    """A filename containing ACCOUNTABILITY routes to the consolidated_accountability
    schema even when the header (2025 = month 20) would otherwise fall into staar_eoc."""
    # Header "2025" parses to test_month=20, which would otherwise hit the staar_eoc branch.
    input_data = "2025ABCDEF\nXYZ456789"
    input_file = tmp_path / "DF_25_101902_Accountability_V01_07212025.txt"
    input_file.write_text(input_data)

    schema_folder = tmp_path / "schemas"
    accountability_folder = schema_folder / "consolidated_accountability"
    accountability_folder.mkdir(parents=True)
    schema_content = """
    fields:
      - start: 1
        end: 4
        output_field: "accountability_year"
        keep: false
      - start: 5
        end: 10
        output_field: "accountability_field"
        keep: false
    """
    (accountability_folder / "consolidated_accountability_2025.yaml").write_text(schema_content)

    output_file = tmp_path / "output.csv"
    df = process_file(str(input_file), str(output_file), schema_folder=str(schema_folder))

    assert os.path.exists(output_file)
    # Columns come from the accountability schema, confirming it was selected over staar_eoc.
    assert list(df.columns) == ["accountability_year", "accountability_field"]
    assert df.loc[0, "accountability_year"] == "2025"


def test_consolidated_accountability_default_schema_is_valid():
    """The shipped consolidated accountability 2024-2025 schema validates and covers positions 1-2206."""
    schema_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "src",
        "tea_data_file_conversion",
        "default_schema",
        "consolidated_accountability",
        "consolidated_accountability_2025.yaml",
    )
    config = load_yaml_config(schema_path)
    validate_yaml_config(config, schema_path)  # Should not raise.
    fields = sorted(config["fields"], key=lambda f: f["start"])
    assert fields[0]["start"] == 1
    assert fields[-1]["end"] == 2206
    # Every position 1..2206 covered exactly once (no gaps, no overlaps).
    for prev, curr in pairwise(fields):
        assert prev["end"] + 1 == curr["start"], (
            f"Gap or overlap between fields ending at {prev['end']} and starting at {curr['start']}"
        )


def test_process_fixed_width_file_preserves_strings(tmp_path):
    """Verify all fields are read as strings, not auto-inferred as numeric."""
    # Row 1: numeric data in both fields. Row 2: blank second field (triggers float conversion without dtype=str).
    input_data = "ABC123\nDEF   "
    input_file = tmp_path / "test_dtype.txt"
    input_file.write_text(input_data)

    config = {
        "fields": [
            {"start": 1, "end": 3, "output_field": "letters", "keep": True},
            {"start": 4, "end": 6, "output_field": "numbers", "keep": True},
        ]
    }

    df = process_fixed_width_file(str(input_file), config)
    assert pd.api.types.is_string_dtype(df["letters"])
    assert pd.api.types.is_string_dtype(df["numbers"])
    assert df.loc[0, "numbers"] == "123"


def test_csv_to_schema_yaml(tmp_path, monkeypatch):
    # Create test CSV
    csv_content = "start,end,field_name\n1,5,Field A\n6,10,Field B"
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(csv_content)

    # Mock input function
    inputs = ["start", "end", "field_name"]
    input_iter = iter(inputs)
    monkeypatch.setattr("builtins.input", lambda _: next(input_iter))

    # Test conversion
    yaml_output = tmp_path / "output.yaml"
    csv_to_schema_yaml(str(csv_file), str(yaml_output))
    assert yaml_output.exists()

    # Verify the generated YAML
    config = load_yaml_config(str(yaml_output))
    assert "fields" in config
    assert len(config["fields"]) == 2


def test_telpas_2026_default_schema_is_valid():
    """The shipped TELPAS 2025-2026 schema validates, tiles positions 1-1200
    exactly, and flags the 10 expected keep-fields."""
    schema_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "src",
        "tea_data_file_conversion",
        "default_schema",
        "telpas",
        "telpas_2026.yaml",
    )
    config = load_yaml_config(schema_path)
    validate_yaml_config(config, schema_path)  # Should not raise.

    fields = sorted(config["fields"], key=lambda f: f["start"])
    assert fields[0]["start"] == 1
    assert fields[-1]["end"] == 1200
    # Every position 1..1200 covered exactly once (no gaps, no overlaps).
    for prev, curr in pairwise(fields):
        assert prev["end"] + 1 == curr["start"], (
            f"Gap or overlap between fields ending at {prev['end']} and starting at {curr['start']}"
        )

    # The brainstormed keep policy: exactly these 10 fields are kept.
    kept = {f["output_field"] for f in fields if f.get("keep", False)}
    expected_kept = {
        "Administration and Student ID Information: Administration Date",
        "Administration and Student ID Information: County-District-Campus Number",
        "Administration and Student ID Information: Last-Name",
        "Administration and Student ID Information: First-Name",
        "Administration and Student ID Information: PEIMS ID",
        "Agency Use: Listening Proficiency Rating",
        "Agency Use: Speaking Proficiency Rating",
        "Agency Use: Reading Proficiency Rating",
        "Agency Use: Writing Proficiency Rating",
        "Agency Use: TELPAS Composite Rating",
    }
    assert kept == expected_kept


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
    """filter_columns keeps only keep:true fields, using mapped_field_name when present.

    Output columns stay in file order (LNAME, MIGSTA), not schema order (MIGSTA, LNAME).
    """
    input_file = tmp_path / "test.csv"
    input_file.write_text('"LNAME","MIGSTA"\n"SMITH","1"\n')

    config = {
        "fields": [
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
    # File order: LNAME, MIGSTA; Schema order: MIGSTA, LNAME.
    # Output must match file order, not schema order.
    assert list(df.columns) == ["Last Name", "migrant_code"]


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

    with pytest.raises(FileNotFoundError, match=r"consolidated_accountability_2099.yaml"):
        process_file(str(input_file), str(tmp_path / "out.csv"), schema_folder=str(tmp_path))
