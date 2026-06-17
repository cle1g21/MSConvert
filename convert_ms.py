#!/usr/bin/env python3
"""
Convert vendor mass spectrometry raw files to mzML or MGF using MSConvert in Apptainer.

Prerequisite (run in your terminal before this script):
    module load apptainer/1.5.0
"""

# Import the sys module so we can exit the script with a status code.
import sys

# Import the os module so we can check paths and create directories.
import os

# Import the shutil module so we can check whether apptainer is on PATH.
import shutil

# Import the subprocess module so we can run the apptainer command safely.
import subprocess

# Import the argparse module so users can pass input file and format on the command line.
import argparse


# Default host directory where converted files are written if --output-dir is not given.
DEFAULT_OUTPUT_DIRECTORY = "/home/cle1g21/RPC/msconvert/output_data"

# Internal container path where the input file's parent directory is mounted.
CONTAINER_INPUT_MOUNT = "/data_in"

# Internal container path where the output directory is mounted.
CONTAINER_OUTPUT_MOUNT = "/data_out"

# Default path to the local Apptainer image pulled from Docker Hub.
DEFAULT_APPTAINER_IMAGE_PATH = "/home/cle1g21/RPC/msconvert/proteowizard.sif"

# Cluster module name the user must load before apptainer is available.
APPTAINER_MODULE = "apptainer/1.5.0"

# Required on Iridis: unpack the SIF image instead of FUSE-mounting (fusermount unavailable).
APPTAINER_UNSQUASH_FLAG = "--unsquash"

# Map user-friendly format names to the MSConvert command-line flags inside the container.
SUPPORTED_FORMATS = {
    "mzml": "--mzML",
    "mgf": "--mgf",
}


def parse_command_line_arguments():
    """Read and validate command-line arguments from the user."""

    # Create the main argument parser with a short description of the script.
    argument_parser = argparse.ArgumentParser(
        description="Convert vendor raw mass spectrometry files to mzML or MGF using Apptainer and MSConvert.",
    )

    # Add a required argument for the path to any vendor raw file or folder.
    argument_parser.add_argument(
        "--input",
        required=True,
        help="Path to the vendor raw file or folder to convert (for example a Bruker .d folder or Thermo .raw file).",
    )

    # Add an optional argument for where converted files should be saved on the host.
    argument_parser.add_argument(
        "--output-dir",
        default=DEFAULT_OUTPUT_DIRECTORY,
        help=f"Host directory for converted output files (default: {DEFAULT_OUTPUT_DIRECTORY}).",
    )

    # Add an optional argument to choose mzML or MGF output format.
    argument_parser.add_argument(
        "--format",
        choices=sorted(SUPPORTED_FORMATS.keys()),
        default="mgf",
        help="Output format: mgf writes .mgf files; mzml writes .mzML files (default: mgf).",
    )

    # Add an optional argument for the path to the local Apptainer image file.
    argument_parser.add_argument(
        "--image",
        default=DEFAULT_APPTAINER_IMAGE_PATH,
        help=f"Path to the Apptainer .sif image (default: {DEFAULT_APPTAINER_IMAGE_PATH}).",
    )

    # Parse the command line and return the resulting namespace object.
    return argument_parser.parse_args()


def resolve_input_paths(input_path):
    """Turn the user input path into absolute host paths used for bind mounts."""

    # Convert the input path to an absolute path on the host filesystem.
    absolute_input_path = os.path.abspath(input_path)

    # Get the directory that contains the input file or folder on the host.
    host_input_parent_directory = os.path.dirname(absolute_input_path)

    # Get just the filename or folder name (no directory prefix).
    input_basename = os.path.basename(absolute_input_path)

    # Return all three pieces for bind-mount and command assembly.
    return absolute_input_path, host_input_parent_directory, input_basename


def resolve_output_directory(output_directory):
    """Turn the output directory into an absolute path and create it if needed."""

    # Convert the output directory to an absolute path on the host.
    absolute_output_directory = os.path.abspath(output_directory)

    # Create the output directory (and any missing parents) if it does not exist yet.
    os.makedirs(absolute_output_directory, exist_ok=True)

    # Return the absolute output path for bind mounts and file checks.
    return absolute_output_directory


