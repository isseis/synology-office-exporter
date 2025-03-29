"""
Tests for the main SynologyOfficeExporter class.
"""

from datetime import datetime
import unittest
from unittest.mock import patch, MagicMock, mock_open
from io import BytesIO, StringIO
import os

from synology_office_exporter.download_history import HISTORY_MAGIC, DownloadHistoryFile
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

    @patch('builtins.open', new_callable=mock_open)
    @patch('json.dump')
    def test_save_download_history(self, mock_json_dump, mock_file_open):
        """Test that download history is saved correctly."""
        with patch.object(DownloadHistoryFile, 'load_history'):
            with patch.object(DownloadHistoryFile, '_build_metadata') as mock_build_metadata:
                mock_build_metadata.return_value = {
                    'version': 1,
                    'magic': HISTORY_MAGIC,
                    'created': '2025-03-22 14:43:44.966404',
                    'program': 'synology-office-exporter'
                }

                exporter = SynologyOfficeExporter(self.mock_synd, output_dir=self.output_dir)
                exporter.history_storage.add_history_entry('/path/to/document.odoc', 'file_id_1', 'hash1',
                                                           datetime(2023, 1, 1, 12, 0, 0))

                # Trigger save
                exporter.history_storage.save_history()

                # Verify file was opened correctly
                history_file = os.path.join(self.output_dir, '.download_history.json')
                mock_file_open.assert_called_with(history_file, 'w')

                # Verify history was dumped
                mock_json_dump.assert_called_once_with(
                    {
                        '_meta': mock_build_metadata.return_value,
                        'files': {
                            '/path/to/document.odoc': {
                                'hash': 'hash1',
                                'file_id': 'file_id_1',
                                'download_time': '2023-01-01 12:00:00'
                            }
                        }
                    },
                    mock_file_open())

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

        with SynologyOfficeExporter(self.mock_synd, stat_buf=stat_buf, skip_history=True) as exporter:
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


if __name__ == '__main__':
    unittest.main()
