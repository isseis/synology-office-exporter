"""
Tests for the functionality that removes output files when Synology Office files are deleted.
"""

import unittest
from unittest.mock import patch, MagicMock

from synology_office_exporter.exporter import SynologyOfficeExporter


class TestDeletedFiles(unittest.TestCase):
    """Test suite for verifying proper cleanup of exported files when original Synology Office files are deleted."""

    def setUp(self):
        """Set up test environment before each test."""
        self.mock_synd = MagicMock()

        self.sample_history = {
            '/path/to/document.odoc': {
                'file_id': 'file_id_1',
                'hash': 'hash1',
                'path': '/path/to/document.odoc',
                'download_time': '2023-01-01 12:00:00'
            },
            '/path/to/spreadsheet.osheet': {
                'file_id': 'file_id_2',
                'hash': 'hash2',
                'path': '/path/to/spreadsheet.osheet',
                'download_time': '2023-01-01 12:00:00'
            }
        }

    @patch('os.path.exists')
    @patch('os.remove')
    def test_remove_deleted_files(self, mock_remove, mock_path_exists):
        """Test that files deleted from NAS are removed from the output directory."""
        mock_path_exists.return_value = True

        download_history = MagicMock()
        with SynologyOfficeExporter(self.mock_synd, output_dir='/tmp/synology_office_exports',
                                    download_history_storage=download_history) as exporter:
            # Simliate that the history file is loaded, and there were two files when the exporter was executed
            # last time.
            download_history.get_history_keys.return_value = set(
                ['/path/to/document.odoc', '/path/to/spreadsheet.osheet'])

            # Simulate that one file still exists on NAS (document.odoc) and one is deleted (spreadsheet.osheet)
            exporter.current_file_paths = set(['/path/to/document.odoc'])

        # Check that the deleted file is removed from history
        download_history.remove_history_entry.assert_called_once_with('/path/to/spreadsheet.osheet')
        mock_remove.assert_called_once_with('/tmp/synology_office_exports/path/to/spreadsheet.xlsx')

        # Check that the counter was incremented
        self.assertEqual(exporter.deleted_files, 1)

    @patch('os.remove')
    def test_file_already_removed(self, mock_remove):
        """Test handling of files that are already removed from the filesystem."""
        download_history = MagicMock()
        exporter = SynologyOfficeExporter(self.mock_synd, output_dir='/tmp/synology_office_exports',
                                          download_history_storage=download_history)
        # Simliate that the history file is loaded, and there were two files when the exporter was executed
        # last time.
        download_history.get_history_keys.return_value = set(
            ['/path/to/document.odoc', '/path/to/spreadsheet.osheet'])

        # Simulate that one file is deleted from NAS
        exporter.current_file_paths = {'/path/to/document.odoc'}

        # Simulate that the file to be removed doesn't exist locally.
        mock_remove.side_effect = FileNotFoundError

        # Call the method to test
        exporter._remove_deleted_files()

        # Check that os.remove was called.
        mock_remove.assert_called_once_with('/tmp/synology_office_exports/path/to/spreadsheet.xlsx')

        # Check that the file is removed from history
        download_history.remove_history_entry.assert_called_once_with('/path/to/spreadsheet.osheet')

        # Check that the counter wasn't incremented (no actual deletion)
        self.assertEqual(exporter.deleted_files, 0)

    @patch('os.remove')
    def test_no_files_to_remove(self, mock_remove):
        """Test that no files are removed when all files still exist on NAS."""
        # Simliate that the history file is loaded, and there were two files when the exporter was
        # executed last time.
        download_history = MagicMock()
        download_history.get_history_keys.return_value = set(
            ['/path/to/document.odoc', '/path/to/spreadsheet.osheet'])
        with SynologyOfficeExporter(self.mock_synd, output_dir='/tmp/synology_office_exports',
                                    download_history_storage=download_history) as exporter:
            # Simulate that all files still exist on the NAS
            exporter.current_file_paths = {'/path/to/document.odoc', '/path/to/spreadsheet.osheet'}

        # Check that os.remove was not called
        mock_remove.assert_not_called()

        # Check that the history is unchanged
        download_history.remove_history_entry.assert_not_called()

        # Check that the counter wasn't incremented
        self.assertEqual(exporter.deleted_files, 0)

    @patch('os.remove')
    def test_save_updated_history(self, mock_remove):
        """Test that updated history (after removal) is saved correctly."""
        download_history = MagicMock()
        download_history.get_history_keys.return_value = set(['/path/to/document.odoc'])

        with SynologyOfficeExporter(self.mock_synd, output_dir='/tmp/synology_office_exports',
                                    download_history_storage=download_history):
            pass

        # Verify that the deleted file from the NAS device is removed locally, and history is updated.
        download_history.remove_history_entry.assert_called_once_with('/path/to/document.odoc')
        mock_remove.assert_called_once_with('/tmp/synology_office_exports/path/to/document.docx')

    @patch('os.remove')
    def test_exception_during_file_deletion_stops_further_deletions(self, mock_remove):
        """Test that an exception during file deletion stops further deletions."""
        download_history = MagicMock()

        exporter = SynologyOfficeExporter(
            self.mock_synd, output_dir='/tmp/synology_office_exports', download_history_storage=download_history)

        # Simliate that the history file is loaded, and there were two files when the exporter was executed
        # last time.
        download_history.get_history_keys.return_value = set(
            ['/path/to/document.odoc', '/path/to/spreadsheet.osheet'])

        # Mark both files as deleted
        exporter.current_file_paths = set()

        # Make first deletion raise an exception
        mock_remove.side_effect = Exception('Permission denied')

        # Run the method
        exporter._remove_deleted_files()

        # Verify exception flag was set
        self.assertTrue(exporter.had_exceptions)

        mock_remove.assert_called_once_with('/tmp/synology_office_exports/path/to/document.docx')

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._remove_deleted_files')
    def test_file_deletion_in_context_manager(self, mock_remove_deleted_files):
        exporter = SynologyOfficeExporter(self.mock_synd, output_dir='/tmp/synology_office_exports',
                                          download_history_storage=MagicMock())
        # Ensure no exceptions
        exporter.had_exceptions = False
        exporter.__exit__(None, None, None)

        # Verify deletion occurred
        mock_remove_deleted_files.assert_called_once()

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._remove_deleted_files')
    def test_no_file_deletion_in_context_manager_with_exceptions_handled(self, mock_remove_deleted_files):
        exporter = SynologyOfficeExporter(self.mock_synd, output_dir='/tmp/synology_office_exports',
                                          download_history_storage=MagicMock())
        # Simulate exceptions occured but captured
        exporter.had_exceptions = True
        exporter.__exit__(None, None, None)

        # Verify deletion not occurred
        mock_remove_deleted_files.assert_not_called()

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._remove_deleted_files')
    def test_no_file_deletion_in_context_manager_with_exceptions_not_handled(self, mock_remove_deleted_files):
        exporter = SynologyOfficeExporter(self.mock_synd, output_dir='/tmp/synology_office_exports',
                                          download_history_storage=MagicMock())
        # Simulate exceptions occured and not captured
        exporter.had_exceptions = False
        exporter.__exit__(Exception, None, None)

        # Verify deletion not occurred
        mock_remove_deleted_files.assert_not_called()

    @patch('os.remove')
    def test_no_file_deletion_when_exception_occurs_and_captured(self, mock_remove):
        exporter = SynologyOfficeExporter(self.mock_synd, output_dir='/tmp/synology_office_exports')
        # Simulate an exception during processing, captured by except block which sets had_exceptions.
        exporter.had_exceptions = True
        exporter.__exit__(None, None, None)

        # Verify no files were deleted
        mock_remove.assert_not_called()

    @patch('os.remove')
    def test_no_file_deletion_when_exception_occurs_and_not_captured(self, mock_remove):
        exporter = SynologyOfficeExporter(self.mock_synd, output_dir='/tmp/synology_office_exports')
        # Simulate an exception during processing, and not captured.
        exporter.had_exceptions = False
        exporter.__exit__(ValueError, ValueError('Test exception'), None)

        # Verify no files were deleted
        mock_remove.assert_not_called()


if __name__ == '__main__':
    unittest.main()
