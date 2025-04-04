"""
Synology Office File Export Tool - Library

This module provides the core functionality to download and convert Synology Office files to their
Microsoft Office equivalents. It connects to a Synology NAS and processes files from shared folders,
team folders, and personal drives.

File conversions performed:
- Synology Spreadsheet (.osheet) -> Microsoft Excel (.xlsx)
- Synology Document (.odoc) -> Microsoft Word (.docx)
- Synology Slides (.oslides) -> Microsoft PowerPoint (.pptx)

This is a library module. For command-line usage, please use cli.py.

Requirements:
- Python 3.6+
- synology-drive package
- filelock package
- python-dotenv package (for cli.py)

See cli.py for command line usage instructions.
"""

from io import BytesIO, StringIO
import logging
import os
import sys
from typing import Optional

from synology_office_exporter.synology_drive_api import SynologyDriveEx
from synology_office_exporter.download_history import DownloadHistoryFile


class SynologyOfficeExporter:
    """
    A tool for exporting and converting Synology Office documents to Microsoft Office formats.

    This class provides the ability to traverse a Synology NAS, identify Synology Office
    documents (odoc, osheet, oslides), and convert them to their Microsoft Office
    counterparts (docx, xlsx, pptx). It handles personal files from My Drive,
    team folder documents, and files shared with the user.

    Features:
    - Maintains a download history to avoid re-downloading unchanged files
    - Preserves folder structure when exporting files
    - Provides detailed logging of operations
    - Tracks statistics about found, skipped, downloaded, and deleted files
    - Supports context manager protocol for proper resource management
    - Handles encrypted files and various error conditions gracefully
    - Removes MS Office files when the source Synology Office files are deleted
    - Uses file locking mechanism to prevent multiple processes from running simultaneously

    Usage example:
        with SynologyOfficeExporter(synd_client, output_dir='./exports') as exporter:
            exporter.download_mydrive_files()
            exporter.download_teamfolder_files()
            exporter.download_shared_files()
    """

    def __init__(self, synd: SynologyDriveEx, output_dir: str = '.', force_download: bool = False,
                 stat_buf: StringIO = None, download_history_storage: DownloadHistoryFile = None):
        """
        Initialize the SynologyOfficeExporter with the given parameters.

        Args:
            synd: SynologyDriveEx instance for API communication
            output_dir: Directory where converted files will be saved
            force_download: If True, files will be downloaded regardless of download history
            stat_buf: StringIO buffer to write statistics output
        """
        self.synd = synd
        self.output_dir = output_dir
        self.stat_buf = stat_buf

        # Initialize history storage
        if download_history_storage is None:
            self.__history_storage = DownloadHistoryFile(
                output_dir=output_dir,
                force_download=force_download
            )
        else:
            self.__history_storage = download_history_storage

        # Counters for tracking statistics
        self.total_found_files = 0
        self.skipped_files = 0
        self.downloaded_files = 0
        self.deleted_files = 0

        # Set to track current files on NAS
        self.current_file_paths = set()

        # Flag to skip file deletion if any exceptions occurred
        self.had_exceptions = False

    def __enter__(self):
        """
        Context manager entry method.

        Locks the download history file and loads existing history data.

        Returns:
            SynologyOfficeExporter: The instance itself for use in with statements.
        """
        self.__history_storage.lock_history()
        self.__history_storage.load_history()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Context manager exit method that saves history and removes deleted files.

        Saves the download history and unlocks the download history file when exiting the context.
        Removes files that have been deleted from the NAS only if no exceptions occurred.

        Args:
            exc_type: Exception type if an exception was raised
            exc_value: Exception value if an exception was raised
            traceback: Traceback if an exception was raised
        """
        # Set exception flag if an exception occurred
        if exc_type is not None:
            self.had_exceptions = True
            logging.warning('Exception occurred during processing, skipping file deletion')

        try:
            # Only remove deleted files if no exceptions occurred
            if not self.had_exceptions:
                self._remove_deleted_files()
            else:
                logging.info('Skipping file deletion due to exceptions during processing')

            self.__history_storage.save_history()
        except Exception:
            raise
        finally:
            self.__history_storage.unlock_history()

        self._dump_summary()

    def _remove_deleted_files(self):
        """
        Remove files from the output directory that have been deleted from the NAS.

        This method identifies files that exist in the download history but not in the current
        file list, deletes those files from the local filesystem, and updates the download history.
        The method will set had_exceptions flag if errors occur during deletion.
        """
        logging.info('Removing deleted files...')
        deleted_file_paths = sorted(self.__history_storage.get_history_keys() - self.current_file_paths)
        for file_path in deleted_file_paths:
            try:
                offline_name = self.convert_synology_to_ms_office_filename(file_path)
                if offline_name is None:
                    logging.error(f'Cannot determine offline name for {file_path}')
                    continue
                output_path = os.path.join(self.output_dir, offline_name.lstrip('/'))

                logging.info(f'Removing deleted file: {output_path}')
                try:
                    os.remove(output_path)
                    self.deleted_files += 1
                except FileNotFoundError:
                    logging.warning(f'File already removed: {output_path}')

                self.__history_storage.remove_history_entry(file_path)

            except Exception as e:
                logging.error(f'Error removing deleted file {file_path}: {e}')
                # Set the exception flag to prevent future deletions in this session
                self.had_exceptions = True
                return

        logging.info(f'Removed {self.deleted_files} files that were deleted from the NAS')

    def download_mydrive_files(self):
        """
        Download and process all Synology Office files from the user's personal My Drive.

        This method traverses the user's personal storage space on the Synology NAS,
        identifying and converting all compatible Synology Office documents.

        Exceptions during processing are caught and logged, allowing the process
        to continue with other files. The had_exceptions flag is set if errors occur.
        """
        logging.info('Downloading My Drive files...')
        try:
            self._process_directory('/mydrive', 'My Drive')
        except Exception as e:
            logging.error(f'Error downloading My Drive files: {e}')
            self.had_exceptions = True

    def download_shared_files(self):
        """
        Download and process all Synology Office files that are shared with the user.

        This method identifies and converts all compatible Synology Office documents
        from files and folders that have been shared with the current user.

        Exceptions during processing are caught and logged, allowing the process
        to continue with other files. The had_exceptions flag is set if errors occur.
        """
        logging.info('Downloading shared files...')
        try:
            for item in self.synd.shared_with_me():
                try:
                    self._process_item(item)
                except Exception as e:
                    logging.error(f'Error processing shared item {item.get("name")}: {e}')
                    self.had_exceptions = True
        except Exception as e:
            logging.error(f'Error accessing shared files: {e}')
            self.had_exceptions = True

    def download_teamfolder_files(self):
        """
        Download and process all Synology Office files from team folders.

        This method traverses all accessible team folders on the Synology NAS,
        identifying and converting all compatible Synology Office documents.

        Exceptions during processing are caught and logged, allowing the process
        to continue with other files and folders. The had_exceptions flag is set if errors occur.
        """
        logging.info('Downloading team folder files...')
        try:
            for name, file_id in self.synd.get_teamfolder_info().items():
                try:
                    self._process_directory(file_id, name)
                except Exception as e:
                    logging.error(f'Error processing team folder {name}: {e}')
                    self.had_exceptions = True
        except Exception as e:
            logging.error(f'Error accessing team folders: {e}')
            self.had_exceptions = True

    def _process_item(self, item):
        """
        Process a single item (file or directory) from the Synology NAS.

        This method handles both directories and documents, skipping encrypted files.
        For directories, it recursively processes all contained items.
        For documents, it passes them to the appropriate document processor.

        Args:
            item: Dictionary containing item information from the Synology API

        The had_exceptions flag is set if errors occur during processing.
        """
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
            logging.error(f'Error processing item {item.get("name")}: {e}')
            self.had_exceptions = True

    def _process_directory(self, file_id: str, dir_name: str):
        """
        Process a directory and all its contents from the Synology NAS.

        This method lists all items in the specified directory and processes
        each one by calling _process_item.

        Args:
            file_id: The ID of the directory to process
            dir_name: The display name of the directory for logging purposes

        The had_exceptions flag is set if errors occur during processing.
        """
        logging.debug(f'Processing directory: {dir_name}')

        try:
            resp = self.synd.list_folder(file_id)
            if not resp['success']:
                logging.error(f'Failed to list folder {dir_name}: {resp.get("error")}')
                self.had_exceptions = True
                return

            for item in resp['data']['items']:
                self._process_item(item)
        except Exception as e:
            logging.error(f'Error processing directory {dir_name}: {e}')
            self.had_exceptions = True

    def _process_document(self, file_id: str, display_path: str, hash: str):
        """
        Process and download a Synology Office document.

        This method checks if the document should be downloaded (based on history and force flag),
        downloads it if needed, converts it to the corresponding Microsoft Office format,
        and updates the download history.

        Args:
            file_id: The ID of the file to download
            display_path: The display path of the file
            hash: The hash of the file to track changes

        The had_exceptions flag is set if errors occur during processing.
        The current_file_paths set is updated to track which files exist on the NAS.
        """
        logging.debug(f'Processing {display_path}')
        try:
            offline_name = self.convert_synology_to_ms_office_filename(display_path)
            if not offline_name:
                logging.debug(f'Skipping non-Synology Office file: {display_path}')
                return

            self.current_file_paths.add(display_path)
            self.total_found_files += 1

            # Check if file is already downloaded and unchanged
            if not self.__history_storage.should_download(display_path, hash):
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
            self.__history_storage.add_history_entry(display_path, file_id, hash)
        except Exception as e:
            logging.error(f'Error downloading document {display_path}: {e}')
            self.had_exceptions = True

    @staticmethod
    def convert_synology_to_ms_office_filename(name: str) -> Optional[str]:
        """
        Converts Synology Office file names to Microsoft Office file names.

        File type conversions:
        - osheet -> xlsx (Excel)
        - odoc -> docx (Word)
        - oslides -> pptx (PowerPoint)

        Args:
            name: The file name to convert

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

    def _dump_summary(self):
        """
        Dump statistics for the execution results.

        This method writes a summary of the operation to the stat_buf if one was provided,
        including counts of found, skipped, downloaded, and deleted files.
        """
        if self.stat_buf is not None:
            self.stat_buf.write('\n===== Download Results Summary =====\n\n')
            self.stat_buf.write(f'Total files found for backup: {self.total_found_files}\n')
            self.stat_buf.write(f'Files skipped: {self.skipped_files}\n')
            self.stat_buf.write(f'Files downloaded: {self.downloaded_files}\n')
            self.stat_buf.write(f'Files deleted: {self.deleted_files}\n')
            self.stat_buf.write('=====================================\n')


if __name__ == '__main__':
    print('This file is a library. Please use main.py to run the program.')
    print('Example: python main.py --help')
    sys.exit(1)
