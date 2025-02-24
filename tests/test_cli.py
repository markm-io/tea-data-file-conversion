import sys

import pytest

# Import the cli module. Make sure your PYTHONPATH is set correctly.
from tea_data_file_conversion import cli


# Define dummy functions to replace export_templates and process_file.
def dummy_export_templates(schema_folder):
    dummy_export_templates.called = True
    dummy_export_templates.schema_folder = schema_folder


dummy_export_templates.called = False
dummy_export_templates.schema_folder = None


def dummy_process_file(input_file, output_file, schema_folder):
    dummy_process_file.called = True
    dummy_process_file.args = (input_file, output_file, schema_folder)


dummy_process_file.called = False
dummy_process_file.args = None


# A fixture to patch the functions in the cli module before each test.
@pytest.fixture(autouse=True)
def patch_cli_functions(monkeypatch):
    monkeypatch.setattr(cli, "export_templates", dummy_export_templates)
    monkeypatch.setattr(cli, "process_file", dummy_process_file)
    # Reset our dummy function flags
    dummy_export_templates.called = False
    dummy_export_templates.schema_folder = None
    dummy_process_file.called = False
    dummy_process_file.args = None


# Test running the CLI without the --export_templates flag.
def test_main_without_export_templates():
    test_input = "dummy_input.txt"
    test_output = "dummy_output.csv"
    test_schema = "dummy_schema"
    sys.argv = [
        "cli.py",
        test_input,
        "--output_file",
        test_output,
        "--schema_folder",
        test_schema,
    ]
    cli.main()
    # export_templates should NOT be called.
    assert not dummy_export_templates.called
    # process_file should be called with the provided values.
    assert dummy_process_file.called
    assert dummy_process_file.args == (test_input, test_output, test_schema)


# Test running the CLI when --export_templates flag is provided.
def test_main_with_export_templates():
    test_input = "dummy_input.txt"
    test_schema = "dummy_schema"
    sys.argv = [
        "cli.py",
        test_input,
        "--schema_folder",
        test_schema,
        "--export_templates",
    ]
    cli.main()
    # When --export_templates is provided, export_templates should be called.
    assert dummy_export_templates.called
    assert dummy_export_templates.schema_folder == test_schema
    # process_file is always called after the if-statement.
    assert dummy_process_file.called
    # Here output_file is not provided so it defaults to None.
    assert dummy_process_file.args == (test_input, None, test_schema)


# Test that missing the required input_file argument causes a SystemExit.
def test_main_missing_input_file():
    sys.argv = ["cli.py"]
    with pytest.raises(SystemExit):
        cli.main()
