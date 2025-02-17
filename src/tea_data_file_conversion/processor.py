# fixedwidth_processor/processor.py

import os
import shutil
import sys

import importlib_resources  # Used to locate package data
import pandas as pd
import yaml


def load_yaml_config(file_path):
    """Load a YAML configuration file."""
    try:
        with open(file_path) as f:
            config = yaml.safe_load(f)
        return config
    except yaml.YAMLError as ye:
        # If YAML parsing fails, output details.
        raise ValueError(f"Error parsing YAML file {file_path}: {ye}") from ye


def validate_yaml_config(config, file_path):
    """
    Validate the structure of the YAML configuration.

    Expected structure:

        {
          "fields": [
             {
               "start": int,
               "end": int,
               "output_field": str,
               "keep": bool (optional)
             },
             ...
          ]
        }

    If the structure is invalid, raise a ValueError with details.
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
    """
    Process a fixed-width file using the provided schema configuration.

    Parameters
    ----------
      input_file (str): Path to the fixed-width text file.
      schema_config (dict): Schema configuration dictionary with field definitions.
      skip_header (bool): If True, skip the first line (header).
      filter_columns (bool): If True, only keep columns marked with "keep": true in the schema.
    Returns
    -------
      pd.DataFrame: DataFrame containing only the columns marked to be kept.

    """
    fields = schema_config["fields"]
    colspecs = []
    col_names = []
    keep_columns = []  # Track columns to keep

    for field in fields:
        start = field["start"] - 1
        end = field["end"]
        colspecs.append((start, end))
        if filter_columns:
            col_name = field["mapped_field_name"] if not pd.isna(field["mapped_field_name"]) else field["output_field"]
        else:
            col_name = field["output_field"]
        col_names.append(col_name)
        if field.get("keep", False):
            keep_columns.append(col_name)

    # Ensure unique column names
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

    # If skipping header, skip the first row.
    df = pd.read_fwf(input_file, colspecs=colspecs, header=None, names=unique_col_names)

    if filter_columns:
        df = df[keep_columns]

    return df


def process_file(input_file, output_file=None, schema_folder=None, filter_columns=False):
    """
    Process the input fixed-width file and write the output CSV.

    The input file must have a header line (first line) where:
      - The first 2 characters represent the test month.
      - The next 2 characters represent an abbreviated school year.

    For "staar" tests (test_month < 10), the test name is "staar".
    For "staar_eoc" tests (test_month >= 10), if test_month is less than 15 then 1 is added
    to the full school year (2000 + abbreviated year).

    The fixed-width schema is loaded from a YAML file that is expected to reside in a subfolder
    under the given schema_folder (or current directory if not provided). For example, if the computed
    test_name is "staar" and full_school_year is 2024, the schema file is expected at:

        <schema_folder>default_schema/staar/staar_2024.yaml

    Parameters
    ----------
      input_file (str): Path to the input fixed-width file.
      output_file (str, optional): Path to the output CSV file. If not provided, the file name is
                                   based on the input file with '_output.csv' appended.
      schema_folder (str, optional): Folder where the YAML schema files reside. Defaults to current folder.
      filter_columns (bool): If True, only keep columns marked with "keep": true in the schema.

    Returns
    -------
      pd.DataFrame: The processed DataFrame.

    """
    # Determine the output file name.
    if output_file is None:
        base, _ = os.path.splitext(input_file)
        output_file = f"{base}_output.csv"

    # Read the header (first line) of the input file.
    with open(input_file) as f:
        header_line = f.readline().strip()

    if len(header_line) < 4:
        raise ValueError("The header line must contain at least 4 characters.")

    # Extract header information.
    header = header_line[:4]
    test_month = int(header[:2])
    school_year_abbr = int(header[2:4])
    full_school_year = 2000 + school_year_abbr

    # Determine test name and adjust full_school_year if needed.
    if test_month < 10:
        test_name = "staar"
    else:
        test_name = "staar_eoc"
        if test_month < 15:
            full_school_year += 1

    # Determine the base folder for schema files.
    base_folder = schema_folder if schema_folder is not None else "default_schema"
    schema_config_file = os.path.join(base_folder, test_name, f"{test_name}_{full_school_year}.yaml")
    print(f"Loading schema config: {schema_config_file}")

    # Load the YAML configuration and validate its structure.
    schema_config = load_yaml_config(schema_config_file)
    try:
        validate_yaml_config(schema_config, schema_config_file)
    except ValueError as ve:
        # If the structure is invalid, print the error and exit.
        print(f"YAML validation error: {ve}")
        sys.exit(1)

    # Process the fixed-width file (skipping the header).
    df = process_fixed_width_file(input_file, schema_config, skip_header=True, filter_columns=filter_columns)

    # Add the computed fields.
    df["school_year"] = full_school_year
    df["test_name"] = test_name

    # Write the output CSV.
    df.to_csv(output_file, index=False)
    print(f"Data has been written to {output_file}")
    return df


def export_templates(schema_folder):
    """
    Export sample YAML template files into a folder structure.

    The function copies the YAML files from the package's built-in default_schema folder
    (which is installed with the package) into the target schema_folder, preserving the structure.

    For example, if the built-in folder contains:

        default_schema/staar/staar_2024.yaml
        default_schema/staar_eoc/staar_eoc_2022.yaml

    then these files will be copied to:

        <schema_folder>/staar/staar_2024.yaml
        <schema_folder>/staar_eoc/staar_eoc_2022.yaml

    After exporting, the function prints a message and exits so the user can review and update the templates.
    """
    # Locate the default_schema folder inside the package using pkg_resources.
    default_schema_path = importlib_resources.path("fixedwidth_processor", "default_schema")
    if not os.path.isdir(default_schema_path):
        print("Default schema folder not found in package.")
        sys.exit(1)

    # Walk through the default_schema folder and copy files preserving directory structure.
    for root, _dirs, files in os.walk(default_schema_path):
        for file in files:
            # Compute the relative path with respect to default_schema_path.
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
    """
    Convert a CSV file into a YAML schema file for fixed-width processing.

    This function loads the CSV file and prints its available columns.
    It then interactively asks the user to select:
      - The column representing the start value.
      - The column representing the end value.
      - The column representing the output field, which should be in the format:
            "Field Category - Field Title"

    For each row in the CSV, a field entry is created with the following structure:

        {
            "start": [Start Row Value],
            "end": [End Row Value],
            "output_field": "[Field Category - Field Title]",
            "keep": false
        }

    The resulting YAML file will have the structure:

        fields:
          - start: [Start Row Value]
            end: [End Row Value]
            output_field: "[Field Category - Field Title]"
            keep: false
          - ... (one entry per CSV row)

    Parameters
    ----------
      csv_file (str): Path to the CSV file.
      yaml_output_file (str, optional): Path to the output YAML file. If not provided, the output
                                        file name is derived from the CSV file (e.g. "data_schema.yaml").

    """
    # Load the CSV file.
    try:
        df = pd.read_csv(csv_file)
    except Exception as e:
        print(f"Error loading CSV file: {e}")
        return

    # Display available columns.
    print("Available columns in the CSV:")
    for col in df.columns:
        print(f" - {col}")

    # Prompt the user for the necessary columns.
    start_col = input("Enter the name of the column representing the start value: ").strip()
    end_col = input("Enter the name of the column representing the end value: ").strip()
    output_field_col = input(
        "Enter the name of the column representing the output field (e.g., 'Field Category: Field Title'): "
    ).strip()

    # Build the list of field dictionaries.
    fields = []
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

        output_field_value = str(row[output_field_col]).replace("\u2013", "-").replace("\n", "").replace("\r", "")
        field_entry = {
            "start": start_value,
            "end": end_value,
            "output_field": output_field_value,
            "keep": row.get("keep", False),
            "mapped_field_name": row.get("Mapped Field Title", output_field_value),
        }
        fields.append(field_entry)

    data = {"fields": fields}

    # Determine output YAML file name if not provided.
    if yaml_output_file is None:
        base, _ = os.path.splitext(csv_file)
        yaml_output_file = f"{base}_schema.yaml"

    try:
        with open(yaml_output_file, "w") as f:
            yaml.dump(data, f, sort_keys=False)
        print(f"Schema YAML file successfully created: {yaml_output_file}")
    except Exception as e:
        print(f"Error writing YAML file: {e}")


if __name__ == "__main__":
    # # If run as a script, call the main function.
    process_file(
        "/Users/markm/Downloads/TEA-Data-Files/RAW_Data_files/STAAR/SF_0524_3-8_101902_ALDINE ISD_V01.txt",
        "/Users/markm/Downloads/TEA-Data-Files/RAW_Data_files/STAAR/SF_0524_3-8_101902_ALDINE ISD_V01_output.csv",
        filter_columns=True,
    )

    # If run as a script, call the main function.
    # csv_to_schema_yaml('/Users/markm/Downloads/TEA-Data-Files/CSV/2024-staar-3-8-data-file.csv',
    #                       '/Users/markm/Downloads/TEA-Data-Files/CSV/2024-staar-3-8-data-file_schema.yaml')
