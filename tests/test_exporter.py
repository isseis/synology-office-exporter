"""
Tests for the SynologyOfficeExporter class
"""

import unittest
from unittest.mock import MagicMock, patch, mock_open
from io import BytesIO
import os
import tempfile
import shutil

from synology_office_exporter.exporter import SynologyOfficeExporter
from synology_office_exporter.download_history import DownloadHistoryFile
from tests.mock_download_history import MockDownloadHistory


class TestExporter(unittest.TestCase):
    """Test suite for the SynologyOfficeExporter class."""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.output_dir = os.path.join(self.temp_dir, "output")
        self.history_file = os.path.join(self.temp_dir, "history.json")

        # Create mocks
        self.mock_synd = MagicMock()
        self.history_storage = DownloadHistoryFile(self.history_file)

        # Initialize the exporter
        self.exporter = SynologyOfficeExporter(
            synd=self.mock_synd,
            download_history_storage=self.history_storage,
            output_dir=self.output_dir
        )

    def tearDown(self):
        """Tear down test fixtures"""
        # Remove temp directory
        shutil.rmtree(self.temp_dir)

    def test_convert_synology_to_ms_office_filename(self):
        """Test conversion of Synology Office filenames to MS Office filenames."""
        self.assertEqual(
            SynologyOfficeExporter.convert_synology_to_ms_office_filename('document.odoc'),
            'document.docx'
        )
        self.assertEqual(
            SynologyOfficeExporter.convert_synology_to_ms_office_filename('spreadsheet.osheet'),
            'spreadsheet.xlsx'
        )
        self.assertEqual(
            SynologyOfficeExporter.convert_synology_to_ms_office_filename('presentation.oslides'),
            'presentation.pptx'
        )
        self.assertIsNone(
            SynologyOfficeExporter.convert_synology_to_ms_office_filename('not_office_file.txt')
        )

    @patch('os.makedirs')
    @patch('builtins.open', new_callable=mock_open)
    def test_save_bytesio_to_file(self, mock_file_open, mock_makedirs):
        """Test saving BytesIO content to a file."""
        test_content = b'test content'
        test_path = os.path.join(self.output_dir, 'test.docx')

        # Create BytesIO with test content
        data = BytesIO(test_content)

        SynologyOfficeExporter.save_bytesio_to_file(data, test_path)

        # Verify directory was created
        mock_makedirs.assert_called_once_with(self.output_dir, exist_ok=True)

        # Verify file was opened correctly
        mock_file_open.assert_called_once_with(test_path, 'wb')

        # Verify content was written
        mock_file_open().write.assert_called_once_with(test_content)

    def test_process_document_tracking(self):
        """Test that documents are properly tracked for deletion detection."""
        # Mock BytesIO for download
        self.mock_synd.download_synology_office_file.return_value = BytesIO(b'test content')

        with patch.object(SynologyOfficeExporter, 'save_bytesio_to_file'):
            exporter = SynologyOfficeExporter(self.mock_synd, MockDownloadHistory(), output_dir=self.output_dir)

            # Clear any auto-loaded history
            exporter.current_file_paths = set()

            # Process a document - should add to current_file_paths
            exporter._process_document('test_file_id', '/path/to/document.odoc', 'hash123')

            # Verify the file ID was added to the tracking set
            self.assertIn('/path/to/document.odoc', exporter.current_file_paths)

    def test_statistics_tracking(self):
        """Test that statistics are correctly tracked and can be retrieved via get_summary."""
        # Create the exporter
        with SynologyOfficeExporter(self.mock_synd, MockDownloadHistory(),
                                    output_dir=self.output_dir) as exporter:
            # Set the statistics values
            exporter.total_found_files = 3
            exporter.skipped_files = 2
            exporter.downloaded_files = 1
            exporter.deleted_files = 4

            # Get the summary
            summary = exporter.get_summary()

            # Verify the summary matches the expected format
            expected_summary = (
                'Total files found for backup: 3\n'
                'Files skipped: 2\n'
                'Files downloaded: 1\n'
                'Files deleted: 4\n'
            )
            self.assertEqual(summary, expected_summary)

    def test_download_mydrive_files_with_exception(self):
        exporter = SynologyOfficeExporter(self.mock_synd, MockDownloadHistory(), output_dir=self.output_dir)

        # Make list_folder raise an exception
        self.mock_synd.list_folder.side_effect = Exception('Network error')

        exporter.download_mydrive_files()
        self.assertTrue(exporter.had_exceptions)

    def test_download_shared_files_with_exception(self):
        exporter = SynologyOfficeExporter(self.mock_synd, MockDownloadHistory(), output_dir=self.output_dir)

        # Make list_folder raise an exception
        self.mock_synd.shared_with_me.side_effect = Exception('Network error')

        exporter.download_shared_files()
        self.assertTrue(exporter.had_exceptions)

    def test_download_teamfolder_files_with_exception(self):
        exporter = SynologyOfficeExporter(self.mock_synd, MockDownloadHistory(), output_dir=self.output_dir)

        # Make list_folder raise an exception
        self.mock_synd.get_teamfolder_info.side_effect = Exception('Network error')

        exporter.download_teamfolder_files()
        self.assertTrue(exporter.had_exceptions)

    def test_process_document_with_exception(self):
        exporter = SynologyOfficeExporter(self.mock_synd, MockDownloadHistory(), output_dir=self.output_dir)

        # Make download_synology_office_file raise an exception
        self.mock_synd.download_synology_office_file.side_effect = Exception('Download error')

        exporter._process_document('testfile', '/path/to/test.odoc', 'hash123')
        self.assertTrue(exporter.had_exceptions)

    @patch('synology_office_exporter.exporter.SynologyOfficeExporter._process_document')
    def test_process_directory(self, mock_process_document):
        """Test the complete process of tracking and removing deleted files."""
        # Mock SynologyDriveEx methods
        self.mock_synd.list_folder.return_value = {
            'success': True,
            'data': {'items': [
                {
                    'file_id': 'file_id_1',
                    'name': 'document.odoc',
                    'display_path': '/path/to/document.odoc',
                    'content_type': 'document',
                    'hash': 'hash1'
                },
            ]}
        }
        self.mock_synd.download_synology_office_file.return_value = BytesIO(b'file content')

        exporter = SynologyOfficeExporter(self.mock_synd, MockDownloadHistory(),
                                          output_dir='/tmp/synology_office_exports')

        # Process directory which only has document.docx now
        exporter._process_directory('dir_id', 'test_dir')

        # Verify that the document was processed
        mock_process_document.assert_called_once_with(
            'file_id_1', '/path/to/document.odoc', 'hash1'
        )

    def test_get_summary(self):
        """Test that get_summary returns correct statistics"""
        # Set up some statistics
        self.exporter.total_found_files = 10
        self.exporter.skipped_files = 3
        self.exporter.downloaded_files = 5
        self.exporter.deleted_files = 2

        # Get summary
        summary = self.exporter.get_summary()

        # Check that summary contains all statistics
        self.assertIn("Total files found for backup: 10", summary)
        self.assertIn("Files skipped: 3", summary)
        self.assertIn("Files downloaded: 5", summary)
        self.assertIn("Files deleted: 2", summary)


if __name__ == '__main__':
    unittest.main()
