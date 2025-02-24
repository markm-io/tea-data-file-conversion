# file: src/tea_data_file_conversion/cli.py

r"""Command-line interface for fixed\-width file processing.

This module provides an entry point to either process a fixed\-width file
into CSV format using a dynamic YAML schema or export default YAML templates.
"""

import argparse

from .processor import export_templates, process_file


def main():
    r"""Parse command\-line arguments and execute the corresponding action.

    Options:
      \- Process a fixed\-width file to CSV.
      \- Export YAML template files if the --export_templates flag is set.
    """
    # Set up the argument parser.
    parser = argparse.ArgumentParser(
        description=r"Process a fixed\-width file and output a CSV based on dynamic YAML schema."
    )
    # Input file (required).
    parser.add_argument("input_file", help=r"Path to the input fixed\-width file.")
    # Optional output file.
    parser.add_argument(
        "--output_file",
        help=(
            "Optional path for the output CSV file. "
            "If not provided, defaults to the input file name with '_output.csv' appended."
        ),
        default=None,
    )
    # Optional schema folder location.
    parser.add_argument(
        "--schema_folder",
        help="Path to the folder containing YAML schema files "
        "(or where templates will be exported). Defaults to current directory.",
        default=".",
    )
    # Flag to export templates.
    parser.add_argument(
        "--export_templates",
        help=r"Export template YAML files from the built\-in "
        r"default_schema folder to the specified schema_folder and exit.",
        action="store_true",
    )

    # Parse the provided arguments.
    args = parser.parse_args()

    # If the export flag is set, export YAML templates and exit immediately.
    if args.export_templates:
        export_templates(args.schema_folder)

    # Otherwise, process the file using the processed arguments.
    process_file(args.input_file, args.output_file, schema_folder=args.schema_folder)


if __name__ == "__main__":
    main()
