import os

import pandas as pd
import pytest

from tea_data_file_conversion.processor import (
    csv_to_schema_yaml,
    load_yaml_config,
    process_file,
    process_fixed_width_file,
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
