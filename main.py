#!/usr/bin/python3
"""
Synology Office File Export Tool - Main Entry Point

This script provides a command-line interface for downloading and converting Synology Office files
to Microsoft Office formats. It uses the OfficeFileDownloader class from office_file_downloader.py.

Usage:
  python main.py [options]

Options:
  -o, --output DIR       Directory where files will be saved (default: current directory)
  -u, --username USER    Synology username
  -p, --password PASS    Synology password
  -s, --server HOST      Synology server URL
  -f, --force            Force download all files, ignoring download history
  --log-level LEVEL      Set the logging level (default: info)
                         Choices: debug, info, warning, error, critical
  -h, --help             Show this help message and exit

Authentication:
  Credentials can be provided in three ways (in order of precedence):
  1. Command line arguments (-u, -p, -s)
  2. Environment variables (via .env file: SYNOLOGY_NAS_USER, SYNOLOGY_NAS_PASS, SYNOLOGY_NAS_HOST)
  3. Interactive prompt

Example:
  python main.py -o ~/Downloads/synology_exports -f --log-level debug
"""

import argparse
import getpass
import logging
import os
import sys
from dotenv import load_dotenv
from synology_office_exporter import OfficeFileDownloader, SynologyDriveEx

# office_file_downloader.pyからLOG_LEVELSを移植
LOG_LEVELS = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL
}


def parse_arguments():
    parser = argparse.ArgumentParser(
        description='Download Synology Office files and convert to Microsoft Office format')
    parser.add_argument('-o', '--output',
                        help='Output directory for downloaded files',
                        default='.')
    parser.add_argument('-u', '--username', help='Synology username')
    parser.add_argument('-p', '--password', help='Synology password')
    parser.add_argument('-s', '--server', help='Synology server URL')
    parser.add_argument('-f', '--force', action='store_true',
                        help='Force download all files, ignoring download history')
    parser.add_argument('--log-level',
                        default='info',
                        choices=LOG_LEVELS.keys(),
                        help='Set the logging level (default: info)')
    return parser.parse_args()


def main():
    args = parse_arguments()

    # Configure logging
    logging.basicConfig(
        level=LOG_LEVELS[args.log_level],
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Try to load .env file for credentials if not provided via command line
    load_dotenv()

    # Get credentials - prioritize command line args over environment variables
    username = args.username or os.getenv('SYNOLOGY_NAS_USER')
    password = args.password or os.getenv('SYNOLOGY_NAS_PASS')
    server = args.server or os.getenv('SYNOLOGY_NAS_HOST')

    # If still missing credentials, prompt the user
    if not username:
        username = input("Synology username: ")
    if not password:
        password = getpass.getpass("Synology password: ")
    if not server:
        server = input("Synology server URL: ")

    # Check if all required credentials are set
    if not all([username, password, server]):
        logging.error("Missing credentials. Please provide username, password, and server.")
        return 1

    try:
        # Connect to Synology Drive
        with SynologyDriveEx(username, password, server, dsm_version='7') as synd:
            # Create and use the downloader
            with OfficeFileDownloader(synd, output_dir=args.output, force_download=args.force) as downloader:
                downloader.download_mydrive_files()
                downloader.download_shared_files()
                downloader.download_teamfolder_files()

        logging.info("Done!")
        return 0
    except Exception as e:
        logging.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
