"""
Download History Management for Synology Office Exporter

This module provides the DownloadHistoryFile class, which manages the download
history and locking mechanism for the Synology Office Exporter.
"""

from filelock import FileLock, Timeout
import logging
import os
import json
from typing import Dict, Any, Set
from datetime import datetime

from synology_office_exporter.exception import DownloadHistoryError

# Constants for the download history file
HISTORY_VERSION = 1
HISTORY_MAGIC = 'SYNOLOGY_OFFICE_EXPORTER'


class DownloadHistoryFile:
    """
    Manages the download history file and locking mechanism.

    This class encapsulates all operations related to the download history,
    including file locking, loading, and saving history data. It provides a clean
    interface for the SynologyOfficeExporter to interact with the history data
    without being concerned with the implementation details.

    Attributes:
        skip_history (bool): If True, download history operations are skipped
        output_dir (str): Directory where the history file is stored
        download_history (dict): The current download history data
        force_download (bool): If True, force download regardless of history
    """

    def __init__(self, output_dir: str = '.', force_download: bool = False, skip_history: bool = False):
        """
        Initialize the DownloadHistoryFile.

        Args:
            output_dir: Directory where the history file will be stored
            force_download: If True, ignore existing history when checking if files need to be downloaded
            skip_history: If True, skip all history operations (for testing)
        """
        self.lock = None
        self.lock_file_path = os.path.join(output_dir, '.download_history.lock')
        self.download_history_file = os.path.join(output_dir, '.download_history.json')
        self.download_history: Dict[str, Any] = {}
        self.force_download = force_download
        self.skip_history = skip_history
        self.output_dir = output_dir

    def __enter__(self):
        """
        Enter the context manager.

        Acquires a lock on the download history file and loads the history data.

        Returns:
            DownloadHistoryFile: The instance itself for use in with statements.
        """
        self.lock_history()
        self.load_history()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit the context manager.

        Releases the lock on the download history file, saving any changes to history.

        Args:
            exc_type: Exception type if an exception was raised
            exc_val: Exception value if an exception was raised
            exc_tb: Traceback if an exception was raised
        """
        try:
            self.save_history()
        finally:
            self.unlock_history()

    def lock_history(self):
        """
        Acquire a lock on the download history file.

        Raises:
            DownloadHistoryError: If the lock cannot be acquired, indicating another process
                                is already running.
        """
        try:
            if not self.skip_history:
                self.lock = FileLock(self.lock_file_path)
                self.lock.acquire(blocking=False)
        except Timeout:
            logging.error('Download history lock file already exists. Another process may be running.')
            raise DownloadHistoryError('Download history lock file already exists. Another process may be running.')

    def unlock_history(self):
        """
        Release the lock on the download history file.
        """
        if self.lock:
            self.lock.release()

    def load_history(self):
        """
        Load the download history from a JSON file.

        Raises:
            DownloadHistoryError: If the history file exists but is corrupted or has an
                                incompatible format.
        """
        if self.skip_history or not os.path.exists(self.download_history_file):
            self.download_history = {}
            return

        try:
            with open(self.download_history_file, 'r') as f:
                history_data = json.load(f)
        except Exception as e:
            logging.error(f'Error loading download history: {e}')
            raise DownloadHistoryError(f'Error loading download history file: {e}')

        # Check if the history file has version information
        if isinstance(history_data, dict) and '_meta' in history_data:
            meta = history_data['_meta']

            # Verify magic number
            if meta.get('magic') != HISTORY_MAGIC:
                raise DownloadHistoryError(
                    f'History file has incorrect magic number. Expected {HISTORY_MAGIC}, got {meta.get("magic")}')

            # Check version compatibility
            version = meta.get('version', 0)
            if version > HISTORY_VERSION:
                raise DownloadHistoryError(
                    f'History file version {version} is newer than current version {HISTORY_VERSION}. ')

            # Extract the actual file history
            self.download_history = history_data.get('files', {})

    def save_history(self):
        """
        Save the download history to a JSON file.
        """
        if self.skip_history:
            return

        try:
            os.makedirs(os.path.dirname(self.download_history_file), exist_ok=True)

            # Create history data with metadata
            history_data = {
                '_meta': self._build_metadata(),
                'files': self.download_history
            }

            with open(self.download_history_file, 'w') as f:
                json.dump(history_data, f)
            logging.info(f'Saved download history for {len(self.download_history)} files')
        except Exception as e:
            logging.error(f'Error saving download history: {e}')

    @staticmethod
    def _build_metadata():
        """
        Generate metadata for the download history file.

        Returns:
            dict: A dictionary containing version, magic number, creation time, and program name.
        """
        return {
            'version': HISTORY_VERSION,
            'magic': HISTORY_MAGIC,
            'created': str(datetime.now()),
            'program': 'synology-office-exporter'
        }

    def get_history(self) -> Dict[str, Any]:
        """
        Get the current download history.

        Returns:
            dict: The current download history
        """
        return self.download_history

    def get_history_keys(self) -> Set[str]:
        """
        Get the set of keys (file paths) in the download history.

        Returns:
            set: Set of file paths in the history
        """
        return set(self.download_history.keys())

    def add_history_entry(self, file_path: str, file_id: str, hash_value: str):
        """
        Add or update an entry in the download history.

        Args:
            file_path: The path of the file
            file_id: The ID of the file
            hash_value: The hash value of the file
        """
        self.download_history[file_path] = {
            'file_id': file_id,
            'hash': hash_value,
            'download_time': str(datetime.now())
        }

    def remove_history_entry(self, file_path: str):
        """
        Remove an entry from the download history.

        Args:
            file_path: The path of the file to remove
        """
        if file_path in self.download_history:
            del self.download_history[file_path]

    def should_download(self, file_path: str, hash_value: str) -> bool:
        """
        Determine if a file should be downloaded based on history and force flag.

        Args:
            file_path: The path of the file
            hash_value: The current hash value of the file

        Returns:
            bool: True if the file should be downloaded, False otherwise
        """
        if self.force_download:
            return True

        if file_path not in self.download_history:
            return True

        return self.download_history[file_path]['hash'] != hash_value