def get_input_stem(input_path):
    """Get the filename stem used by MSConvert to name the output file."""

    # Extract the basename and remove the last extension (for example .d or .raw).
    return os.path.splitext(os.path.basename(os.path.abspath(input_path)))[0]


def get_expected_output_path(input_path, output_directory, output_format):
    """Build the path where MSConvert should write the converted file on the host."""

    # Get the stem MSConvert uses from the input filename.
    input_stem = get_input_stem(input_path)

    # Choose the file extension that matches the requested output format.
    if output_format == "mzml":
        # mzML files typically use the .mzML extension (capital ML).
        output_extension = ".mzML"
    else:
        # MGF files use the .mgf extension.
        output_extension = ".mgf"

    # Join the output directory, stem, and extension into the full expected path.
    return os.path.join(os.path.abspath(output_directory), input_stem + output_extension)


def get_alternate_mzml_paths(expected_output_path):
    """Return possible mzML path variants because extension casing can differ on Linux."""

    # Start with the primary expected path in the list of paths to check.
    candidate_paths = [expected_output_path]

    # If the expected path ends with .mzML, also check lowercase .mzml.
    if expected_output_path.endswith(".mzML"):
        candidate_paths.append(expected_output_path[:-5] + ".mzml")

    # If the expected path ends with .mzml, also check uppercase .mzML.
    if expected_output_path.endswith(".mzml"):
        candidate_paths.append(expected_output_path[:-5] + ".mzML")

    # Return the list of paths to try when verifying output.
    return candidate_paths


def check_apptainer_available():
    """Verify that the apptainer command is on PATH after module load."""

    # Look for the apptainer executable in the user's PATH.
    apptainer_executable = shutil.which("apptainer")

    # If apptainer was not found, print a clear instruction and return False.
    if apptainer_executable is None:
        print("ERROR: The 'apptainer' command was not found on your PATH.")
        print(f"Please run this in your terminal first: module load {APPTAINER_MODULE}")
        return False

    # Apptainer is available, so pre-check passes.
    return True


def check_input_exists(absolute_input_path):
    """Confirm the input file or folder exists on the host before running the container."""

    # Check whether the input path exists as a file or directory.
    if not os.path.exists(absolute_input_path):
        print(f"ERROR: Input path does not exist: {absolute_input_path}")
        return False

    # Input exists, so pre-check passes.
    return True


def check_apptainer_image(image_path):
    """Confirm the local .sif image file exists before attempting conversion."""

    # Check whether the Apptainer image file is present on disk.
    if not os.path.isfile(image_path):
        print(f"ERROR: Apptainer image not found: {image_path}")
        print("Pull it once with:")
        print(f"  module load {APPTAINER_MODULE}")
        print(f"  apptainer pull {image_path} docker://proteowizard/pwiz-skyline-i-agree-to-the-vendor-licenses")
        return False

    # Image file exists, so pre-check passes.
    return True


def build_apptainer_command(
    host_input_parent_directory,
    input_basename,
    host_output_directory,
    image_path,
    msconvert_format_flag,
):
    """Assemble the apptainer run command as a list of arguments (no shell string)."""

    # Build the command list that subprocess will execute directly.
    apptainer_command = [
        "apptainer",
        "run",
        APPTAINER_UNSQUASH_FLAG,
        "--bind",
        f"{host_input_parent_directory}:{CONTAINER_INPUT_MOUNT}",
        "--bind",
        f"{host_output_directory}:{CONTAINER_OUTPUT_MOUNT}",
        image_path,
        "wine",
        "msconvert",
        f"{CONTAINER_INPUT_MOUNT}/{input_basename}",
        "-o",
        CONTAINER_OUTPUT_MOUNT,
        msconvert_format_flag,
    ]

    # Return the completed command list.
    return apptainer_command


def format_command_for_display(command_list):
    """Turn the command list into a single readable string for the user to copy."""

    # Join arguments with spaces so the user can copy the command from the terminal.
    return " ".join(command_list)


