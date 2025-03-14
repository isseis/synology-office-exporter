#! /usr/bin/python3
"""
Synology Office File Export Tool - Library

This module provides the core functionality to download and convert Synology Office files to their
Microsoft Office equivalents. It connects to a Synology NAS and processes files from shared folders,
team folders, and personal drives.

File conversions performed:
- Synology Spreadsheet (.osheet) -> Microsoft Excel (.xlsx)
- Synology Document (.odoc) -> Microsoft Word (.docx)
- Synology Slides (.oslides) -> Microsoft PowerPoint (.pptx)

This is a library module. For command-line usage, please use main.py.

Requirements:
- Python 3.6+
- synology-drive-ex package
- python-dotenv package (for main.py)

See main.py for command line usage instructions.
"""

from io import BytesIO
import logging
import os
import sys
from typing import Optional
import json
from datetime import datetime

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
    def __init__(self, synd: SynologyDriveEx, output_dir: str = '.', force_download: bool = False):
        self.synd = synd
        self.output_dir = output_dir
        self.download_history_file = os.path.join(output_dir, '.download_history.json')
        self.download_history = {}
        self.force_download = force_download
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
        logging.debug(f'Processing directory: {dir_name}')

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
        logging.debug(f'Processing {display_path}')
        try:
            # Check if file is already downloaded and unchanged
            if not self.force_download and (file_id in self.download_history
                                            and self.download_history[file_id]['hash'] == hash):
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


if __name__ == '__main__':
    # main.pyを使うよう促す
    print("This file is a library. Please use main.py to run the program.")
    print("Example: python main.py --help")
    sys.exit(1)
