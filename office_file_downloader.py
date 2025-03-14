#! /usr/bin/python3
"""
Synology Office File Export Tool

This script enables users to download and convert Synology Office files to their
Microsoft Office equivalents. It connects to a Synology NAS using credentials stored
in environment variables and processes files from shared folders, team folders, and personal drives.

File conversions performed:
- Synology Spreadsheet (.osheet) -> Microsoft Excel (.xlsx)
- Synology Document (.odoc) -> Microsoft Word (.docx)
- Synology Slides (.oslides) -> Microsoft PowerPoint (.pptx)

Requirements:
- Python 3.6+
- synology-drive-ex package
- python-dotenv package

Setup:
1. Create a .env file with the following variables:
   SYNOLOGY_NAS_USER=your_username
   SYNOLOGY_NAS_PASS=your_password
   SYNOLOGY_NAS_HOST=your_nas_ip_or_hostname

Usage:
  python office_file_downloader.py [options]

Options:
  --log-level {debug,info,warning,error,critical}
                        Set the logging level (default: info)
  --output-dir DIRECTORY, -o DIRECTORY
                        Directory where files will be saved (default: current directory)
  --help                Show this help message and exit

The tool will:
1. Connect to the Synology NAS using credentials from the .env file
2. Process files from:
   - Your personal My Drive
   - Team folders you have access to
   - Files shared with you by other users
3. Download Synology Office files and convert them to Microsoft Office format
4. Save the converted files to the specified output directory, preserving the folder structure
5. Skip encrypted files (which cannot be automatically converted)
"""

from io import BytesIO
import logging
import os
import sys
import argparse
from typing import Optional
import json
from datetime import datetime

from dotenv import load_dotenv
from synology_drive_ex import SynologyDriveEx

# Mapping of log level strings to actual log levels
LOG_LEVELS = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL
}


