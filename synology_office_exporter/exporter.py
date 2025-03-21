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

from synology_office_exporter.synology_drive_api import SynologyDriveEx

# Mapping of log level strings to actual log levels
LOG_LEVELS = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL
}


class SynologyOfficeExporter:
    """
    A tool for exporting and converting Synology Office documents to Microsoft Office formats.

    This class provides the ability to traverse a Synology NAS, identif3y Synology Office
    documents (odoc, osheet, oslides), and convert them to their Microsoft Office
    counterparts (docx, xlsx, pptx). It handles personal files from My Drive,
    team folder documents, and files shared with the user.

    Features:
    - Maintains a download history to avoid re-downloading unchanged files
    - Preserves folder structure when exporting files
    - Provides detailed logging of operations
    - Tracks statistics about found, skipped, and downloaded files
    - Supports context manager protocol for proper resource management
    - Handles encrypted files and various error conditions gracefully

    Usage example:
        with SynologyOfficeExporter(synd_client, output_dir="./exports") as exporter:
            exporter.download_mydrive_files()
            exporter.download_teamfolder_files()
            exporter.download_shared_files()
            exporter.print_summary()
    """

    def __init__(self, synd: SynologyDriveEx, output_dir: str = '.', force_download: bool = False):
        """
        Initialize the SynologyOfficeExporter with the given parameters.

        Args:
            synd: SynologyDriveEx instance for API communication
            output_dir: Directory where converted files will be saved
            force_download: If True, files will be downloaded regardless of download history
        """
        self.synd = synd
        self.output_dir = output_dir
        self.download_history_file = os.path.join(output_dir, '.download_history.json')
        self.download_history = {}
        self.force_download = force_download
        self._load_download_history()

        # Counters for tracking statistics
        self.total_found_files = 0
        self.skipped_files = 0
        self.downloaded_files = 0

    def __enter__(self):
        """
        Context manager entry method.

        Returns:
            SynologyOfficeExporter: The instance itself for use in with statements.
        """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Context manager exit method. Saves the download history when exiting the context.

        Args:
            exc_type: Exception type if an exception was raised
            exc_value: Exception value if an exception was raised
            traceback: Traceback if an exception was raised
        """
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
        """
        Download and process all Synology Office files from the user's personal My Drive.

        This method traverses the user's personal storage space on the Synology NAS,
        identifying and converting all compatible Synology Office documents.

        Exceptions during processing are caught and logged, allowing the process
        to continue with other files.
        """
        logging.info('Downloading My Drive files...')
        try:
            self._process_directory('/mydrive', 'My Drive')
        except Exception as e:
            logging.error(f'Error downloading My Drive files: {e}')

    def download_shared_files(self):
        """
        Download and process all Synology Office files that are shared with the user.

        This method identifies and converts all compatible Synology Office documents
        from files and folders that have been shared with the current user.

        Exceptions during processing are caught and logged, allowing the process
        to continue with other files.
        """
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
        """
        Download and process all Synology Office files from team folders.

        This method traverses all accessible team folders on the Synology NAS,
        identifying and converting all compatible Synology Office documents.

        Exceptions during processing are caught and logged, allowing the process
        to continue with other files and folders.
        """
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
            offline_name = self.get_offline_name(display_path)
            if not offline_name:
                logging.debug(f'Skipping non-Synology Office file: {display_path}')
                return

            self.total_found_files += 1

            # Check if file is already downloaded and unchanged
            if not self.force_download and (file_id in self.download_history
                                            and self.download_history[file_id]['hash'] == hash):
                logging.info(f'Skipping already downloaded file: {display_path}')
                self.skipped_files += 1
                return

            # Convert absolute path to relative by removing leading slashes
            offline_name = offline_name.lstrip('/')

            # Create full path with output directory
            output_path = os.path.join(self.output_dir, offline_name)

            logging.info(f'Downloading {display_path} => {output_path}')
            data = self.synd.download_synology_office_file(file_id)
            self.save_bytesio_to_file(data, output_path)

            self.downloaded_files += 1

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

        This method creates any necessary parent directories before writing the file.
        The BytesIO position is reset to the beginning before reading.

        Args:
            data: BytesIO object containing the file data
            path: Destination file path where data will be saved
        """
        data.seek(0)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'wb') as f:
            f.write(data.getvalue())

    def print_summary(self):
        """
        Display statistics for the execution results.
        """
        print("\n===== Download Results Summary =====")
        print(f"Total files found for backup: {self.total_found_files}")
        print(f"Files skipped: {self.skipped_files}")
        print(f"Files downloaded: {self.downloaded_files}")
        print("=====================================")


if __name__ == '__main__':
    print("This file is a library. Please use main.py to run the program.")
    print("Example: python main.py --help")
    sys.exit(1)