def run_conversion(apptainer_command):
    """Run MSConvert inside Apptainer and capture stdout and stderr."""

    # Print the exact command so the user can reproduce the run manually.
    print("Running command:")
    print(format_command_for_display(apptainer_command))
    print()

    # Execute the apptainer command and capture standard output and standard error.
    completed_process = subprocess.run(
        apptainer_command,
        capture_output=True,
        text=True,
    )

    # Print MSConvert and Wine messages from standard output.
    if completed_process.stdout:
        print("--- stdout ---")
        print(completed_process.stdout)

    # Print diagnostic messages from standard error (often verbose but useful).
    if completed_process.stderr:
        print("--- stderr ---")
        print(completed_process.stderr)

    # Return the completed process object so the caller can check the exit code.
    return completed_process


def verify_output_file(expected_output_path, output_format):
    """Check that the converted file appeared in the output directory on the host."""

    # For mzML, check multiple extension casings because Linux paths are case-sensitive.
    if output_format == "mzml":
        paths_to_check = get_alternate_mzml_paths(expected_output_path)
    else:
        paths_to_check = [expected_output_path]

    # Try each candidate path until one exists on disk.
    for candidate_path in paths_to_check:
        if os.path.isfile(candidate_path):
            file_size_bytes = os.path.getsize(candidate_path)
            print(f"SUCCESS: Output file created: {candidate_path}")
            print(f"         File size: {file_size_bytes:,} bytes")
            return candidate_path

    # None of the expected paths were found after conversion.
    print(f"WARNING: Expected output file was not found at: {expected_output_path}")
    if output_format == "mzml":
        print("         Also checked alternate mzML extension casing.")
    return None


def main():
    """Run the full conversion workflow from argument parsing through verification."""

    # Read command-line arguments from the user.
    arguments = parse_command_line_arguments()

    # Resolve input to absolute paths and get the basename for the container command.
    absolute_input_path, host_input_parent_directory, input_basename = resolve_input_paths(
        arguments.input
    )

    # Resolve and create the output directory on the host.
    absolute_output_directory = resolve_output_directory(arguments.output_dir)

    # Look up the MSConvert flag that matches the requested output format.
    msconvert_format_flag = SUPPORTED_FORMATS[arguments.format]

    # Compute where we expect the converted file to appear after a successful run.
    expected_output_path = get_expected_output_path(
        absolute_input_path,
        absolute_output_directory,
        arguments.format,
    )

    # Print a short summary so the user can confirm settings before conversion starts.
    print("MSConvert conversion via Apptainer")
    print(f"  Input:       {absolute_input_path}")
    print(f"  Output dir:  {absolute_output_directory}")
    print(f"  Format:      {arguments.format} ({msconvert_format_flag})")
    print(f"  Image:       {arguments.image}")
    print(f"  Expected:    {expected_output_path}")
    print()

    # Stop if apptainer is not available (user likely forgot module load).
    if not check_apptainer_available():
        sys.exit(1)

    # Stop if the input file or folder does not exist.
    if not check_input_exists(absolute_input_path):
        sys.exit(1)

    # Stop if the Apptainer image has not been pulled yet.
    if not check_apptainer_image(arguments.image):
        sys.exit(1)

    # Build the apptainer run command with dynamic bind mounts and format flag.
    apptainer_command = build_apptainer_command(
        host_input_parent_directory,
        input_basename,
        absolute_output_directory,
        arguments.image,
        msconvert_format_flag,
    )

    # Run the conversion and capture logs from inside the container.
    completed_process = run_conversion(apptainer_command)

    # Stop if MSConvert or Apptainer returned a non-zero exit code.
    if completed_process.returncode != 0:
        print(f"ERROR: Conversion failed with exit code {completed_process.returncode}")
        sys.exit(1)

    # Confirm the output file exists on the host and print its path and size.
    output_file_path = verify_output_file(expected_output_path, arguments.format)

    # Stop if the output file was not found despite a zero exit code.
    if output_file_path is None:
        sys.exit(1)

    # Exit with success status code zero.
    sys.exit(0)


# Only run main() when this file is executed as a script, not when imported.
if __name__ == "__main__":
    main()
