"""Unit tests for the SynologyOfficeExporter statistics tracking functionality."""
import unittest
from unittest.mock import Mock, patch
import os
import tempfile
from io import BytesIO, StringIO

from synology_office_exporter.exporter import SynologyOfficeExporter


class TestSynologyOfficeExporter(unittest.TestCase):
    """
    Test suite for the SynologyOfficeExporter class.

    This class tests the functionality of the SynologyOfficeExporter, particularly focusing on:
    - Statistics tracking and reporting

    Each test case sets up a controlled environment with mocked dependencies
    and temporary files to ensure tests are isolated and repeatable.
    """

    def setUp(self):
        # Create a mock for SynologyDriveEx
        self.mock_synd = Mock()

        # Create a temporary directory for testing
        self.temp_dir = tempfile.mkdtemp()

        # Create an instance of the exporter
        self.exporter = SynologyOfficeExporter(self.mock_synd, output_dir=self.temp_dir)

        # Clear download history
        self.exporter.download_history = {}

        # Reset statistics counters
        self.exporter.total_found_files = 0
        self.exporter.skipped_files = 0
        self.exporter.downloaded_files = 0

    def tearDown(self):
        # Remove the temporary directory
        history_file = os.path.join(self.temp_dir, '.download_history.json')
        if os.path.exists(history_file):
            os.remove(history_file)
        os.rmdir(self.temp_dir)

    def test_process_document_new_file(self):
        """Test processing a new file"""
        # Set up the mock
        mock_data = BytesIO(b'test data')
        self.mock_synd.download_synology_office_file.return_value = mock_data

        # File information for testing
        file_id = 'test_file_id'
        display_path = 'test_document.odoc'
        file_hash = 'test_hash'

        # Execute the test
        with patch.object(SynologyOfficeExporter, 'save_bytesio_to_file') as mock_save:
            self.exporter._process_document(file_id, display_path, file_hash)

            # Verify
            self.assertEqual(self.exporter.total_found_files, 1)
            self.assertEqual(self.exporter.downloaded_files, 1)
            self.assertEqual(self.exporter.skipped_files, 0)
            mock_save.assert_called_once()

    def test_process_document_already_downloaded(self):
        """Test processing an already downloaded file"""
        # File information for testing
        file_id = 'test_file_id'
        display_path = 'test_document.odoc'
        file_hash = 'test_hash'

        # Add file to download history
        self.exporter.download_history = {
            file_id: {
                'hash': file_hash,
                'path': display_path,
                'output_path': os.path.join(self.temp_dir, 'test_document.docx'),
                'download_time': '2023-01-01 00:00:00'
            }
        }

        # Execute the test
        with patch.object(SynologyOfficeExporter, 'save_bytesio_to_file') as mock_save:
            self.exporter._process_document(file_id, display_path, file_hash)

            # Verify
            self.assertEqual(self.exporter.total_found_files, 1)
            self.assertEqual(self.exporter.downloaded_files, 0)
            self.assertEqual(self.exporter.skipped_files, 1)
            mock_save.assert_not_called()

    def test_process_non_office_document(self):
        """Test processing a non-Synology Office file"""
        # File information for testing
        file_id = 'test_file_id'
        display_path = 'test_document.pdf'
        file_hash = 'test_hash'

        # Execute the test
        with patch.object(SynologyOfficeExporter, 'save_bytesio_to_file') as mock_save:
            self.exporter._process_document(file_id, display_path, file_hash)

            # Verify
            self.assertEqual(self.exporter.total_found_files, 0)
            self.assertEqual(self.exporter.downloaded_files, 0)
            self.assertEqual(self.exporter.skipped_files, 0)
            mock_save.assert_not_called()

    def test_print_summary(self):
        """Test output of statistics"""
        # Set counters
        self.exporter.total_found_files = 10
        self.exporter.downloaded_files = 7
        self.exporter.skipped_files = 3

        # Capture standard output
        with patch('sys.stdout', new=StringIO()) as fake_out:
            self.exporter.print_summary()
            output = fake_out.getvalue()

            # Verify output content
            self.assertIn("Total files found for backup: 10", output)
            self.assertIn("Files skipped: 3", output)
            self.assertIn("Files downloaded: 7", output)

    def test_force_download(self):
        """Test that files are re-downloaded when force_download=True even if already downloaded"""
        # Enable force_download
        self.exporter.force_download = True

        # File information for testing
        file_id = 'test_file_id'
        display_path = 'test_document.odoc'
        file_hash = 'test_hash'

        # Add file to download history
        self.exporter.download_history = {
            file_id: {
                'hash': file_hash,
                'path': display_path,
                'output_path': os.path.join(self.temp_dir, 'test_document.docx'),
                'download_time': '2023-01-01 00:00:00'
            }
        }

        # Set up the mock
        mock_data = BytesIO(b'test data')
        self.mock_synd.download_synology_office_file.return_value = mock_data

        # Execute the test
        with patch.object(SynologyOfficeExporter, 'save_bytesio_to_file') as mock_save:
            self.exporter._process_document(file_id, display_path, file_hash)

            # Verify
            self.assertEqual(self.exporter.total_found_files, 1)
            self.assertEqual(self.exporter.downloaded_files, 1)
            self.assertEqual(self.exporter.skipped_files, 0)
            mock_save.assert_called_once()


if __name__ == '__main__':
    unittest.main()