class OfficeFileDownloader:
    def __init__(self, synd: SynologyDriveEx, output_dir: str = '.'):
        self.synd = synd
        self.output_dir = output_dir
        self.download_history_file = os.path.join(output_dir, '.download_history.json')
        self.download_history = {}
        self._load_download_history()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._save_download_history()

    def _load_download_history(self):
        """Load the download history from a JSON file."""
        try:
            if os.path.exists(self.download_history_file):
                with open(self.download_history_file, 'r') as f:
                    self.download_history = json.load(f)
                logging.info(f"Loaded download history for {len(self.download_history)} files")
        except Exception as e:
            logging.error(f"Error loading download history: {e}")
            self.download_history = {}

    def _save_download_history(self):
        """Save the download history to a JSON file."""
        try:
            os.makedirs(os.path.dirname(self.download_history_file), exist_ok=True)
            with open(self.download_history_file, 'w') as f:
                json.dump(self.download_history, f)
            logging.info(f"Saved download history for {len(self.download_history)} files")
        except Exception as e:
            logging.error(f"Error saving download history: {e}")

    def download_mydrive_files(self):
        logging.info('Downloading My Drive files...')
        try:
            self._process_directory('/mydrive', 'My Drive')
        except Exception as e:
            logging.error(f'Error downloading My Drive files: {e}')

    def download_shared_files(self):
        logging.info('Downloading shared files...')
        try:
            for item in self.synd.shared_with_me():
                try:
                    self._process_item(item)
                except Exception as e:
                    logging.error(f"Error processing shared item {item.get('name')}: {e}")
        except Exception as e:
            logging.error(f'Error accessing shared files: {e}')

    def download_teamfolder_files(self):
        logging.info('Downloading team folder files...')
        try:
            for name, file_id in self.synd.get_teamfolder_info().items():
                try:
                    self._process_directory(file_id, name)
                except Exception as e:
                    logging.error(f'Error processing team folder {name}: {e}')
        except Exception as e:
            logging.error(f'Error accessing team folders: {e}')

    def _process_item(self, item):
        try:
            file_id = item['file_id']
            display_path = item.get('display_path', item.get('name'))
            content_type = item['content_type']
            hash = item.get('hash')

            if content_type == 'dir':
                self._process_directory(file_id, display_path)
            elif content_type == 'document':
                if item.get('encrypted'):
                    logging.info(f'Skipping encrypted file: {display_path}')
                    return
                self._process_document(file_id, display_path, hash)
        except Exception as e:
            logging.error(f"Error processing item {item.get('name')}: {e}")

    def _process_directory(self, file_id: str, dir_name: str):
        logging.info(f'Processing directory: {dir_name}')

        try:
            resp = self.synd.list_folder(file_id)
            if not resp['success']:
                logging.error(f"Failed to list folder {dir_name}: {resp.get('error')}")
                return

            for item in resp['data']['items']:
                self._process_item(item)
        except Exception as e:
            logging.error(f'Error processing directory {dir_name}: {e}')

    def _process_document(self, file_id: str, display_path: str, hash: str):
        """
        Process and download a Synology Office document.

        Args:
            file_id: The ID of the file to download
            display_path: The display path of the file
            hash: The hash of the file to track changes
        """
        logging.info(f'Processing {display_path}')
        try:
            # Check if file is already downloaded and unchanged
            if file_id in self.download_history and self.download_history[file_id]['hash'] == hash:
                logging.info(f'Skipping already downloaded file: {display_path}')
                return

            offline_name = self.get_offline_name(display_path)
            if not offline_name:
                logging.debug(f'Skipping non-Synology Office file: {display_path}')
                return

            # Convert absolute path to relative by removing leading slashes
            offline_name = offline_name.lstrip('/')

            # Create full path with output directory
            output_path = os.path.join(self.output_dir, offline_name)

            logging.info(f'Downloading {display_path} => {output_path}')
            data = self.synd.download_synology_office_file(file_id)
            self.save_bytesio_to_file(data, output_path)

            # Save download info to history
            self.download_history[file_id] = {
                'hash': hash,
                'path': display_path,
                'output_path': output_path,
                'download_time': str(datetime.now())
            }
        except Exception as e:
            logging.error(f'Error downloading document {display_path}: {e}')

    @staticmethod
    def get_offline_name(name: str) -> Optional[str]:
        """
        Converts Synology Office file names to Microsoft Office file names.

        File type conversions:
        - osheet -> xlsx (Excel)
        - odoc -> docx (Word)
        - oslides -> pptx (PowerPoint)

        Parameters:
            name (str): The file name to convert

        Returns:
            str or None: The file name with corresponding Microsoft Office extension.
                        Returns None if not a Synology Office file.
        """
        extension_mapping = {
            '.osheet': '.xlsx',
            '.odoc': '.docx',
            '.oslides': '.pptx'
        }
        for ext, new_ext in extension_mapping.items():
            if name.endswith(ext):
                return name[: -len(ext)] + new_ext
        return None

    @staticmethod
    def save_bytesio_to_file(data: BytesIO, path: str):
        """
        Save the contents of a BytesIO object to a file.
        """
        data.seek(0)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(data.getvalue())


def main() -> int:
    parser = argparse.ArgumentParser(description='Tool to export Synology Office files')
    parser.add_argument(
        '--log-level',
        default='info',
        choices=LOG_LEVELS.keys(),
        help='Set the logging level (default: info)'
    )
    parser.add_argument(
        '--output-dir',
        '-o',
        default='.',
        help='Directory where files will be saved (default: current directory)'
    )
    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=LOG_LEVELS[args.log_level],
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Load .env file
    load_dotenv()

    nas_user = os.getenv('SYNOLOGY_NAS_USER')
    nas_pass = os.getenv('SYNOLOGY_NAS_PASS')
    nas_host = os.getenv('SYNOLOGY_NAS_HOST')

    # Check if all required environment variables are set
    missing = [var for var, val in [('SYNOLOGY_NAS_USER', nas_user),
                                    ('SYNOLOGY_NAS_PASS', nas_pass),
                                    ('SYNOLOGY_NAS_HOST', nas_host)] if not val]
    if missing:
        logging.error(f"Environment variables not set: {', '.join(missing)}")
        logging.error('Please set the following variables in your .env file and try again:')
        for var in missing:
            logging.error(f"  {var}=value")
        return 1

    # default http port is 5000, https is 5001.
    with SynologyDriveEx(nas_user, nas_pass, nas_host, dsm_version='7') as synd:
        with OfficeFileDownloader(synd, args.output_dir) as ofd:
            ofd.download_mydrive_files()
            ofd.download_teamfolder_files()
            ofd.download_shared_files()
    return 0


if __name__ == '__main__':
    sys.exit(main())
