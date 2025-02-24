# file: src/tea_data_file_conversion/processor.py

r"""Processor module for fixed\-width file conversion.

This module provides functions to:
  \- Load and validate YAML schema configurations.
  \- Process fixed\-width files into structured DataFrame objects.
  \- Export template YAML schema files.
  \- Convert CSV files into YAML schema files interactively.
"""

import os
import shutil
import sys

import importlib_resources  # Used to locate package data.
import pandas as pd
import yaml


def load_yaml_config(file_path):
    """
    Load a YAML configuration file for processing.

    Parameters
    ----------
    file_path : str
        The path to the YAML configuration file.

    Returns
    -------
    dict
        The parsed YAML configuration.

    Raises
    ------
    ValueError
        If there is an error parsing the YAML file.
    """
    try:
        with open(file_path) as f:
            config = yaml.safe_load(f)
        return config
    except yaml.YAMLError as ye:
        # Raise an error with details of parsing issues.
        raise ValueError(f"Error parsing YAML file {file_path}: {ye}") from ye


def validate_yaml_config(config, file_path):
    """
    Validate the structure of the YAML configuration.

    The configuration must be a dictionary containing a key 'fields' mapping to a list.
    Each field in the list must contain 'start', 'end', and 'output_field' keys.

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

    for index, field in enumerate(config["fields"]):
        if not isinstance(field, dict):
            raise ValueError(f"YAML file {file_path}, field at index {index} is not a dictionary.")
        for key in ["start", "end", "output_field"]:
            if key not in field:
                raise ValueError(f"YAML file {file_path}, field at index {index} is missing required key '{key}'.")
        if not isinstance(field["start"], int):
            raise ValueError(f"YAML file {file_path}, field at index {index} key 'start' must be an integer.")
        if not isinstance(field["end"], int):
            raise ValueError(f"YAML file {file_path}, field at index {index} key 'end' must be an integer.")
        if not isinstance(field["output_field"], str):
            raise ValueError(f"YAML file {file_path}, field at index {index} key 'output_field' must be a string.")
        if "keep" in field and not isinstance(field["keep"], bool):
            raise ValueError(f"YAML file {file_path}, field at index {index} key 'keep' must be a boolean.")


def process_fixed_width_file(input_file, schema_config, skip_header=False, filter_columns=False):
    r"""
    Process a fixed\-width file using the provided YAML schema configuration.

    It determines column boundaries based on the schema, reads the file using pandas,
    and applies optional filtering to only return columns marked to be kept.

    Parameters
    ----------
    input_file : str
        The path to the fixed\-width text file.
    schema_config : dict
        Schema configuration dictionary with field definitions.
    skip_header : bool, optional
        Skip the header row if True (default is False).
    filter_columns : bool, optional
        If True, return only DataFrame columns that are marked with "keep": true.

    Returns
    -------
    pd.DataFrame
        DataFrame with the processed data.
    """
    fields = schema_config["fields"]
    colspecs = []  # List of tuples defining start and end positions for each field.
    col_names = []  # List of column names derived from the schema.
    keep_columns = []  # Track columns flagged to be retained.

    for field in fields:
        # Adjust the start position because the schema uses 1-based indexing.
        start = field["start"] - 1
        end = field["end"]
        colspecs.append((start, end))
        # Use 'mapped_field_name' when filtering columns if available.
        if filter_columns:
            col_name = (
                field["mapped_field_name"] if not pd.isna(field.get("mapped_field_name")) else field["output_field"]
            )
        else:
            col_name = field["output_field"]
        col_names.append(col_name)
        if field.get("keep", False):
            keep_columns.append(col_name)

    # Ensure each column name is unique by appending a counter if needed.
    unique_col_names = []
    for col_name in col_names:
        if col_name in unique_col_names:
            count = 1
            new_col_name = f"{col_name}_{count}"
            while new_col_name in unique_col_names:
                count += 1
                new_col_name = f"{col_name}_{count}"
            unique_col_names.append(new_col_name)
        else:
            unique_col_names.append(col_name)

    # Read the fixed\-width file into a DataFrame.
    df = pd.read_fwf(input_file, colspecs=colspecs, header=None, names=unique_col_names)

    if filter_columns:
        df = df[keep_columns]

    return df


def process_file(input_file, output_file=None, schema_folder=None, filter_columns=False):
    r"""
    Process an input fixed\-width file and output a CSV file.

    The function:
      \- Determines the appropriate YAML schema based on header info.
      \- Loads and validates the schema.
      \- Processes the input file and writes the output DataFrame to CSV.

    Parameters
    ----------
    input_file : str
        The path to the fixed\-width input file.
    output_file : str, optional
        File path for the output CSV. Defaults to input file name with '_output.csv' appended.
    schema_folder : str, optional
        Folder where the YAML schema files are located; defaults to the current folder.
    filter_columns : bool, optional
        If True, only load columns flagged with "keep": true (default is False).

    Returns
    -------
    pd.DataFrame
        The processed DataFrame.
    """
    # Define the output CSV file name if not explicitly provided.
    if output_file is None:
        base, _ = os.path.splitext(input_file)
        output_file = f"{base}_output.csv"

    # Read and validate the header line.
    with open(input_file) as f:
        header_line = f.readline().strip()

    if len(header_line) < 4:
        raise ValueError("The header line must contain at least 4 characters.")

    # Extract test month and abbreviated school year from header.
    header = header_line[:4]
    test_month = int(header[:2])
    school_year_abbr = int(header[2:4])
    full_school_year = 2000 + school_year_abbr

    # Determine test type and adjust school year if necessary.
    if test_month < 10:
        test_name = "staar"
    else:
        test_name = "staar_eoc"
        if test_month < 15:
            full_school_year += 1

    # Compose the path to the expected YAML schema file.
    base_folder = schema_folder if schema_folder is not None else "default_schema"
    schema_config_file = os.path.join(base_folder, test_name, f"{test_name}_{full_school_year}.yaml")
    print(f"Loading schema config: {schema_config_file}")

    # Load and validate the YAML configuration.
    schema_config = load_yaml_config(schema_config_file)
    try:
        validate_yaml_config(schema_config, schema_config_file)
    except ValueError as ve:
        print(f"YAML validation error: {ve}")
        sys.exit(1)

    # Process the file using the loaded schema.
    df = process_fixed_width_file(input_file, schema_config, skip_header=True, filter_columns=filter_columns)

    # Write the processed data to a CSV file.
    df.to_csv(output_file, index=False)
    print(f"Data has been written to {output_file}")
    return df


def export_templates(schema_folder):
    r"""
    Export sample YAML template files to a specified folder.

    The function copies files from the built\-in default_schema directory
    (packaged with this module) into the target folder while preserving the
    original directory structure.

    Parameters
    ----------
    schema_folder : str
        The destination folder for exporting the template YAML files.

    Exits
    -----
    The function exits after exporting the template files.
    """
    # Locate the default_schema folder within the package.
    default_schema_path = importlib_resources.path("fixedwidth_processor", "default_schema")
    if not os.path.isdir(default_schema_path):
        print("Default schema folder not found in package.")
        sys.exit(1)

    # Iterate over the directory structure and copy each file.
    for root, _dirs, files in os.walk(default_schema_path):
        for file in files:
            rel_path = os.path.relpath(os.path.join(root, file), default_schema_path)
            target_file = os.path.join(schema_folder, rel_path)
            os.makedirs(os.path.dirname(target_file), exist_ok=True)
            shutil.copy(os.path.join(root, file), target_file)
    print(f"Template YAML files exported to {schema_folder}.")
    print(
        "Please review and update the templates as needed, then run the script again using the --schema_folder option."
    )
    sys.exit(0)


def csv_to_schema_yaml(csv_file, yaml_output_file=None):
    r"""
    Convert a CSV file into a YAML schema file for fixed\-width processing.

    This function loads a CSV file, lists available columns, and interactively
    prompts the user to select fields corresponding to start, end, and output
    values, then writes out a YAML file with the chosen configuration.

    Parameters
    ----------
    csv_file : str
        Path to the input CSV file.
    yaml_output_file : str, optional
        Output file path for the YAML schema. If omitted, a default name is generated.
    """
    try:
        df = pd.read_csv(csv_file)
    except Exception as e:
        print(f"Error loading CSV file: {e}")
        return

    # Display available CSV columns for user selection.
    print("Available columns in the CSV:")
    for col in df.columns:
        print(f" - {col}")

    # Request the user to enter the necessary columns.
    start_col = input("Enter the name of the column representing the start value: ").strip()
    end_col = input("Enter the name of the column representing the end value: ").strip()
    output_field_col = input(
        "Enter the name of the column representing the output field (e.g., 'Field Category - Field Title'): "
    ).strip()

    fields = []  # Prepare a list for schema field definitions.
    for index, row in df.iterrows():
        try:
            start_value = int(row[start_col])
        except (ValueError, TypeError):
            print(f"Row {index}: Could not convert start value '{row[start_col]}' to int. Skipping this row.")
            continue

        try:
            end_value = int(row[end_col])
        except (ValueError, TypeError):
            print(f"Row {index}: Could not convert end value '{row[end_col]}' to int. Skipping this row.")
            continue

        # Clean the output field by replacing special dash characters.
        output_field_value = (
            str(row[output_field_col]).replace("\u2010", "-").replace("\u2013", "-").replace("\n", "").replace("\r", "")
        )
        field_entry = {
            "start": start_value,
            "end": end_value,
            "output_field": output_field_value,
            "keep": row.get("keep", False),
            "mapped_field_name": row.get("Mapped Field Title", output_field_value),
        }
        fields.append(field_entry)

    data = {"fields": fields}

    # Set default output YAML file name if none provided.
    if yaml_output_file is None:
        base, _ = os.path.splitext(csv_file)
        yaml_output_file = f"{base}_schema.yaml"

    try:
        with open(yaml_output_file, "w") as f:
            yaml.dump(data, f, sort_keys=False)
        print(f"Schema YAML file successfully created: {yaml_output_file}")
    except Exception as e:
        print(f"Error writing YAML file: {e}")
