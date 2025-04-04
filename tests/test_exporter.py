"""
Tests for the main SynologyOfficeExporter class.
"""

import unittest
from unittest.mock import patch, MagicMock, mock_open
from io import BytesIO, StringIO
import os

from synology_office_exporter.exporter import SynologyOfficeExporter


class TestExporter(unittest.TestCase):
    """Test suite for the SynologyOfficeExporter class."""

    def setUp(self):
        """Set up test environment before each test."""
        # Create a mock SynologyDriveEx instance
        self.mock_synd = MagicMock()
        self.output_dir = '/tmp/synology_office_exports'

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

    @patch('os.path.exists')
    @patch('builtins.open', new_callable=mock_open)
    @patch('json.load')
    def test_process_document_tracking(self, mock_json_load, mock_file_open, mock_path_exists):
        """Test that documents are properly tracked for deletion detection."""
        mock_path_exists.return_value = True
        mock_json_load.return_value = {}

        # Mock BytesIO for download
        mock_data = BytesIO(b'test content')
        self.mock_synd.download_synology_office_file.return_value = mock_data

        with patch.object(SynologyOfficeExporter, 'save_bytesio_to_file'):
            exporter = SynologyOfficeExporter(self.mock_synd, output_dir=self.output_dir)

            # Clear any auto-loaded history
            exporter.current_file_paths = set()

            # Process a document - should add to current_file_paths
            exporter._process_document('test_file_id', '/path/to/document.odoc', 'hash123')

            # Verify the file ID was added to the tracking set
            self.assertIn('/path/to/document.odoc', exporter.current_file_paths)

    def test_stat_buf(self):
        """Test that statistics are correctly written to the provided buffer."""
        stat_buf = StringIO()

        with SynologyOfficeExporter(self.mock_synd, stat_buf=stat_buf,
                                    download_history_storage=MagicMock()) as exporter:
            exporter.total_found_files = 3
            exporter.skipped_files = 2
            exporter.downloaded_files = 1
            exporter.deleted_files = 4

        # Verify output matches expected format
        self.assertEqual(
            stat_buf.getvalue(),
            '\n===== Download Results Summary =====\n\n'
            'Total files found for backup: 3\n'
            'Files skipped: 2\n'
            'Files downloaded: 1\n'
            'Files deleted: 4\n'
            '=====================================\n'
        )

    def test_download_mydrive_files_with_exception(self):
        exporter = SynologyOfficeExporter(self.mock_synd, output_dir=self.output_dir)

        # Make list_folder raise an exception
        self.mock_synd.list_folder.side_effect = Exception('Network error')

        exporter.download_mydrive_files()
        self.assertTrue(exporter.had_exceptions)

    def test_download_shared_files_with_exception(self):
        exporter = SynologyOfficeExporter(self.mock_synd, output_dir=self.output_dir)

        # Make list_folder raise an exception
        self.mock_synd.shared_with_me.side_effect = Exception('Network error')

        exporter.download_shared_files()
        self.assertTrue(exporter.had_exceptions)

    def test_download_teamfolder_files_with_exception(self):
        exporter = SynologyOfficeExporter(self.mock_synd, output_dir=self.output_dir)

        # Make list_folder raise an exception
        self.mock_synd.get_teamfolder_info.side_effect = Exception('Network error')

        exporter.download_teamfolder_files()
        self.assertTrue(exporter.had_exceptions)

    def test_process_document_with_exception(self):
        exporter = SynologyOfficeExporter(self.mock_synd, output_dir=self.output_dir)

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

        exporter = SynologyOfficeExporter(self.mock_synd, output_dir='/tmp/synology_office_exports',
                                          download_history_storage=MagicMock())

        # Process directory which only has document.docx now
        exporter._process_directory('dir_id', 'test_dir')

        # Verify that the document was processed
        mock_process_document.assert_called_once_with(
            'file_id_1', '/path/to/document.odoc', 'hash1'
        )


if __name__ == '__main__':
    unittest.main()
