# fixedwidth_processor/cli.py

import argparse

from tea_data_file_conversion.processor import export_templates, process_file


def main():
    parser = argparse.ArgumentParser(
        description="Process a fixed-width file and output a CSV based on dynamic YAML schema."
    )
    parser.add_argument("input_file", help="Path to the input fixed-width file.")
    parser.add_argument(
        "--output_file",
        help=(
            "Optional path for the output CSV file. "
            "If not provided, defaults to the input file name with '_output.csv' appended."
        ),
        default=None,
    )
    parser.add_argument(
        "--schema_folder",
        help="Path to the folder containing YAML schema files (or "
        "where templates will be exported). Defaults to current directory.",
        default=".",
    )
    parser.add_argument(
        "--export_templates",
        help="Export template YAML files from the built-in default_schema "
        "folder to the specified schema_folder and exit.",
        action="store_true",
    )
    args = parser.parse_args()

    # If export_templates flag is set, export templates and exit.
    if args.export_templates:
        export_templates(args.schema_folder)

    # Otherwise, process the file using the provided schema_folder.
    process_file(args.input_file, args.output_file, schema_folder=args.schema_folder)


if __name__ == "__main__":
    main()
